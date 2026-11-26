"""Parámetros operativos del sistema. Todos los valores son supuestos de partida
y deben calibrarse con los datos reales del campus."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Parametros:
    # Ventana del pico vespertino [inicio, fin) en horas locales.
    hora_pico_inicio: int = 14
    hora_pico_fin: int = 17
    # Compuerta de riesgo: solo se exporta si P(|error| <= delta) >= 1 - alpha.
    alpha: float = 0.05
    # Margen de error admisible sobre ln C (0.10 ~ ±10 % de consumo).
    delta: float = 0.10
    # Rejilla de temperaturas base (°C) evaluadas por AIC.
    rejilla_tb: tuple[float, ...] = field(default_factory=lambda: tuple(float(t) for t in range(22, 31)))

    def en_pico(self, hora: int) -> bool:
        return self.hora_pico_inicio <= hora % 24 < self.hora_pico_fin

    @property
    def confianza(self) -> float:
        return 1.0 - self.alpha
