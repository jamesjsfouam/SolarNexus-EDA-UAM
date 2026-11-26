import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from solarnexus import datos  # noqa: E402
from solarnexus.web.app import app  # noqa: E402


@pytest.fixture
def cliente():
    with TestClient(app) as c:
        c.post("/api/datos/demo")
        c.post("/api/indicadores/restablecer")
        yield c


def test_pagina_y_estaticos(cliente):
    r = cliente.get("/")
    assert r.status_code == 200 and "SolarNexus" in r.text
    assert cliente.get("/estatico/app.js").status_code == 200


def test_datos_demo(cliente):
    r = cliente.get("/api/datos").json()
    assert r["origen"] == "demo" and r["dias"] == 364 and r["inicio"] == "2026-01-05"


def test_periodos(cliente):
    q = {"a_inicio": "2026-02-01", "a_fin": "2026-05-31", "b_inicio": "2026-08-01", "b_fin": "2026-11-30"}
    r = cliente.get("/api/periodos", params=q)
    assert r.status_code == 200
    j = r.json()
    assert j["chow"]["significativo"] is True
    assert j["tb_automatica"] is True
    assert 6 < j["ahorro_normalizado_pct"] < 9
    assert len(j["coeficientes"]) == 5


@pytest.mark.parametrize(
    "q, mensaje",
    [
        ({"a_inicio": "2026-02-01", "a_fin": "2026-05-31", "b_inicio": "2026-05-01", "b_fin": "2026-06-30"}, "solaparse"),
        ({"a_inicio": "2026-05-31", "a_fin": "2026-02-01", "b_inicio": "2026-08-01", "b_fin": "2026-09-30"}, "anterior"),
        ({"a_inicio": "2026-02-01", "a_fin": "2026-02-01", "b_inicio": "2026-08-01", "b_fin": "2026-09-30"}, "al menos"),
        ({"a_inicio": "ayer", "a_fin": "2026-02-01", "b_inicio": "2026-08-01", "b_fin": "2026-09-30"}, "no válida"),
    ],
)
def test_periodos_errores(cliente, q, mensaje):
    r = cliente.get("/api/periodos", params=q)
    assert r.status_code == 400 and mensaje in r.json()["detail"]


def test_despacho(cliente):
    r = cliente.get("/api/despacho", params={"fecha": "2026-09-15"})
    assert r.status_code == 200
    j = r.json()
    assert len(j["horas"]) == 24 and j["pico_previsto"] is True
    assert cliente.get("/api/despacho", params={"fecha": "2026-01-06"}).status_code == 400


def test_subir_csv_y_restablecer(cliente):
    texto = datos.a_csv(datos.generar(20, semilla=5))
    r = cliente.post("/api/datos/csv", content=texto.encode(), headers={"Content-Type": "text/csv"})
    assert r.status_code == 200 and r.json()["origen"] == "csv" and r.json()["dias"] == 20
    assert cliente.post("/api/datos/csv", content=b"basura").status_code == 400
    assert cliente.post("/api/datos/demo").json()["origen"] == "demo"


def test_indicadores(cliente):
    j = cliente.get("/api/indicadores").json()
    assert (j["a"], j["b"]) == ("2024", "2025")
    assert any("per cápita" in a for a in j["advertencias"])
    assert any("implícito" in a for a in j["advertencias"])
    assert j["periodos"][1]["emisiones_netas_kg"] == pytest.approx(41122.23)
    periodos = j["periodos"] + [{"periodo": "2026", "pct_solar": 40, "intensidad_kwh_m2": 99}]
    r = cliente.put("/api/indicadores", json={"periodos": periodos, "a": "2025", "b": "2026"})
    assert r.status_code == 200
    solar = next(f for f in r.json()["comparacion"] if f["clave"] == "pct_solar")
    assert solar["cambio"] == pytest.approx(6)
    assert cliente.put("/api/indicadores", json={"periodos": [{"periodo": "x", "pct_solar": 200}]}).status_code == 400
    assert cliente.get("/api/indicadores", params={"a": "1999", "b": "2025"}).status_code == 404
