"""Datos horarios del campus: generador SINTÉTICO y carga/exportación en CSV.

El generador no produce mediciones reales: sirve para probar el pipeline mientras
llegan los datos de la estación Copérnico, el registro académico y Solar Jaguar.
El consumo se genera con el propio modelo 3P y coeficientes conocidos, de modo que
las pruebas pueden comprobar que la estimación los recupera.

Formato CSV (una fila por hora, cabecera obligatoria):
    fecha,temperatura,humedad,actividad,area,consumo,pv
    2026-01-05T00:00,24.8,0.81,0.05,2410,72.3,0
- fecha: ISO 8601 (hora local). temperatura en °C. humedad en fracción (o en %, se
  convierte si algún valor supera 1). actividad en (0, 1]. area en m². consumo y pv en kWh.
- pv es opcional (se toma 0 si falta).
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass

import numpy as np

from .oraculo import Observaciones, cdd

# Coeficientes "verdaderos" del generador (b0, b1_cdd, b2_hum, b3_ln_act, b4_ln_area).
BETA_VERDADERO = np.array([2.0, 0.08, 0.3, 0.25, 0.35])
TB_VERDADERA = 27.0
SIGMA_VERDADERA = 0.04
PV_PICO_KWH = 600.0  # producción horaria máxima supuesta de Solar Jaguar
FECHA_INICIAL = "2026-01-05"  # lunes

COLUMNAS = ("fecha", "temperatura", "humedad", "actividad", "area", "consumo", "pv")


@dataclass(frozen=True)
class SerieCampus:
    fechas: np.ndarray         # datetime64[h]
    observaciones: Observaciones
    pv: np.ndarray             # kWh por hora

    @property
    def horas(self) -> np.ndarray:
        return (self.fechas - self.fechas.astype("datetime64[D]")).astype(int)

    @property
    def dia_semana(self) -> np.ndarray:
        """0 = lunes … 6 = domingo."""
        return (self.fechas.astype("datetime64[D]").astype(int) + 3) % 7

    def __len__(self) -> int:
        return len(self.fechas)

    def filtrar(self, mascara: np.ndarray) -> SerieCampus:
        return SerieCampus(self.fechas[mascara], self.observaciones.filtrar(mascara), self.pv[mascara])

    def tramo(self, inicio: int, fin: int) -> SerieCampus:
        m = np.zeros(len(self), dtype=bool)
        m[inicio:fin] = True
        return self.filtrar(m)

    def dia(self, indice: int) -> SerieCampus:
        return self.tramo(24 * indice, 24 * (indice + 1))

    def entre(self, inicio: str, fin: str) -> SerieCampus:
        """Horas desde el día `inicio` hasta el día `fin`, ambos incluidos (YYYY-MM-DD)."""
        d = self.fechas.astype("datetime64[D]")
        return self.filtrar((d >= np.datetime64(inicio, "D")) & (d <= np.datetime64(fin, "D")))

    def antes_de(self, fecha: str) -> SerieCampus:
        return self.filtrar(self.fechas.astype("datetime64[D]") < np.datetime64(fecha, "D"))

    def consumo_diario(self) -> tuple[np.ndarray, np.ndarray]:
        """(días, consumo total kWh por día)."""
        dias = self.fechas.astype("datetime64[D]")
        unicos, inv = np.unique(dias, return_inverse=True)
        return unicos, np.bincount(inv, weights=np.asarray(self.observaciones.consumo, dtype=float))


def _en_rangos(dias: np.ndarray, rangos: tuple[tuple[str, str], ...]) -> np.ndarray:
    m = np.zeros(len(dias), dtype=bool)
    for ini, fin in rangos:
        m |= (dias >= np.datetime64(ini, "D")) & (dias <= np.datetime64(fin, "D"))
    return m


def generar(
    dias: int,
    semilla: int = 0,
    fecha_inicial: str = FECHA_INICIAL,
    vacaciones: tuple[tuple[str, str], ...] = (),
    mejora_eficiencia: tuple[str, float] | None = None,
) -> SerieCampus:
    """Genera `dias` días horarios con clima de Managua, calendario académico y PV.

    vacaciones: rangos de fechas (inclusive) sin clases aunque sean días laborables.
    mejora_eficiencia: (fecha, reducción) resta `reducción` a ln C desde esa fecha,
    simulando p. ej. un cambio de equipos de climatización (0.08 ≈ 8 % menos consumo).
    """
    rng = np.random.default_rng(semilla)
    n = 24 * dias
    fechas = np.datetime64(fecha_inicial, "h") + np.arange(n).astype("timedelta64[h]")
    dias_cal = fechas.astype("datetime64[D]")
    horas = np.arange(n) % 24
    dia_semana = (dias_cal.astype(int) + 3) % 7
    laborable = (dia_semana < 5) & ~_en_rangos(dias_cal, vacaciones)

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
    ln_c = x @ BETA_VERDADERO + rng.normal(0, SIGMA_VERDADERA, n)
    if mejora_eficiencia is not None:
        fecha, reduccion = mejora_eficiencia
        ln_c = ln_c - reduccion * (dias_cal >= np.datetime64(fecha, "D"))

    return SerieCampus(
        fechas=fechas,
        observaciones=Observaciones(temperatura, humedad, actividad, area, np.exp(ln_c)),
        pv=pv,
    )


def generar_anio_demo(semilla: int = 3) -> SerieCampus:
    """Un año académico sintético con vacaciones y una mejora de eficiencia el 1 de agosto."""
    return generar(
        364,
        semilla=semilla,
        vacaciones=(("2026-03-30", "2026-04-05"), ("2026-06-29", "2026-07-19"), ("2026-12-14", "2027-01-03")),
        mejora_eficiencia=("2026-08-01", 0.08),
    )


def cargar_csv(texto: str) -> SerieCampus:
    lector = csv.DictReader(io.StringIO(texto.lstrip("﻿")))
    if lector.fieldnames is None:
        raise ValueError("El CSV está vacío")
    cabecera = {c.strip().lower() for c in lector.fieldnames}
    faltan = [c for c in COLUMNAS if c != "pv" and c not in cabecera]
    if faltan:
        raise ValueError(f"Faltan columnas en el CSV: {', '.join(faltan)}")

    filas = [{k.strip().lower(): (v or "").strip() for k, v in fila.items() if k} for fila in lector]
    if len(filas) < 24:
        raise ValueError("El CSV necesita al menos 24 filas horarias")
    try:
        fechas = np.array([np.datetime64(f["fecha"].replace(" ", "T"), "h") for f in filas])
        col = {c: np.array([float(f[c]) for f in filas]) for c in COLUMNAS[1:6]}
        pv = np.array([float(f.get("pv") or 0) for f in filas])
    except (KeyError, ValueError) as e:
        raise ValueError(f"Valor no válido en el CSV: {e}") from e

    orden = np.argsort(fechas, kind="stable")
    if np.any(np.diff(fechas[orden]) == np.timedelta64(0, "h")):
        raise ValueError("Hay fechas repetidas en el CSV")
    if np.nanmax(col["humedad"]) > 1:
        col["humedad"] = col["humedad"] / 100
    return SerieCampus(
        fechas=fechas[orden],
        observaciones=Observaciones(
            col["temperatura"][orden], col["humedad"][orden], col["actividad"][orden],
            col["area"][orden], col["consumo"][orden],
        ),
        pv=pv[orden],
    )


def a_csv(serie: SerieCampus) -> str:
    o = serie.observaciones
    salida = io.StringIO()
    w = csv.writer(salida, lineterminator="\n")
    w.writerow(COLUMNAS)
    for i in range(len(serie)):
        w.writerow([
            str(serie.fechas[i]), f"{o.temperatura[i]:.2f}", f"{o.humedad[i]:.3f}", f"{o.actividad[i]:.3f}",
            f"{o.area[i]:.1f}", f"{o.consumo[i]:.2f}", f"{serie.pv[i]:.2f}",
        ])
    return salida.getvalue()
