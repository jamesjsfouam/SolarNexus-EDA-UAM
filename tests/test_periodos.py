import pytest

from solarnexus import datos
from solarnexus.periodos import comparar_periodos


@pytest.fixture(scope="module")
def anio():
    return datos.generar_anio_demo()


def test_detecta_la_mejora_de_eficiencia(anio):
    r = comparar_periodos(
        anio.entre("2026-02-01", "2026-05-31").observaciones,
        anio.entre("2026-08-01", "2026-11-30").observaciones,
    )
    assert r.tb == datos.TB_VERDADERA
    assert r.cambio_significativo()
    # Mejora simulada: ln C − 0.08  →  1 − e^−0.08 ≈ 7.7 % de ahorro
    assert r.ahorro_normalizado_pct == pytest.approx(7.7, abs=1.0)
    assert r.aic_separados < r.conjunto.aic


def test_sin_cambio_no_hay_ruptura(anio):
    r = comparar_periodos(
        anio.entre("2026-02-01", "2026-03-29").observaciones,
        anio.entre("2026-04-06", "2026-05-31").observaciones,
    )
    assert not r.cambio_significativo()
    assert abs(r.ahorro_normalizado_pct) < 2
    assert r.chow_gl == (5, r.a.n + r.b.n - 10)


def test_tb_fija_y_coeficientes(anio):
    r = comparar_periodos(
        anio.entre("2026-02-01", "2026-03-31").observaciones,
        anio.entre("2026-09-01", "2026-10-31").observaciones,
        tb=26,
    )
    assert r.tb == 26
    assert [c.nombre for c in r.coeficientes] == ["b0", "b1_cdd", "b2_hum", "b3_ln_act", "b4_ln_area"]
    assert all(0 <= c.p_valor <= 1 for c in r.coeficientes)


def test_csv_ida_y_vuelta(anio):
    tramo = anio.entre("2026-03-02", "2026-03-04")
    leida = datos.cargar_csv(datos.a_csv(tramo))
    assert len(leida) == 72
    assert str(leida.fechas[0]) == "2026-03-02T00"
    assert leida.observaciones.consumo == pytest.approx(tramo.observaciones.consumo, abs=0.01)
    assert list(leida.dia_semana[:1]) == [0]  # lunes


def test_csv_humedad_en_porcentaje_y_errores():
    filas = ["fecha,temperatura,humedad,actividad,area,consumo"] + [
        f"2026-01-05 {h:02d}:00,28,75,0.5,5000,200" for h in range(24)
    ]
    s = datos.cargar_csv("\n".join(filas))
    assert s.observaciones.humedad[0] == pytest.approx(0.75)
    assert s.pv.sum() == 0
    with pytest.raises(ValueError, match="Faltan columnas"):
        datos.cargar_csv("fecha,temperatura\n2026-01-05T00:00,28\n")
    with pytest.raises(ValueError, match="repetidas"):
        datos.cargar_csv("\n".join(filas + [filas[1]]))
