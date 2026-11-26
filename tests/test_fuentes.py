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
    ULTIMO_ERA5 = "2026-12-31"

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
            elif u.path == "/v1/archive":
                # ERA5 llega con retraso: el simulador solo tiene hasta ULTIMO_ERA5.
                fin = min(np.datetime64(q["end_date"]), np.datetime64(type(self).ULTIMO_ERA5))
                horas = _horas_locales(q["start_date"], str(fin)) if fin >= np.datetime64(q["start_date"]) else []
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
    _Simulador.ULTIMO_ERA5 = "2026-12-31"
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


# ---------- historial sin clima (sin estación Copérnico) ----------

def _csv_sin_clima(dias=3, inicio="2026-10-01", con_temperatura_en=()):
    s = datos.generar(dias, semilla=4, fecha_inicial=inicio)
    filas = ["fecha,temperatura,humedad,actividad,area,consumo,pv"]
    for i, linea in enumerate(datos.a_csv(s).splitlines()[1:]):
        f, t, h, a, ar, c, pv = linea.split(",")
        medido = i in con_temperatura_en
        filas.append(",".join([f, t if medido else "", h if medido else "", a, ar, c, pv]))
    return "\n".join(filas) + "\n"


def test_cargar_csv_clima_opcional():
    texto = _csv_sin_clima()
    with pytest.raises(ValueError):
        datos.cargar_csv(texto)  # la web de main sigue exigiendo el clima
    s = datos.cargar_csv(texto, clima_opcional=True)
    assert np.isnan(s.observaciones.temperatura).all() and len(s) == 72
    sin_columnas = "fecha,actividad,area,consumo\n" + "\n".join(
        f"2026-10-01T{h:02d}:00,0.5,5000,100" for h in range(24))
    s2 = datos.cargar_csv(sin_columnas, clima_opcional=True)
    assert np.isnan(s2.observaciones.humedad).all()
    with pytest.raises(ValueError, match="consumo"):
        datos.cargar_csv("fecha,actividad,area\n2026-10-01T00:00,0.5,5000\n" * 1, clima_opcional=True)


def test_completar_clima_respeta_lo_medido(servidor):
    s = datos.cargar_csv(_csv_sin_clima(con_temperatura_en=(5,)), clima_opcional=True)
    medido = s.observaciones.temperatura[5]
    r = fuentes.completar_clima(s)
    t = r.serie.observaciones.temperatura
    assert not np.isnan(t).any() and t[5] == medido  # Copérnico no se sustituye
    # El simulador de Open-Meteo deja vacía la hora 3 de cada respuesta: ERA5 rellena 70 y
    # NASA POWER, al final de la cadena, la hora que ninguna de las dos fuentes de Open-Meteo trae.
    assert r.horas_completadas == {"open-meteo-archivo": 70, "nasa-power": 1} and r.total == 71
    assert r.serie.observaciones.consumo is s.observaciones.consumo


def test_completar_clima_cadena_de_respaldo(servidor):
    _Simulador.ULTIMO_ERA5 = "2026-10-01"  # ERA5 no tiene los dos últimos días
    s = datos.cargar_csv(_csv_sin_clima(), clima_opcional=True)
    r = fuentes.completar_clima(s)
    # ERA5 cubre el 1 de octubre salvo la hora 3 (vacía en el simulador); los pronósticos archivados
    # cubren el 2 y el 3, pero su respuesta empieza el día 1 y también trae vacía esa hora 3;
    # NASA POWER la completa al final de la cadena.
    assert r.horas_completadas == {"open-meteo-archivo": 23, "open-meteo-pasados": 48, "nasa-power": 1}
    assert not np.isnan(r.serie.observaciones.temperatura).any()
    with pytest.raises(ValueError, match="No se pudo completar"):
        fuentes.completar_clima(s, cadena=("open-meteo-archivo",))
    with pytest.raises(ValueError, match="historial"):
        fuentes.completar_clima(s, cadena=("open-meteo",))


def test_mediciones_api_sin_clima():
    from solarnexus.estadistica import cliente
    registros = [{"interval_start": f"2026-10-01T{h:02d}:00:00Z", "temperature_c": None, "humidity_pct": None,
                  "activity_index": 0.5, "conditioned_area_m2": 5000.0, "consumption_kwh": 100.0,
                  "pv_generation_kwh": 0.0} for h in range(24)]
    s = cliente.mediciones_a_serie(registros)
    assert np.isnan(s.observaciones.temperatura).all() and np.isnan(s.observaciones.humedad).all()


def test_cli_completa_el_clima(servidor, tmp_path, capsys):
    entrada = tmp_path / "uam.csv"
    entrada.write_text(_csv_sin_clima(dias=20, inicio="2026-09-10"), encoding="utf-8")
    salida = tmp_path / "completo.csv"
    assert main(["exportar", "--csv", str(entrada), "--salida", str(salida)]) == 0
    assert "completado con APIs en 480 de 480 horas" in capsys.readouterr().out
    assert not np.isnan(datos.cargar_csv(salida.read_text(encoding="utf-8")).observaciones.temperatura).any()
    assert main(["validar", "--csv", str(entrada), "--dias", "3"]) == 0
    assert main(["exportar", "--csv", str(entrada), "--clima-historial", "ninguno"]) == 1
