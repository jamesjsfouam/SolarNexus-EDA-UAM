import math

import numpy as np
import pytest

from solarnexus import datos
from solarnexus.oraculo import Observaciones, Pronostico, ajustar, cdd, seleccionar_por_aic


@pytest.fixture(scope="module")
def serie():
    return datos.generar(60, semilla=1)


def test_cdd():
    assert list(cdd(np.array([20.0, 27.0, 30.5]), 27.0)) == [0.0, 0.0, 3.5]


def test_recupera_coeficientes_verdaderos(serie):
    modelo = ajustar(serie.observaciones, datos.TB_VERDADERA)
    assert modelo.beta == pytest.approx(datos.BETA_VERDADERO, abs=0.15)
    assert math.sqrt(modelo.sigma2) == pytest.approx(datos.SIGMA_VERDADERA, rel=0.1)
    assert modelo.r2 > 0.95


def test_aic_elige_la_temperatura_base_verdadera(serie):
    mejor, candidatos = seleccionar_por_aic(serie.observaciones, range(22, 31))
    assert mejor.tb == datos.TB_VERDADERA
    assert len(candidatos) == 9


def test_aic_y_aic_eviews_son_coherentes(serie):
    m = ajustar(serie.observaciones, 27)
    assert m.aic_eviews == pytest.approx(m.aic / m.n)


def test_probabilidad_en_margen():
    p = Pronostico(ln_consumo=np.array([5.0]), sigma_f=np.array([0.05]))
    # delta = 1.96·sigma  →  P ≈ 0.95
    assert p.prob_en_margen(1.96 * 0.05)[0] == pytest.approx(0.95, abs=1e-3)
    bajo, alto = p.intervalo(0.05)
    assert bajo[0] < math.exp(5.0) < alto[0]


def test_pronostico_tiene_error_mayor_que_sigma(serie):
    m = ajustar(serie.observaciones, 27)
    pron = m.pronosticar(serie.dia(0).observaciones)
    assert np.all(pron.sigma_f >= math.sqrt(m.sigma2))


def test_validaciones():
    with pytest.raises(ValueError):
        Observaciones(np.ones(3), np.ones(3), np.ones(2), np.ones(3))
    with pytest.raises(ValueError):
        Observaciones(np.ones(3), np.ones(3), np.zeros(3), np.ones(3))
    with pytest.raises(ValueError):
        ajustar(Observaciones(np.ones(3), np.ones(3), np.ones(3), np.ones(3)), 27)
