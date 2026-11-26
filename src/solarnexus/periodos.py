"""Análisis econométrico entre dos periodos (A = referencia, B = comparación).

Para cada periodo se estima el modelo 3P con la misma temperatura base Tb (elegida
por mínimo AIC sobre los datos conjuntos, para que los coeficientes sean comparables)
y se calcula:

- Test de Chow: ¿la relación consumo–clima–actividad cambió entre A y B?
      F = [(SSR_c - SSR_a - SSR_b) / k] / [(SSR_a + SSR_b) / (n_a + n_b - 2k)]
- Diferencia de cada coeficiente con su z y p-valor (muestras independientes).
- AIC conjunto frente a la suma de AIC por periodo (¿compensa separar los modelos?).
- Ahorro normalizado (estilo ASHRAE / M&V): el modelo de A, aplicado a las condiciones
  de clima y actividad de B, da el consumo que B habría tenido "sin cambios"; la
  diferencia con el consumo real de B es el ahorro (o sobreconsumo) atribuible al cambio.

Aviso: con datos horarios los residuos suelen estar autocorrelacionados, lo que hace
los p-valores optimistas. Conviene confirmarlos con datos diarios o errores HAC.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np
from scipy import stats

from .oraculo import NOMBRES_COEFICIENTES, ModeloAjustado, Observaciones, ajustar, seleccionar_por_aic


@dataclass(frozen=True)
class ResumenPeriodo:
    modelo: ModeloAjustado
    n: int
    consumo_total_kwh: float
    consumo_medio_kwh: float
    temperatura_media: float
    humedad_media: float
    actividad_media: float


@dataclass(frozen=True)
class DiferenciaCoeficiente:
    nombre: str
    a: float
    b: float
    ee_a: float
    ee_b: float
    diferencia: float  # b - a
    z: float
    p_valor: float


@dataclass(frozen=True)
class ComparacionPeriodos:
    tb: float
    a: ResumenPeriodo
    b: ResumenPeriodo
    conjunto: ModeloAjustado
    chow_f: float
    chow_p: float
    chow_gl: tuple[int, int]
    coeficientes: list[DiferenciaCoeficiente]
    consumo_b_esperado_kwh: float  # consumo de B predicho con el modelo de A
    ahorro_normalizado_kwh: float  # esperado - real (> 0 = ahorro)

    @property
    def aic_separados(self) -> float:
        return self.a.modelo.aic + self.b.modelo.aic

    @property
    def variacion_consumo_medio_pct(self) -> float:
        return 100 * (self.b.consumo_medio_kwh / self.a.consumo_medio_kwh - 1)

    @property
    def ahorro_normalizado_pct(self) -> float:
        return 100 * self.ahorro_normalizado_kwh / self.consumo_b_esperado_kwh

    def cambio_significativo(self, alpha: float = 0.05) -> bool:
        return self.chow_p < alpha


def _resumen(obs: Observaciones, modelo: ModeloAjustado) -> ResumenPeriodo:
    c = np.asarray(obs.consumo, dtype=float)
    return ResumenPeriodo(
        modelo=modelo,
        n=len(obs),
        consumo_total_kwh=float(c.sum()),
        consumo_medio_kwh=float(c.mean()),
        temperatura_media=float(np.mean(obs.temperatura)),
        humedad_media=float(np.mean(obs.humedad)),
        actividad_media=float(np.mean(obs.actividad)),
    )


def comparar_periodos(
    a: Observaciones,
    b: Observaciones,
    tb: float | None = None,
    rejilla_tb: Iterable[float] = range(22, 31),
) -> ComparacionPeriodos:
    if a.consumo is None or b.consumo is None:
        raise ValueError("Ambos periodos necesitan la serie de consumo")
    conjunto_obs = Observaciones.concatenar(a, b)
    if tb is None:
        conjunto, _ = seleccionar_por_aic(conjunto_obs, rejilla_tb)
        tb = conjunto.tb
    else:
        conjunto = ajustar(conjunto_obs, tb)
    ma, mb = ajustar(a, tb), ajustar(b, tb)

    k = ma.k
    gl_den = ma.n + mb.n - 2 * k
    ssr_sep = ma.ssr + mb.ssr
    chow_f = ((conjunto.ssr - ssr_sep) / k) / (ssr_sep / gl_den)
    chow_p = float(stats.f.sf(chow_f, k, gl_den))

    coeficientes = []
    for nombre, ba, bb, ea, eb in zip(NOMBRES_COEFICIENTES, ma.beta, mb.beta, ma.errores_estandar, mb.errores_estandar):
        z = (bb - ba) / np.hypot(ea, eb)
        coeficientes.append(
            DiferenciaCoeficiente(
                nombre=nombre, a=float(ba), b=float(bb), ee_a=float(ea), ee_b=float(eb),
                diferencia=float(bb - ba), z=float(z), p_valor=float(2 * stats.norm.sf(abs(z))),
            )
        )

    # Línea base: modelo de A en condiciones de B (corrección de la media log-normal).
    esperado = float(np.sum(np.exp(b.matriz(tb) @ ma.beta + ma.sigma2 / 2)))
    real_b = float(np.sum(b.consumo))
    return ComparacionPeriodos(
        tb=float(tb),
        a=_resumen(a, ma),
        b=_resumen(b, mb),
        conjunto=conjunto,
        chow_f=float(chow_f),
        chow_p=chow_p,
        chow_gl=(k, gl_den),
        coeficientes=coeficientes,
        consumo_b_esperado_kwh=esperado,
        ahorro_normalizado_kwh=esperado - real_b,
    )
