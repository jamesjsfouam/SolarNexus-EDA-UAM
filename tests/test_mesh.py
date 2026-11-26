import pytest

from solarnexus.mesh import Enlace, Nodo, RedMeshDC, conviene_transferir


def test_regla_de_enrutamiento():
    assert conviene_transferir(0.02, 0.12)
    assert not conviene_transferir(0.15, 0.12)


def test_transferencia_directa_cuando_es_mas_barata_que_ciclar():
    red = RedMeshDC(
        [Nodo("Copérnico", 100, 20), Nodo("Pabellón C", 0, 50)],
        [Enlace("Copérnico", "Pabellón C", capacidad=100, costo_transferencia=0.02)],
        costo_ciclado=0.12,
    )
    r = red.resolver()
    assert r.flujos[("Copérnico", "Pabellón C")] == pytest.approx(50)
    assert r.switches_cerrados == [("Copérnico", "Pabellón C")]
    assert r.desde_central["Pabellón C"] == pytest.approx(0)
    assert r.vertido["Copérnico"] == pytest.approx(30)
    # Nodo con excedente vertido: energía extra no vale nada; el receptor paga el transporte.
    assert r.precios_sombra["Copérnico"] == pytest.approx(0)
    assert r.precios_sombra["Pabellón C"] == pytest.approx(0.02)


def test_switch_abierto_si_transferir_cuesta_mas_que_ciclar():
    red = RedMeshDC(
        [Nodo("A", 100, 0), Nodo("B", 0, 50)],
        [Enlace("A", "B", capacidad=100, costo_transferencia=0.20)],
        costo_ciclado=0.12,
    )
    r = red.resolver()
    assert r.switches_cerrados == []
    assert r.desde_central["B"] == pytest.approx(50)
    assert r.precios_sombra["B"] == pytest.approx(0.12)


def test_congestion_y_perdidas_elevan_el_precio_sombra():
    red = RedMeshDC(
        [Nodo("A", 100, 0), Nodo("B", 0, 80)],
        [Enlace("A", "B", capacidad=50, costo_transferencia=0.01, perdida=0.04)],
        costo_ciclado=0.12,
    )
    r = red.resolver()
    assert r.flujos[("A", "B")] == pytest.approx(50)
    assert r.desde_central["B"] == pytest.approx(80 - 50 * 0.96)
    assert r.precios_sombra["B"] == pytest.approx(0.12)
    # Enlace saturado: A solo puede verter, su energía marginal vale 0.
    assert r.precios_sombra["A"] == pytest.approx(0)


def test_costo_fijo_de_switch_puede_dejarlo_abierto():
    red = RedMeshDC(
        [Nodo("A", 10, 0), Nodo("B", 0, 1)],
        [Enlace("A", "B", capacidad=10, costo_transferencia=0.0, costo_switch=1.0)],
        costo_ciclado=0.12,
    )
    assert red.resolver().switches_cerrados == []


def test_validaciones():
    with pytest.raises(ValueError):
        RedMeshDC([Nodo("A", 1, 1), Nodo("A", 1, 1)], [], 0.1)
    with pytest.raises(ValueError):
        RedMeshDC([Nodo("A", 1, 1)], [Enlace("A", "Z", 1)], 0.1)
