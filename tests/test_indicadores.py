import pytest

from solarnexus import indicadores
from solarnexus.indicadores import IndicadoresPeriodo


def fila(filas, clave):
    return next(f for f in filas if f["clave"] == clave)


@pytest.fixture(scope="module")
def filas():
    p24, p25 = indicadores.cargar()
    return indicadores.comparar(p24, p25)


def test_valores_publicados(filas):
    solar = fila(filas, "pct_solar")
    assert solar["cambio"] == pytest.approx(9) and solar["mejora"] is True

    intensidad = fila(filas, "intensidad_kwh_m2")
    assert intensidad["cambio_relativo_pct"] == pytest.approx(-1.92, abs=0.01)
    assert intensidad["mejora"] is True

    comunidad = fila(filas, "comunidad_personas")
    assert comunidad["cambio_relativo_pct"] == pytest.approx(14.9, abs=0.05)
    assert comunidad["mejora"] is None

    export = fila(filas, "exportacion_kwh")
    assert export["a"] is None and export["b"] == 60200 and export["cambio"] is None


def test_per_capita_metodo_uam_reproduce_lo_publicado(filas):
    # La UAM publica 51.43 y 45.49 kg CO2/persona = (brutas + evitadas) / comunidad
    uam = fila(filas, "per_capita_uam_kg")
    assert uam["a"] == pytest.approx(51.43, abs=0.01)
    assert uam["b"] == pytest.approx(45.49, abs=0.01)
    assert uam["mejora"] is None  # no es un indicador de emisiones reales


def test_per_capita_real_y_netas(filas):
    real = fila(filas, "per_capita_real_kg")
    assert real["a"] == pytest.approx(38.11, abs=0.01)
    assert real["b"] == pytest.approx(25.59, abs=0.01)
    assert real["cambio_relativo_pct"] == pytest.approx(-32.9, abs=0.1)
    assert real["mejora"] is True

    netas = fila(filas, "emisiones_netas_kg")
    assert netas["b"] == pytest.approx(41122.23, abs=0.01)  # lo que el informe llama "reducción"
    assert netas["cambio"] == pytest.approx(-114839.19, abs=0.01)


def test_solar_implicita_y_advertencias():
    p24, p25 = indicadores.cargar()
    assert p24.solar_implicita_pct == pytest.approx(25.9, abs=0.1)
    assert p25.solar_implicita_pct == pytest.approx(43.7, abs=0.1)
    avisos = indicadores.advertencias_calculadas(p24, p25)
    assert len(avisos) == 1 and "2025" in avisos[0]
    assert len(indicadores.cargar_advertencias()) >= 4


def test_derivados_sin_datos():
    p = IndicadoresPeriodo("x", comunidad_personas=100)
    assert p.per_capita_real_kg is None and p.emisiones_netas_kg is None and p.solar_implicita_pct is None
    d = IndicadoresPeriodo("y", emisiones_brutas_kg=200, co2_evitado_kg=50, comunidad_personas=0).a_dict()
    assert d["emisiones_netas_kg"] == 150 and d["per_capita_real_kg"] is None


def test_validacion():
    with pytest.raises(ValueError):
        IndicadoresPeriodo.desde_dict({"periodo": "", "pct_solar": 10})
    with pytest.raises(ValueError):
        IndicadoresPeriodo.desde_dict({"periodo": "2026", "pct_solar": 120})
    with pytest.raises(ValueError):
        IndicadoresPeriodo.desde_dict({"periodo": "2026", "co2_evitado_kg": "mucho"})
    p = IndicadoresPeriodo.desde_dict({"periodo": "2026", "pct_solar": "40", "co2_evitado_kg": "", "otro": 1})
    assert p.pct_solar == 40 and p.co2_evitado_kg is None
