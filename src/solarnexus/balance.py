"""Ecuaciones de balance energético del campus (unidades: kWh por intervalo).

Base:      C_t = G_t + PV_t - X_t
Extendida: C_t = G_t + PV_t + B_descarga,t - B_carga,t - X_t
"""

from __future__ import annotations

from dataclasses import dataclass

TOLERANCIA = 1e-6


def consumo_base(g: float, pv: float, x: float) -> float:
    return g + pv - x


def consumo_extendido(g: float, pv: float, b_descarga: float, b_carga: float, x: float) -> float:
    return g + pv + b_descarga - b_carga - x


@dataclass(frozen=True)
class FlujosEnergia:
    """Flujos de un intervalo t. Todos deben ser >= 0."""

    consumo: float      # C_t
    red: float          # G_t   importación desde el SIN
    pv: float           # PV_t  generación Solar Jaguar
    b_carga: float      # B_carga,t
    b_descarga: float   # B_descarga,t
    exportacion: float  # X_t

    def __post_init__(self) -> None:
        for nombre in ("consumo", "red", "pv", "b_carga", "b_descarga", "exportacion"):
            if getattr(self, nombre) < -TOLERANCIA:
                raise ValueError(f"{nombre} no puede ser negativo: {getattr(self, nombre)}")
        if self.b_carga > TOLERANCIA and self.b_descarga > TOLERANCIA:
            raise ValueError("La batería no puede cargar y descargar en el mismo intervalo")

    @property
    def residuo(self) -> float:
        """Diferencia entre el consumo y el lado derecho de la ecuación extendida."""
        return self.consumo - consumo_extendido(
            self.red, self.pv, self.b_descarga, self.b_carga, self.exportacion
        )

    def cuadra(self, tolerancia: float = TOLERANCIA) -> bool:
        return abs(self.residuo) <= tolerancia
