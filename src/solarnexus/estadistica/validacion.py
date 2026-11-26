"""Validación del modelo 3P: ajuste en muestra, backtest fuera de muestra y calibración.

El backtest reproduce lo que pasará en operación: el modelo se estima con los datos
anteriores a `inicio_prueba` y, para cada día de prueba, se pronostica con el
escenario climatológico construido solo con información disponible antes de ese día.
Así la calibración incluye también la incertidumbre de los regresores, no solo la
del modelo.

Calibración: la probabilidad publicada P(|e| <= delta) es fiable si, entre los
intervalos de prueba, la fracción real con |e| <= delta coincide con la probabilidad
media pronosticada. Si no coincide, se busca el factor k que escala sigma_f para que
coincidan (k > 1: el modelo era demasiado confiado).
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import brentq

from ..datos import SerieCampus
from ..oraculo import ModeloAjustado, seleccionar_por_aic
from .diagnosticos import Diagnosticos, diagnosticar, residuos
from .metricas import Metricas, calcular_metricas
from .pronostico import escenario_climatologico, prob_en_margen, pronosticar_dia

LIMITES_FIABILIDAD = (0.0, 0.5, 0.7, 0.8, 0.9, 0.95, 1.0)


@dataclass(frozen=True)
class FilaFiabilidad:
    desde: float
    hasta: float
    n: int
    prob_media: float
    frecuencia_observada: float


@dataclass(frozen=True)
class ReporteValidacion:
    modelo: ModeloAjustado
    diagnosticos: Diagnosticos
    inicio_prueba: str
    dias_prueba: int
    delta: float
    dentro_muestra: Metricas
    fuera_horario: Metricas
    fuera_diario: Metricas
    prob_media_sin_calibrar: float
    frecuencia_en_margen: float
    factor_calibracion: float
    prob_media_calibrada: float
    cobertura_95: float
    fiabilidad: list[FilaFiabilidad] = field(default_factory=list)
    inicio_entrenamiento: str | None = None

    @property
    def apto_para_despacho(self) -> bool:
        """Cumple ASHRAE 14 fuera de muestra (horario) y la calibración queda dentro de ±5 puntos."""
        return bool(self.fuera_horario.cumple_ashrae and abs(self.prob_media_calibrada - self.frecuencia_en_margen) <= 0.05)

    def a_dict(self) -> dict:
        def met(m: Metricas) -> dict:
            return {"n": m.n, "cv_rmse_pct": m.cv_rmse_pct, "nmbe_pct": m.nmbe_pct, "r2": m.r2,
                    "mape_pct": m.mape_pct, "frecuencia": m.frecuencia, "cumple_ashrae": m.cumple_ashrae}

        d = self.diagnosticos
        return {
            "modelo": {"tb": self.modelo.tb, "n": self.modelo.n, "r2": self.modelo.r2, "aic": self.modelo.aic,
                       "sigma": math.sqrt(self.modelo.sigma2)},
            "coeficientes": [c.__dict__ for c in d.coeficientes],
            "diagnosticos": {
                "durbin_watson": d.durbin_watson,
                "pruebas": [p.__dict__ for p in (d.breusch_godfrey, d.breusch_pagan, d.jarque_bera)],
                "rezagos_hac": d.rezagos_hac, "factor_duan": d.factor_duan, "avisos": d.avisos(),
            },
            "backtest": {"inicio": self.inicio_prueba, "dias": self.dias_prueba, "delta": self.delta,
                         "inicio_entrenamiento": self.inicio_entrenamiento},
            "dentro_muestra": met(self.dentro_muestra),
            "fuera_muestra_horario": met(self.fuera_horario),
            "fuera_muestra_diario": met(self.fuera_diario),
            "calibracion": {
                "prob_media_sin_calibrar": self.prob_media_sin_calibrar,
                "frecuencia_en_margen": self.frecuencia_en_margen,
                "factor_calibracion": self.factor_calibracion,
                "prob_media_calibrada": self.prob_media_calibrada,
                "cobertura_intervalo_95": self.cobertura_95,
                "fiabilidad": [f.__dict__ for f in self.fiabilidad],
            },
            "apto_para_despacho": self.apto_para_despacho,
        }


def factor_calibracion(sigma_f: np.ndarray, aciertos: np.ndarray, delta: float) -> float:
    """k tal que mean(erf(delta / (k·sigma_f·√2))) = fracción observada con |e| <= delta."""
    objetivo = float(np.mean(aciertos))
    # Con 0 % o 100 % de aciertos no hay solución finita: se acota.
    objetivo = min(max(objetivo, 0.005), 0.995)
    f = lambda k: float(np.mean(prob_en_margen(sigma_f, delta, k))) - objetivo  # noqa: E731
    return float(brentq(f, 1e-3, 1e3))


def tabla_fiabilidad(prob: np.ndarray, aciertos: np.ndarray, limites: Iterable[float] = LIMITES_FIABILIDAD) -> list[FilaFiabilidad]:
    limites = list(limites)
    filas = []
    for i, (a, b) in enumerate(zip(limites, limites[1:])):
        m = (prob >= a) & ((prob < b) if i < len(limites) - 2 else (prob <= b))
        if m.any():
            filas.append(FilaFiabilidad(a, b, int(m.sum()), float(prob[m].mean()), float(aciertos[m].mean())))
    return filas


def validar(
    serie: SerieCampus,
    inicio_prueba: str,
    dias_prueba: int = 28,
    rejilla_tb: Iterable[float] = range(22, 31),
    delta: float = 0.10,
    dias_escenario: int = 28,
    inicio_entrenamiento: str | None = None,
) -> ReporteValidacion:
    """`inicio_entrenamiento` permite descartar datos anteriores a un quiebre estructural
    (p. ej. la entrada de Copérnico) para que la línea base represente el régimen actual."""
    entrenamiento = serie.antes_de(inicio_prueba)
    if inicio_entrenamiento is not None:
        d = entrenamiento.fechas.astype("datetime64[D]")
        entrenamiento = entrenamiento.filtrar(d >= np.datetime64(inicio_entrenamiento, "D"))
    if len(entrenamiento) < 24 * 14:
        raise ValueError("Hacen falta al menos 14 días de datos antes del inicio de la prueba")
    modelo, _ = seleccionar_por_aic(entrenamiento.observaciones, rejilla_tb)
    diag = diagnosticar(modelo, entrenamiento.observaciones)

    x, e = residuos(modelo, entrenamiento.observaciones)
    real_in = np.asarray(entrenamiento.observaciones.consumo, dtype=float)
    dentro = calcular_metricas(real_in, np.exp(x @ modelo.beta) * diag.factor_duan, p=modelo.k)

    inicio = np.datetime64(inicio_prueba, "D")
    reales, estimados, e_ln, sigmas, reales_dia, estimados_dia = [], [], [], [], [], []
    for i in range(dias_prueba):
        fecha = str(inicio + np.timedelta64(i, "D"))
        dia = serie.entre(fecha, fecha)
        if len(dia) != 24:
            continue
        esc = escenario_climatologico(serie, fecha, dias=dias_escenario)
        pron = pronosticar_dia(modelo, esc, delta=delta, factor_duan=diag.factor_duan)
        c = np.asarray(dia.observaciones.consumo, dtype=float)
        reales.append(c)
        estimados.append(pron.demanda_kwh)
        e_ln.append(np.log(c) - pron.ln_demanda)
        sigmas.append(pron.sigma_f)
        reales_dia.append(c.sum())
        estimados_dia.append(pron.demanda_kwh.sum())
    if len(reales) < 2:
        raise ValueError("El periodo de prueba no tiene al menos 2 días completos de datos")

    real, est = np.concatenate(reales), np.concatenate(estimados)
    e_ln, sigma = np.concatenate(e_ln), np.concatenate(sigmas)
    aciertos = (np.abs(e_ln) <= delta).astype(float)
    p_sin = prob_en_margen(sigma, delta)
    k = factor_calibracion(sigma, aciertos, delta)
    p_cal = prob_en_margen(sigma, delta, k)
    cobertura_95 = float(np.mean(np.abs(e_ln) <= 1.959964 * k * sigma))

    return ReporteValidacion(
        modelo=modelo,
        diagnosticos=diag,
        inicio_prueba=inicio_prueba,
        dias_prueba=len(reales),
        delta=delta,
        dentro_muestra=dentro,
        fuera_horario=calcular_metricas(real, est),
        fuera_diario=calcular_metricas(np.array(reales_dia), np.array(estimados_dia), frecuencia="diario"),
        prob_media_sin_calibrar=float(p_sin.mean()),
        frecuencia_en_margen=float(aciertos.mean()),
        factor_calibracion=k,
        prob_media_calibrada=float(p_cal.mean()),
        cobertura_95=cobertura_95,
        fiabilidad=tabla_fiabilidad(p_cal, aciertos),
        inicio_entrenamiento=inicio_entrenamiento,
    )
