"""Pruebas de diagnóstico de los residuos del modelo 3P (en escala log).

- Durbin-Watson y Breusch-Godfrey: autocorrelación. Con datos horarios casi siempre
  aparece, y entonces los errores estándar MCO subestiman la incertidumbre.
- Breusch-Pagan (versión de Koenker): heterocedasticidad.
- Jarque-Bera: normalidad, supuesto de la probabilidad en el margen.
- Errores estándar HAC de Newey-West: robustos a ambas cosas; son los que deben
  usarse para decidir si un coeficiente es significativo.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy import stats

from ..oraculo import NOMBRES_COEFICIENTES, ModeloAjustado, Observaciones


@dataclass(frozen=True)
class Prueba:
    nombre: str
    estadistico: float
    p_valor: float | None
    hipotesis_nula: str

    def rechaza(self, alpha: float = 0.05) -> bool:
        return bool(self.p_valor is not None and self.p_valor < alpha)


@dataclass(frozen=True)
class CoeficienteHAC:
    nombre: str
    valor: float
    ee_mco: float
    ee_hac: float
    t_hac: float
    p_valor_hac: float


@dataclass(frozen=True)
class Diagnosticos:
    durbin_watson: float
    breusch_godfrey: Prueba
    breusch_pagan: Prueba
    jarque_bera: Prueba
    coeficientes: list[CoeficienteHAC]
    rezagos_hac: int
    factor_duan: float  # E[exp(e)]: corrige el sesgo al volver de logaritmos a kWh

    def avisos(self, alpha: float = 0.05) -> list[str]:
        avisos = []
        if self.breusch_godfrey.rechaza(alpha) or not 1.5 <= self.durbin_watson <= 2.5:
            avisos.append("Residuos autocorrelacionados: usa los errores HAC, no los de MCO.")
        if self.breusch_pagan.rechaza(alpha):
            avisos.append("Heterocedasticidad: la varianza del error cambia con los regresores.")
        if self.jarque_bera.rechaza(alpha):
            avisos.append("Residuos no normales: la probabilidad en el margen debe calibrarse empíricamente.")
        return avisos


def residuos(modelo: ModeloAjustado, obs: Observaciones) -> tuple[np.ndarray, np.ndarray]:
    """(X, e) con e = ln C - X·β."""
    x = obs.matriz(modelo.tb)
    return x, np.log(np.asarray(obs.consumo, dtype=float)) - x @ modelo.beta


def _r2_auxiliar(y: np.ndarray, x: np.ndarray) -> float:
    b, *_ = np.linalg.lstsq(x, y, rcond=None)
    u = y - x @ b
    sst = float(((y - y.mean()) ** 2).sum())
    return 1 - float(u @ u) / sst if sst > 0 else 0.0


def durbin_watson(e: np.ndarray) -> float:
    return float(np.sum(np.diff(e) ** 2) / np.sum(e**2))


def breusch_godfrey(x: np.ndarray, e: np.ndarray, rezagos: int) -> Prueba:
    n = len(e)
    rez = np.column_stack([np.concatenate([np.zeros(k), e[:-k]]) for k in range(1, rezagos + 1)])
    lm = n * _r2_auxiliar(e, np.column_stack([x, rez]))
    return Prueba("Breusch-Godfrey", lm, float(stats.chi2.sf(lm, rezagos)), f"sin autocorrelación hasta el rezago {rezagos}")


def breusch_pagan(x: np.ndarray, e: np.ndarray) -> Prueba:
    lm = len(e) * _r2_auxiliar(e**2, x)
    return Prueba("Breusch-Pagan", lm, float(stats.chi2.sf(lm, x.shape[1] - 1)), "varianza constante")


def jarque_bera(e: np.ndarray) -> Prueba:
    jb, p = stats.jarque_bera(e)
    return Prueba("Jarque-Bera", float(jb), float(p), "residuos normales")


def newey_west(x: np.ndarray, e: np.ndarray, rezagos: int | None = None) -> tuple[np.ndarray, int]:
    """Matriz de covarianza HAC de Newey-West (núcleo de Bartlett)."""
    n = len(e)
    if rezagos is None:
        rezagos = int(math.floor(4 * (n / 100) ** (2 / 9)))
    xe = x * e[:, None]
    s = xe.T @ xe
    for l in range(1, rezagos + 1):
        g = xe[l:].T @ xe[:-l]
        s += (1 - l / (rezagos + 1)) * (g + g.T)
    xtx_inv = np.linalg.pinv(x.T @ x)
    return xtx_inv @ s @ xtx_inv, rezagos


def diagnosticar(modelo: ModeloAjustado, obs: Observaciones, rezagos_bg: int = 24) -> Diagnosticos:
    """Diagnósticos sobre la muestra de estimación. rezagos_bg=24 cubre un día de datos horarios."""
    x, e = residuos(modelo, obs)
    cov_hac, rezagos = newey_west(x, e)
    ee_hac = np.sqrt(np.diag(cov_hac))
    gl = len(e) - x.shape[1]
    coeficientes = [
        CoeficienteHAC(
            nombre=nombre, valor=float(b), ee_mco=float(em), ee_hac=float(eh), t_hac=float(b / eh),
            p_valor_hac=float(2 * stats.t.sf(abs(b / eh), gl)),
        )
        for nombre, b, em, eh in zip(NOMBRES_COEFICIENTES, modelo.beta, modelo.errores_estandar, ee_hac)
    ]
    return Diagnosticos(
        durbin_watson=durbin_watson(e),
        breusch_godfrey=breusch_godfrey(x, e, rezagos_bg),
        breusch_pagan=breusch_pagan(x, e),
        jarque_bera=jarque_bera(e),
        coeficientes=coeficientes,
        rezagos_hac=rezagos,
        factor_duan=float(np.mean(np.exp(e))),
    )
