"""Métricas de ajuste y criterios de aceptación de ASHRAE Guideline 14.

    CV(RMSE) = sqrt( Σ (y - ŷ)² / (n - p) ) / ȳ
    NMBE     = Σ (y - ŷ) / ((n - p) · ȳ)

Con datos horarios el modelo se acepta si CV(RMSE) <= 30 % y |NMBE| <= 10 %;
con datos mensuales, 15 % y 5 %.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

CRITERIOS_ASHRAE = {
    "horario": {"cv_rmse": 30.0, "nmbe": 10.0},
    "diario": {"cv_rmse": 25.0, "nmbe": 10.0},  # interpolación habitual; Guideline 14 fija horario y mensual
    "mensual": {"cv_rmse": 15.0, "nmbe": 5.0},
}


@dataclass(frozen=True)
class Metricas:
    n: int
    cv_rmse_pct: float
    nmbe_pct: float
    r2: float
    mape_pct: float
    frecuencia: str

    @property
    def cumple_ashrae(self) -> bool:
        c = CRITERIOS_ASHRAE[self.frecuencia]
        return bool(self.cv_rmse_pct <= c["cv_rmse"] and abs(self.nmbe_pct) <= c["nmbe"])


def calcular_metricas(real: np.ndarray, estimado: np.ndarray, p: int = 0, frecuencia: str = "horario") -> Metricas:
    """Métricas en kWh. `p` = parámetros estimados (0 para validación fuera de muestra)."""
    if frecuencia not in CRITERIOS_ASHRAE:
        raise ValueError(f"Frecuencia desconocida: {frecuencia}")
    y = np.asarray(real, dtype=float)
    yhat = np.asarray(estimado, dtype=float)
    if y.shape != yhat.shape or y.size == 0:
        raise ValueError("Las series real y estimada deben tener la misma longitud (> 0)")
    n = y.size
    if n <= p:
        raise ValueError("Hacen falta más observaciones que parámetros")
    e = y - yhat
    media = float(y.mean())
    sst = float(((y - media) ** 2).sum())
    return Metricas(
        n=n,
        cv_rmse_pct=100 * float(np.sqrt((e @ e) / (n - p))) / media,
        nmbe_pct=100 * float(e.sum()) / ((n - p) * media),
        r2=1 - float(e @ e) / sst if sst > 0 else float("nan"),
        mape_pct=100 * float(np.mean(np.abs(e) / np.abs(y))),
        frecuencia=frecuencia,
    )
