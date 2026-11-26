import json
import math
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

import numpy as np
import pytest

from solarnexus import datos
from solarnexus.estadistica import a_contrato, calcular_metricas, escenario_climatologico, pronosticar_dia, validar
from solarnexus.estadistica import cliente
from solarnexus.estadistica.__main__ import main
from solarnexus.estadistica.diagnosticos import breusch_godfrey, durbin_watson, jarque_bera, newey_west
from solarnexus.estadistica.validacion import factor_calibracion
from solarnexus.oraculo import ajustar


@pytest.fixture(scope="module")
def anio():
    return datos.generar_anio_demo()


@pytest.fixture(scope="module")
def reporte(anio):
    # Se excluye el quiebre del 1 de agosto para que la línea base sea del régimen actual.
    return validar(anio, "2026-10-01", dias_prueba=21, inicio_entrenamiento="2026-08-01")


# ---------- métricas ----------

def test_metricas_ashrae():
    real = np.array([100.0, 110, 90, 100])
    m = calcular_metricas(real, real)
    assert m.cv_rmse_pct == 0 and m.nmbe_pct == 0 and m.cumple_ashrae
    sesgado = calcular_metricas(real, real * 0.8)  # subestima 20 %
    assert sesgado.nmbe_pct == pytest.approx(20)
    assert not sesgado.cumple_ashrae
    assert calcular_metricas(real, real * 0.8, frecuencia="mensual").nmbe_pct == pytest.approx(20)
    with pytest.raises(ValueError):
        calcular_metricas(real, real[:2])
    with pytest.raises(ValueError):
        calcular_metricas(real, real, frecuencia="semanal")


# ---------- diagnósticos ----------

def test_durbin_watson_y_breusch_godfrey_detectan_ar1():
    rng = np.random.default_rng(0)
    n = 2000
    x = np.column_stack([np.ones(n), rng.normal(size=n)])
    ruido = rng.normal(size=n)
    assert durbin_watson(ruido) == pytest.approx(2, abs=0.15)
    assert not breusch_godfrey(x, ruido, 4).rechaza()

    ar = np.zeros(n)
    for t in range(1, n):
        ar[t] = 0.7 * ar[t - 1] + ruido[t]
    assert durbin_watson(ar) < 1
    assert breusch_godfrey(x, ar, 4).rechaza()


def test_jarque_bera_y_newey_west():
    rng = np.random.default_rng(1)
    assert not jarque_bera(rng.normal(size=3000)).rechaza()
    assert jarque_bera(rng.exponential(size=3000)).rechaza()

    n = 3000
    x = np.column_stack([np.ones(n), rng.normal(size=n)])
    e = np.zeros(n)
    u = rng.normal(size=n)
    for t in range(1, n):
        e[t] = 0.8 * e[t - 1] + u[t]
    cov, rezagos = newey_west(x, e)
    sigma2 = e @ e / (n - 2)
    ee_mco = np.sqrt(np.diag(sigma2 * np.linalg.inv(x.T @ x)))
    # Con autocorrelación positiva el error HAC de la constante es mucho mayor que el de MCO.
    assert np.sqrt(cov[0, 0]) > 2 * ee_mco[0]
    assert rezagos >= 1


def test_diagnosticos_del_modelo(reporte):
    d = reporte.diagnosticos
    assert len(d.coeficientes) == 5
    assert all(c.ee_hac > 0 for c in d.coeficientes)
    assert d.factor_duan == pytest.approx(1.0, abs=0.01)


# ---------- calibración y validación ----------

def test_factor_calibracion_recupera_la_escala():
    rng = np.random.default_rng(2)
    sigma = np.full(20000, 0.05)
    errores = rng.normal(0, 0.10, size=sigma.size)  # error real: el doble de lo que dice el modelo
    aciertos = (np.abs(errores) <= 0.1).astype(float)
    assert factor_calibracion(sigma, aciertos, 0.1) == pytest.approx(2.0, rel=0.05)


