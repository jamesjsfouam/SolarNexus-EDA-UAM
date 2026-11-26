import pytest

from solarnexus.balance import FlujosEnergia, consumo_base, consumo_extendido


def test_ecuacion_base_es_caso_particular_de_la_extendida():
    assert consumo_base(100, 50, 20) == consumo_extendido(100, 50, 0, 0, 20) == 130


def test_flujos_que_cuadran():
    f = FlujosEnergia(consumo=300, red=50, pv=200, b_carga=0, b_descarga=50, exportacion=0)
    assert f.cuadra()


def test_flujos_que_no_cuadran():
    f = FlujosEnergia(consumo=300, red=0, pv=200, b_carga=0, b_descarga=0, exportacion=0)
    assert not f.cuadra()
    assert f.residuo == pytest.approx(100)


def test_rechaza_negativos_y_carga_descarga_simultanea():
    with pytest.raises(ValueError):
        FlujosEnergia(consumo=10, red=-1, pv=11, b_carga=0, b_descarga=0, exportacion=0)
    with pytest.raises(ValueError):
        FlujosEnergia(consumo=10, red=0, pv=10, b_carga=5, b_descarga=5, exportacion=0)
