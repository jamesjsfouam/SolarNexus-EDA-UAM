"""Motor econométrico 3P (ASHRAE) en forma log-lineal.

    ln C_{t+1} = b0 + b1·CDD_{t+1}(Tb) + b2·HUM_{t+1} + b3·ln ACT_{t+1} + b4·ln AREA_{t+1} + e

Se estima por MCO, se elige la temperatura base Tb con el menor AIC y cada
pronóstico lleva su error estándar y la probabilidad de caer dentro del margen
admisible delta:  P(|ln C - ln Ĉ| <= delta) = P(|Z| <= delta / sigma_f).
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np

NOMBRES_COEFICIENTES = ("b0", "b1_cdd", "b2_hum", "b3_ln_act", "b4_ln_area")


def cdd(temperatura: np.ndarray | float, tb: float) -> np.ndarray:
    """Grados de enfriamiento respecto a la temperatura base: max(T - Tb, 0)."""
    return np.maximum(np.asarray(temperatura, dtype=float) - tb, 0.0)


@dataclass(frozen=True)
class Observaciones:
    """Serie de observaciones (históricas o pronosticadas) de los regresores.

    temperatura en °C, humedad relativa en fracción [0, 1], actividad académica
    en (0, 1], área climatizada activa en m² (> 0). consumo en kWh (opcional
    cuando se usa para pronosticar).
    """

    temperatura: np.ndarray
    humedad: np.ndarray
    actividad: np.ndarray
    area: np.ndarray
    consumo: np.ndarray | None = None

    def __post_init__(self) -> None:
        campos = {
            "temperatura": self.temperatura,
            "humedad": self.humedad,
            "actividad": self.actividad,
            "area": self.area,
        }
        if self.consumo is not None:
            campos["consumo"] = self.consumo
        n = {len(np.atleast_1d(v)) for v in campos.values()}
        if len(n) != 1:
            raise ValueError(f"Las series tienen longitudes distintas: {n}")
        for nombre in ("actividad", "area") + (("consumo",) if self.consumo is not None else ()):
            if np.any(np.asarray(campos[nombre]) <= 0):
                raise ValueError(f"{nombre} debe ser > 0 (entra en logaritmo)")

    def __len__(self) -> int:
        return len(np.atleast_1d(self.temperatura))

    def matriz(self, tb: float) -> np.ndarray:
        """Matriz de diseño X con constante."""
        return np.column_stack(
            [
                np.ones(len(self)),
                cdd(self.temperatura, tb),
                np.asarray(self.humedad, dtype=float),
                np.log(np.asarray(self.actividad, dtype=float)),
                np.log(np.asarray(self.area, dtype=float)),
            ]
        )


@dataclass(frozen=True)
class Pronostico:
    ln_consumo: np.ndarray
    sigma_f: np.ndarray  # error estándar del pronóstico en escala log

    @property
    def consumo(self) -> np.ndarray:
        """Pronóstico puntual en kWh (mediana de la log-normal)."""
        return np.exp(self.ln_consumo)

    def prob_en_margen(self, delta: float) -> np.ndarray:
        """P(|Z| <= delta/sigma_f) = erf(delta / (sigma_f·√2))."""
        z = delta / (self.sigma_f * math.sqrt(2.0))
        return np.vectorize(math.erf)(z)

    def intervalo(self, alpha: float = 0.05) -> tuple[np.ndarray, np.ndarray]:
        """Intervalo de confianza (1 - alpha) en kWh, aproximación normal."""
        from scipy.stats import norm

        z = norm.ppf(1 - alpha / 2)
        return np.exp(self.ln_consumo - z * self.sigma_f), np.exp(self.ln_consumo + z * self.sigma_f)


@dataclass(frozen=True)
class ModeloAjustado:
    tb: float
    beta: np.ndarray
    sigma2: float          # varianza de los residuos (insesgada)
    log_verosimilitud: float
    n: int
    xtx_inv: np.ndarray
    r2: float

    @property
    def k(self) -> int:
        return len(self.beta)

    @property
    def aic(self) -> float:
        """AIC = 2k - 2·ln L."""
        return 2 * self.k - 2 * self.log_verosimilitud

    @property
    def aic_eviews(self) -> float:
        """Versión normalizada que reporta EViews: (-2ℓ + 2k) / T."""
        return (-2 * self.log_verosimilitud + 2 * self.k) / self.n

    def coeficientes(self) -> dict[str, float]:
        return dict(zip(NOMBRES_COEFICIENTES, (float(b) for b in self.beta)))

    def pronosticar(self, obs: Observaciones) -> Pronostico:
        x = obs.matriz(self.tb)
        ln_c = x @ self.beta
        # Var(error de pronóstico) = sigma² (1 + x' (X'X)^-1 x)
        apalancamiento = np.einsum("ij,jk,ik->i", x, self.xtx_inv, x)
        sigma_f = np.sqrt(self.sigma2 * (1.0 + apalancamiento))
        return Pronostico(ln_consumo=ln_c, sigma_f=sigma_f)


def ajustar(obs: Observaciones, tb: float) -> ModeloAjustado:
    """Estima el modelo 3P log-lineal por MCO para una Tb dada."""
    if obs.consumo is None:
        raise ValueError("Se necesita la serie de consumo para estimar el modelo")
    x = obs.matriz(tb)
    y = np.log(np.asarray(obs.consumo, dtype=float))
    n, k = x.shape
    if n <= k:
        raise ValueError(f"Hacen falta más de {k} observaciones (hay {n})")
    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    residuos = y - x @ beta
    ssr = float(residuos @ residuos)
    sst = float(((y - y.mean()) ** 2).sum())
    # Log-verosimilitud gaussiana concentrada (la misma que usa EViews).
    log_l = -n / 2 * (1 + math.log(2 * math.pi) + math.log(ssr / n))
    return ModeloAjustado(
        tb=tb,
        beta=beta,
        sigma2=ssr / (n - k),
        log_verosimilitud=log_l,
        n=n,
        xtx_inv=np.linalg.pinv(x.T @ x),
        r2=1 - ssr / sst if sst > 0 else float("nan"),
    )


def seleccionar_por_aic(obs: Observaciones, rejilla_tb: Iterable[float]) -> tuple[ModeloAjustado, list[ModeloAjustado]]:
    """Ajusta el modelo para cada Tb y devuelve (mejor por AIC, todos los candidatos)."""
    candidatos = [ajustar(obs, float(tb)) for tb in rejilla_tb]
    if not candidatos:
        raise ValueError("La rejilla de temperaturas base está vacía")
    return min(candidatos, key=lambda m: m.aic), candidatos
