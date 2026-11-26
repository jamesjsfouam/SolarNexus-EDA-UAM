"""Controlador de despacho predictivo (intervalos de 1 hora, energía en kWh).

Reglas (README, sección 2):
  1. Carga: si se pronostica un pico vespertino mayor que la PV, o el pronóstico
     no es lo bastante fiable, se bloquea la exportación y el excedente va a la batería.
  2. Peak shaving: dentro de la ventana pico se descarga la batería para no comprar G_t.
  3. Exportación: sin pico previsto y con P(|e| <= delta) >= 1 - alpha se puentea la
     batería y el excedente sale al SIN.
Fuera de esas situaciones el campus consume en autoconsumo e importa el déficit.

Si la batería está llena o al límite de potencia durante la carga, el excedente que
no cabe se exporta (exportación residual) en lugar de desperdiciarse.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from .balance import FlujosEnergia
from .config import Parametros


class Regimen(str, Enum):
    CARGA = "carga"
    PEAK_SHAVING = "peak_shaving"
    EXPORTACION = "exportacion"
    AUTOCONSUMO = "autoconsumo"


@dataclass
class Bateria:
    capacidad_kwh: float
    potencia_max_kw: float
    soc_kwh: float = 0.0
    soc_min_kwh: float = 0.0
    eficiencia_carga: float = 0.95  # fracción de la energía de entrada que se almacena

    def __post_init__(self) -> None:
        if not 0 <= self.soc_min_kwh <= self.soc_kwh <= self.capacidad_kwh:
            raise ValueError("Debe cumplirse 0 <= soc_min <= soc <= capacidad")
        if not 0 < self.eficiencia_carga <= 1:
            raise ValueError("La eficiencia de carga debe estar en (0, 1]")

    @property
    def max_carga(self) -> float:
        """Energía máxima que se puede tomar de la red interna en 1 h."""
        return min(self.potencia_max_kw, (self.capacidad_kwh - self.soc_kwh) / self.eficiencia_carga)

    @property
    def max_descarga(self) -> float:
        return min(self.potencia_max_kw, self.soc_kwh - self.soc_min_kwh)

    def cargar(self, energia: float) -> float:
        energia = max(0.0, min(energia, self.max_carga))
        self.soc_kwh = min(self.capacidad_kwh, self.soc_kwh + energia * self.eficiencia_carga)
        return energia

    def descargar(self, energia: float) -> float:
        energia = max(0.0, min(energia, self.max_descarga))
        self.soc_kwh -= energia
        return energia


@dataclass(frozen=True)
class DecisionDespacho:
    hora: int
    regimen: Regimen
    flujos: FlujosEnergia
    soc_final_kwh: float
    prob_en_margen: float


class ControladorDespacho:
    def __init__(self, bateria: Bateria, parametros: Parametros | None = None) -> None:
        self.bateria = bateria
        self.p = parametros or Parametros()

    def pico_previsto(self, horas: Sequence[int], consumo: Sequence[float], pv: Sequence[float]) -> bool:
        """¿Algún intervalo de la ventana pico tiene demanda mayor que la PV pronosticada?"""
        return any(self.p.en_pico(h) and c > g for h, c, g in zip(horas, consumo, pv))

    def planificar(
        self,
        horas: Sequence[int],
        consumo: Sequence[float],
        pv: Sequence[float],
        prob_en_margen: Sequence[float],
    ) -> list[DecisionDespacho]:
        """Plan de despacho para el horizonte dado (normalmente 24 h). Modifica el SOC de la batería."""
        if not (len(horas) == len(consumo) == len(pv) == len(prob_en_margen)):
            raise ValueError("Las series del horizonte deben tener la misma longitud")
        hay_pico = self.pico_previsto(horas, consumo, pv)
        plan = []
        for h, c, g, prob in zip(horas, consumo, pv, prob_en_margen):
            plan.append(self._decidir(int(h), float(c), float(g), float(prob), hay_pico))
        return plan

    def _decidir(self, hora: int, c: float, pv: float, prob: float, hay_pico: bool) -> DecisionDespacho:
        red = b_carga = b_descarga = exportacion = 0.0
        deficit = max(c - pv, 0.0)
        excedente = max(pv - c, 0.0)
        exportacion_autorizada = not hay_pico and prob >= self.p.confianza

        if deficit > 0:
            if hay_pico and self.p.en_pico(hora) and self.bateria.max_descarga > 0:
                regimen = Regimen.PEAK_SHAVING
                b_descarga = self.bateria.descargar(deficit)
            else:
                regimen = Regimen.AUTOCONSUMO
            red = deficit - b_descarga
        elif excedente > 0:
            if exportacion_autorizada:
                regimen = Regimen.EXPORTACION
                exportacion = excedente
            else:
                regimen = Regimen.CARGA
                b_carga = self.bateria.cargar(excedente)
                exportacion = excedente - b_carga  # residual: batería llena o al límite
        else:
            regimen = Regimen.AUTOCONSUMO

        flujos = FlujosEnergia(
            consumo=c, red=red, pv=pv, b_carga=b_carga, b_descarga=b_descarga, exportacion=exportacion
        )
        assert flujos.cuadra(), f"Balance roto en la hora {hora}: residuo {flujos.residuo}"
        return DecisionDespacho(hora, regimen, flujos, self.bateria.soc_kwh, prob)
