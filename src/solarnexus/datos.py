"""Generador de datos SINTÉTICOS horarios del campus.

No son mediciones reales: sirven para probar el pipeline de punta a punta mientras
llegan los datos de la estación Copérnico, el registro académico y Solar Jaguar.
El consumo se genera con el propio modelo 3P y coeficientes conocidos, de modo que
las pruebas pueden comprobar que la estimación los recupera.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .oraculo import Observaciones, cdd

# Coeficientes "verdaderos" del generador (b0, b1_cdd, b2_hum, b3_ln_act, b4_ln_area).
BETA_VERDADERO = np.array([2.0, 0.08, 0.3, 0.25, 0.35])
TB_VERDADERA = 27.0
SIGMA_VERDADERA = 0.04
PV_PICO_KWH = 600.0  # producción horaria máxima supuesta de Solar Jaguar


@dataclass(frozen=True)
class SerieCampus:
    horas: np.ndarray          # hora del día 0..23
    dia_semana: np.ndarray     # 0 = lunes … 6 = domingo
    observaciones: Observaciones
    pv: np.ndarray             # kWh por hora

    def tramo(self, inicio: int, fin: int) -> SerieCampus:
        o = self.observaciones
        return SerieCampus(
            horas=self.horas[inicio:fin],
            dia_semana=self.dia_semana[inicio:fin],
            observaciones=Observaciones(
                temperatura=o.temperatura[inicio:fin],
                humedad=o.humedad[inicio:fin],
                actividad=o.actividad[inicio:fin],
                area=o.area[inicio:fin],
                consumo=None if o.consumo is None else o.consumo[inicio:fin],
            ),
            pv=self.pv[inicio:fin],
        )

    def dia(self, indice: int) -> SerieCampus:
        return self.tramo(24 * indice, 24 * (indice + 1))


def generar(dias: int, semilla: int = 0, dia_semana_inicial: int = 0) -> SerieCampus:
    """Genera `dias` días horarios con clima de Managua, calendario académico y PV."""
    rng = np.random.default_rng(semilla)
    n = 24 * dias
    t = np.arange(n)
    horas = t % 24
    dia_semana = (t // 24 + dia_semana_inicial) % 7
    laborable = dia_semana < 5

    # Temperatura: mínima ~24 °C de madrugada, máxima ~34 °C hacia las 15 h.
    temperatura = 29 + 5 * np.sin(2 * np.pi * (horas - 9) / 24) + rng.normal(0, 0.8, n)
    humedad = np.clip(0.75 - 0.012 * (temperatura - 29) + rng.normal(0, 0.03, n), 0.3, 0.98)

    en_clase = laborable & (horas >= 7) & (horas < 21)
    actividad = np.where(en_clase, rng.uniform(0.6, 1.0, n), rng.uniform(0.04, 0.08, n))
    area = 2000 + 8000 * actividad * rng.uniform(0.85, 1.15, n)

    nubosidad = rng.uniform(0.75, 1.0, dias).repeat(24)
    pv = PV_PICO_KWH * np.maximum(np.sin(np.pi * (horas - 6) / 12), 0) * nubosidad

    x = np.column_stack(
        [np.ones(n), cdd(temperatura, TB_VERDADERA), humedad, np.log(actividad), np.log(area)]
    )
    consumo = np.exp(x @ BETA_VERDADERO + rng.normal(0, SIGMA_VERDADERA, n))

    return SerieCampus(
        horas=horas,
        dia_semana=dia_semana,
        observaciones=Observaciones(temperatura, humedad, actividad, area, consumo),
        pv=pv,
    )
