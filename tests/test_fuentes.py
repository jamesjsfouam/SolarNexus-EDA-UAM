"""Fuentes de clima con un servidor HTTP simulado (sin acceso a Internet)."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import numpy as np
import pytest

from solarnexus import datos
from solarnexus.estadistica import fuentes, validar
from solarnexus.estadistica.__main__ import main
from solarnexus.estadistica.pronostico import escenario_con_clima


def _horas_locales(inicio: str, fin: str) -> list[str]:
    d0, d1 = np.datetime64(inicio, "h"), np.datetime64(fin, "h") + np.timedelta64(23, "h")
    return [str(t) + ":00" for t in np.arange(d0, d1 + np.timedelta64(1, "h"))]


class _Simulador(BaseHTTPRequestHandler):
    peticiones: list = []

    def _json(self, cuerpo, codigo=200):
        b = json.dumps(cuerpo).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):  # noqa: N802
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        type(self).peticiones.append((u.path, q))
        if u.path in ("/v1/forecast", "/v1/archive"):
            if "forecast_days" in q:
                fin = np.datetime64("2026-11-26", "D") + np.timedelta64(int(q["forecast_days"]) - 1, "D")
                horas = _horas_locales("2026-11-26", str(fin))
            else:
                horas = _horas_locales(q["start_date"], q["end_date"])
            n = len(horas)
            h = [int(t[11:13]) for t in horas]
            temperatura = [29 + 5 * np.sin(2 * np.pi * (x - 9) / 24) for x in h]
            temperatura[3] = None  # un hueco
            return self._json({"hourly": {
                "time": horas,
                "temperature_2m": temperatura,
                "relative_humidity_2m": [70] * n,
                "shortwave_radiation": [max(0.0, 900 * np.sin(np.pi * (x - 6) / 12)) for x in h],
            }})
        if u.path == "/api/temporal/hourly/point":
            d0 = np.datetime64(f"{q['start'][:4]}-{q['start'][4:6]}-{q['start'][6:]}", "h")
            d1 = np.datetime64(f"{q['end'][:4]}-{q['end'][4:6]}-{q['end'][6:]}", "h") + np.timedelta64(23, "h")
            claves = [str(t).replace("-", "").replace("T", "") for t in np.arange(d0, d1 + np.timedelta64(1, "h"))]
            # T2M = hora UTC, para comprobar la conversión a Managua; radiación sin publicar (-999).
            return self._json({
                "header": {"fill_value": -999.0},
                "properties": {"parameter": {
                    "T2M": {k: float(k[8:10]) for k in claves},
                    "RH2M": {k: 80.0 for k in claves},
                    "ALLSKY_SFC_SW_DWN": {k: -999.0 for k in claves},
                }},
            })
        self._json({"error": True, "reason": "ruta desconocida"}, 400)

    def log_message(self, *args):
        pass


@pytest.fixture
def servidor(monkeypatch):
    _Simulador.peticiones = []
    srv = HTTPServer(("127.0.0.1", 0), _Simulador)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    for nombre in ("URL_OPEN_METEO", "URL_OPEN_METEO_PASADOS", "URL_OPEN_METEO_ARCHIVO", "URL_NASA_POWER"):
        monkeypatch.setattr(fuentes, nombre, base)
    yield base
    srv.shutdown()


def test_open_meteo_pronostico_y_parametros(servidor):
    c = fuentes.open_meteo_pronostico(2)
    assert len(c) == 48 and c.fuente == "open-meteo"
    assert np.isnan(c.temperatura[3]) and c.humedad[0] == pytest.approx(0.70)
    ruta, q = _Simulador.peticiones[-1]
    assert ruta == "/v1/forecast" and q["timezone"] == "America/Managua"
    assert q["latitude"] == str(fuentes.LAT_UAM) and "shortwave_radiation" in q["hourly"]
    with pytest.raises(ValueError):
        fuentes.open_meteo_pronostico(20)


def test_open_meteo_historico(servidor):
    pasados = fuentes.open_meteo_historico("2026-10-01", "2026-10-03")
    assert pasados.fuente == "open-meteo-pasados" and len(pasados) == 72
    assert _Simulador.peticiones[-1][0] == "/v1/forecast"
    era5 = fuentes.open_meteo_historico("2026-10-01", "2026-10-01", pronosticos_pasados=False)
    assert era5.fuente == "open-meteo-archivo" and _Simulador.peticiones[-1][0] == "/v1/archive"
    with pytest.raises(ValueError):
        fuentes.open_meteo_historico("2026-10-05", "2026-10-01")


def test_nasa_power_utc_a_managua_y_relleno(servidor, monkeypatch):
    c = fuentes.nasa_power("2026-10-01", "2026-10-02")
    assert len(c) == 48 and str(c.fechas[0]) == "2026-10-01T00"
    # 00:00 en Managua = 06:00 UTC; el simulador devuelve la hora UTC como temperatura.
    assert c.temperatura[0] == 6 and c.temperatura[18] == 0
    assert np.isnan(c.radiacion).all()  # -999 → NaN
    assert c.humedad[0] == pytest.approx(0.80)
    monkeypatch.setattr(fuentes, "_DIAS_POR_PETICION_POWER", 2)
    _Simulador.peticiones = []
    largo = fuentes.nasa_power("2026-10-01", "2026-10-06")
    assert len(largo) == 6 * 24 and len(_Simulador.peticiones) == 4  # 7 días UTC en tramos de 2


def test_perfil_24h_y_csv(servidor):
    c = fuentes.open_meteo_historico("2026-10-01", "2026-10-02")
    t, h, r = c.perfil_24h("2026-10-02")
    assert t.shape == (24,) and r[12] == pytest.approx(900)
    assert np.isnan(fuentes.Clima("x", c.fechas[:0], c.temperatura[:0], c.humedad[:0], c.radiacion[:0]).perfil_24h("2026-10-02")[0]).all()
    assert c.a_csv().splitlines()[0] == "fecha,temperatura,humedad,radiacion"


def test_pv_desde_radiacion():
    pv = fuentes.pv_desde_radiacion(np.array([0, 500, 1000, -5]), kwp=730, rendimiento=0.8)
    assert list(pv) == pytest.approx([0, 292, 584, 0])
    with pytest.raises(ValueError):
        fuentes.pv_desde_radiacion(np.ones(2), kwp=0)


def test_escenario_con_clima(servidor):
    serie = datos.generar_anio_demo()
    c = fuentes.open_meteo_historico("2026-11-03", "2026-11-03")
    e = escenario_con_clima(serie, "2026-11-03", c, kwp=730)
    assert e.origen == "open-meteo-pasados"
    t, _, r = c.perfil_24h("2026-11-03")
    # Hora 3 sin dato en la fuente: conserva el valor climatológico.
    assert e.observaciones.temperatura[15] == pytest.approx(t[15])
    assert not np.isnan(e.observaciones.temperatura[3])
    assert e.pv[12] == pytest.approx(730 * 0.9 * 0.8)
    sin_kwp = escenario_con_clima(serie, "2026-11-03", c)
    assert sin_kwp.pv[12] != pytest.approx(e.pv[12])  # PV histórica del campus
    with pytest.raises(ValueError, match="no tiene datos"):
        escenario_con_clima(serie, "2026-12-25", c)


def test_validar_con_clima(servidor):
    serie = datos.generar_anio_demo()
    c = fuentes.open_meteo_historico("2026-10-01", "2026-10-04")
    r = validar(serie, "2026-10-01", dias_prueba=6, inicio_entrenamiento="2026-08-01", clima=c)
    # 4 días con la fuente y 2 sin datos → escenario climatológico.
    assert r.regresores == {"climatológico": 2, "open-meteo-pasados": 4}
    assert r.a_dict()["backtest"]["regresores"] == r.regresores


def test_cli_clima_y_pronostico(servidor, tmp_path, capsys):
    salida = tmp_path / "clima.csv"
    assert main(["clima", "--fuente", "nasa-power", "--inicio", "2026-10-01", "--fin", "2026-10-01",
                 "--salida", str(salida)]) == 0
    assert len(salida.read_text(encoding="utf-8").splitlines()) == 25
    p = tmp_path / "p.json"
    assert main(["pronosticar", "--desde", "2026-08-01", "--dias", "7", "--clima", "open-meteo-pasados",
                 "--kwp", "730", "--salida", str(p)]) == 0
    cuerpo = json.loads(p.read_text(encoding="utf-8"))
    assert "Open-Meteo.com" in cuerpo["notes"] and "open-meteo-pasados" in cuerpo["notes"]
    assert cuerpo["points"][12]["pv_generation_kwh"] == pytest.approx(730 * 0.9 * 0.8, rel=1e-3)
    # NASA sin radiación publicada: avisa y usa la PV histórica.
    assert main(["pronosticar", "--desde", "2026-08-01", "--dias", "7", "--clima", "nasa-power", "--kwp", "730"]) == 0
    assert "aún no publica la radiación" in capsys.readouterr().out
    # El pronóstico de Open-Meteo no sirve para validar días pasados.
    with pytest.raises(SystemExit):
        main(["validar", "--clima", "open-meteo"])