def test_validacion_demo(reporte):
    assert reporte.dias_prueba == 21
    assert reporte.fuera_horario.cumple_ashrae
    assert abs(reporte.fuera_horario.nmbe_pct) < 3
    # El modelo es demasiado confiado al usar regresores esperados: k > 1.
    assert reporte.factor_calibracion > 1
    assert reporte.prob_media_sin_calibrar > reporte.frecuencia_en_margen
    assert reporte.prob_media_calibrada == pytest.approx(reporte.frecuencia_en_margen, abs=0.01)
    assert reporte.cobertura_95 == pytest.approx(0.95, abs=0.04)
    json.dumps(reporte.a_dict())  # serializable


def test_validacion_errores(anio):
    with pytest.raises(ValueError, match="14 días"):
        validar(anio, "2026-01-10")


# ---------- escenario, pronóstico y contrato ----------

def test_escenario_climatologico(anio):
    esc = escenario_climatologico(anio, "2026-11-03")  # martes
    assert len(esc.horas) == 24 and esc.dias_usados == 28
    assert esc.observaciones.consumo is None
    assert esc.pv[0] == 0 and esc.pv[12] > 300
    finde = escenario_climatologico(anio, "2026-11-07")  # sábado
    assert finde.observaciones.actividad.max() < esc.observaciones.actividad.max()
    propio = escenario_climatologico(anio, "2026-11-03", actividad=np.full(24, 0.05))
    assert np.all(propio.observaciones.actividad == 0.05)
    with pytest.raises(ValueError):
        escenario_climatologico(anio, "2026-01-05")
    with pytest.raises(ValueError):
        escenario_climatologico(anio, "2026-11-03", actividad=np.ones(5))


def test_contrato(anio):
    historico = anio.antes_de("2026-11-03")
    modelo = ajustar(historico.observaciones, 27)
    dias = [pronosticar_dia(modelo, escenario_climatologico(historico, f), factor_calibracion=2.0)
            for f in ("2026-11-04", "2026-11-03")]
    c = a_contrato(dias, notes="x" * 3000)
    p = c["points"]
    assert len(p) == 48 and len(c["notes"]) == 2000
    assert p[0]["interval_start"] == "2026-11-03T00:00:00-06:00"
    assert p[24]["interval_start"] == "2026-11-04T00:00:00-06:00"
    instantes = [datetime.fromisoformat(x["interval_start"]) for x in p]
    assert instantes == sorted(instantes)
    assert all((b - a).total_seconds() == 3600 for a, b in zip(instantes, instantes[1:]))
    assert all(0 <= x["probability_within_margin"] <= 1 and x["demand_kwh"] > 0 for x in p)
    # k = 2 baja la probabilidad respecto a la sin calibrar
    sin = pronosticar_dia(modelo, escenario_climatologico(historico, "2026-11-03"))
    assert dias[1].probabilidad_en_margen.mean() < sin.probabilidad_en_margen.mean()
    with pytest.raises(ValueError, match="168"):
        a_contrato(dias * 4)


# ---------- cliente de la API ----------

def _registro(utc: str, consumo=100.0, actividad=0.5):
    return {"interval_start": utc, "temperature_c": 30.0, "humidity_pct": 70.0, "activity_index": actividad,
            "conditioned_area_m2": 5000.0, "consumption_kwh": consumo, "pv_generation_kwh": None}


def test_mediciones_a_serie():
    registros = [_registro(f"2026-11-02T{h:02d}:00:00Z", actividad=0.0 if h == 0 else 0.5) for h in range(23, -1, -1)]
    s = cliente.mediciones_a_serie(registros)
    assert len(s) == 24
    assert str(s.fechas[0]) == "2026-11-01T18"  # 00:00 UTC = 18:00 del día anterior en Managua
    assert s.observaciones.humedad[0] == pytest.approx(0.70)
    assert s.observaciones.actividad.min() == cliente.ACTIVIDAD_MINIMA
    assert s.pv.sum() == 0
    with pytest.raises(ValueError, match="24"):
        cliente.mediciones_a_serie(registros[:5])
    with pytest.raises(ValueError, match="repetidas"):
        cliente.mediciones_a_serie(registros + registros[:1])


