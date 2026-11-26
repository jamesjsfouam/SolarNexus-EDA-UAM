import pytest

from solarnexus.despacho import Bateria, ControladorDespacho, Regimen

HORAS = [11, 12, 14, 15, 16]


def controlador(soc=0.0):
    return ControladorDespacho(Bateria(capacidad_kwh=1000, potencia_max_kw=200, soc_kwh=soc, eficiencia_carga=1.0))


def test_dia_con_pico_carga_al_mediodia_y_recorta_el_pico():
    c = controlador()
    plan = c.planificar(HORAS, consumo=[200, 200, 500, 500, 500], pv=[400, 400, 300, 300, 300], prob_en_margen=[0.99] * 5)
    regimenes = [d.regimen for d in plan]
    assert regimenes[:2] == [Regimen.CARGA, Regimen.CARGA]
    assert all(d.flujos.exportacion == 0 for d in plan)
    assert regimenes[2:] == [Regimen.PEAK_SHAVING, Regimen.PEAK_SHAVING, Regimen.AUTOCONSUMO]
    # 400 kWh almacenados: 200 + 200 descargados, la tercera hora del pico va a red.
    assert plan[4].flujos.red == pytest.approx(200)
    assert all(d.flujos.cuadra() for d in plan)


def test_sin_pico_y_pronostico_fiable_exporta():
    c = controlador()
    plan = c.planificar(HORAS, consumo=[100] * 5, pv=[400] * 5, prob_en_margen=[0.99] * 5)
    assert all(d.regimen is Regimen.EXPORTACION for d in plan)
    assert all(d.flujos.exportacion == pytest.approx(300) for d in plan)
    assert c.bateria.soc_kwh == 0


def test_pronostico_poco_fiable_bloquea_la_exportacion():
    c = controlador()
    plan = c.planificar([12], consumo=[100], pv=[400], prob_en_margen=[0.80])
    assert plan[0].regimen is Regimen.CARGA
    # potencia máxima 200: el resto sale como exportación residual
    assert plan[0].flujos.b_carga == pytest.approx(200)
    assert plan[0].flujos.exportacion == pytest.approx(100)


def test_bateria_respeta_limites():
    b = Bateria(capacidad_kwh=100, potencia_max_kw=60, soc_kwh=20, soc_min_kwh=10, eficiencia_carga=0.9)
    assert b.descargar(50) == pytest.approx(10)
    assert b.cargar(500) == pytest.approx(60)
    assert b.soc_kwh == pytest.approx(10 + 54)
    with pytest.raises(ValueError):
        Bateria(capacidad_kwh=10, potencia_max_kw=5, soc_kwh=20)