class _BackendFalso(BaseHTTPRequestHandler):
    registros: list = []
    recibido: dict = {}

    def _json(self, codigo, cuerpo):
        datos_ = json.dumps(cuerpo).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(datos_)))
        self.end_headers()
        self.wfile.write(datos_)

    def do_GET(self):  # noqa: N802
        from urllib.parse import parse_qs, urlparse
        q = parse_qs(urlparse(self.path).query)
        limite, desde = int(q["limit"][0]), int(q["offset"][0])
        self._json(200, self.registros[desde:desde + limite])

    def do_POST(self):  # noqa: N802
        largo = int(self.headers["Content-Length"])
        type(self).recibido = json.loads(self.rfile.read(largo))
        if not self.recibido.get("points"):
            self._json(422, {"detail": "sin puntos"})
        else:
            self._json(201, {"id": 7, **self.recibido})

    def log_message(self, *args):
        pass


@pytest.fixture
def backend():
    inicio = np.datetime64("2026-09-01T00", "h")
    _BackendFalso.registros = [_registro(f"{inicio + np.timedelta64(i, 'h')}:00:00Z") for i in range(1500)][::-1]
    servidor = HTTPServer(("127.0.0.1", 0), _BackendFalso)
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    yield f"http://127.0.0.1:{servidor.server_address[1]}"
    servidor.shutdown()


def test_cliente_pagina_y_envia(backend):
    s = cliente.leer_mediciones(backend)
    assert len(s) == 1500  # dos páginas: 1000 + 500
    r = cliente.enviar_pronostico(backend, {"points": [{"x": 1}]})
    assert r["id"] == 7 and _BackendFalso.recibido["points"] == [{"x": 1}]
    with pytest.raises(cliente.ErrorAPI, match="422"):
        cliente.enviar_pronostico(backend, {"points": []})
    with pytest.raises(ValueError, match="URL"):
        cliente.leer_mediciones("ftp://ejemplo")


def test_cliente_sin_conexion():
    with pytest.raises(cliente.ErrorAPI, match="conectar"):
        cliente.leer_mediciones("http://127.0.0.1:9")


# ---------- línea de comandos ----------

def test_cli_validar_json(capsys):
    assert main(["validar", "--desde", "2026-08-01", "--dias", "14", "--json"]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["modelo"]["tb"] == 27 and "calibracion" in d


def test_cli_pronosticar(tmp_path, capsys):
    salida = tmp_path / "p.json"
    assert main(["pronosticar", "--desde", "2026-08-01", "--dias", "14", "--horizonte", "2", "--salida", str(salida)]) == 0
    cuerpo = json.loads(salida.read_text(encoding="utf-8"))
    assert len(cuerpo["points"]) == 48 and cuerpo["source"] == "statistics-service"
    assert "k=" in cuerpo["notes"]
    with pytest.raises(SystemExit):
        main(["pronosticar", "--horizonte", "9"])


def test_cli_exportar_y_reporte_para_r(tmp_path, capsys):
    csv = tmp_path / "datos" / "d.csv"
    assert main(["exportar", "--desde", "2026-08-01", "--salida", str(csv)]) == 0
    serie = datos.cargar_csv(csv.read_text(encoding="utf-8"))
    assert str(serie.fechas[0]) == "2026-08-01T00"
    reporte = tmp_path / "r.json"
    assert main(["validar", "--csv", str(csv), "--inicio-prueba", "2026-10-01", "--dias", "7",
                 "--desde", "2026-08-01", "--salida", str(reporte)]) == 0
    d = json.loads(reporte.read_text(encoding="utf-8"))
    # Campos que lee analisis/contraste_python.R
    assert d["backtest"]["inicio"] == "2026-10-01" and d["backtest"]["inicio_entrenamiento"] == "2026-08-01"
    assert {"valor", "ee_mco", "ee_hac"} <= set(d["coeficientes"][0])
    assert {p["nombre"] for p in d["diagnosticos"]["pruebas"]} == {"Breusch-Godfrey", "Breusch-Pagan", "Jarque-Bera"}
    assert {"aic", "r2", "n", "tb"} <= set(d["modelo"]) and "cv_rmse_pct" in d["dentro_muestra"]


def test_cli_error_controlado(capsys):
    assert main(["validar", "--inicio-prueba", "2026-01-10"]) == 1
    assert "Error" in capsys.readouterr().err


def test_probabilidad_formula():
    from solarnexus.estadistica.pronostico import prob_en_margen
    assert prob_en_margen(np.array([0.05]), 0.1)[0] == pytest.approx(math.erf(0.1 / (0.05 * math.sqrt(2))))
