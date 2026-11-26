"""Pronóstico de 24 h y conversión al contrato de POST /api/v1/forecasts.

Para pronosticar el día D hacen falta los regresores de D (clima, actividad, área) y
la PV esperada. Mientras no haya pronóstico meteorológico ni calendario académico
conectados, se usa un **escenario climatológico**: para cada hora, el promedio de esa
hora en los últimos `dias` días del mismo tipo (laborable o fin de semana) anteriores
a D. Se pueden sustituir la actividad (calendario) o el clima (pronóstico) cuando existan.

La demanda se devuelve como media en kWh: exp(ln Ĉ) · factor de Duan (smearing).
La probabilidad en el margen usa el error estándar del pronóstico multiplicado por un
factor de calibración k estimado en el backtest (validacion.py):

    P(|ln C - ln Ĉ| <= delta) = erf( delta / (k · sigma_f · √2) )
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import timedelta, timezone

import numpy as np

from ..datos import SerieCampus
from ..oraculo import ModeloAjustado, Observaciones

# Nicaragua no aplica horario de verano: UTC-6 todo el año.
ZONA_MANAGUA = timezone(timedelta(hours=-6), "America/Managua")
MAX_PUNTOS_CONTRATO = 168


@dataclass(frozen=True)
class Escenario:
    fecha: str
    horas: np.ndarray
    observaciones: Observaciones  # sin consumo
    pv: np.ndarray
    dias_usados: int


@dataclass(frozen=True)
class PronosticoDia:
    fecha: str
    horas: np.ndarray
    demanda_kwh: np.ndarray
    ln_demanda: np.ndarray
    sigma_f: np.ndarray
    probabilidad_en_margen: np.ndarray
    pv_kwh: np.ndarray
    delta: float
    factor_calibracion: float


def _es_laborable(fechas) -> np.ndarray:
    """Lunes a viernes (vectorizado; el 1970-01-01 fue jueves)."""
    return (np.asarray(fechas, dtype="datetime64[D]").astype(np.int64) + 3) % 7 < 5


def escenario_climatologico(
    historico: SerieCampus,
    fecha: str,
    dias: int = 28,
    actividad: np.ndarray | None = None,
    temperatura: np.ndarray | None = None,
    humedad: np.ndarray | None = None,
) -> Escenario:
    """Regresores esperados del día `fecha` a partir de los `dias` días previos del mismo tipo."""
    objetivo = np.datetime64(fecha, "D")
    previo = historico.antes_de(fecha)
    dias_serie = previo.fechas.astype("datetime64[D]")
    mismo_tipo = _es_laborable(dias_serie) == _es_laborable(objetivo)
    candidatos = np.unique(dias_serie[mismo_tipo])[-dias:]
    if len(candidatos) == 0:
        raise ValueError(f"No hay días del mismo tipo antes de {fecha} para construir el escenario")
    sel = previo.filtrar(np.isin(dias_serie, candidatos))
    horas = sel.horas
    o = sel.observaciones

    def perfil(valores) -> np.ndarray:
        v = np.asarray(valores, dtype=float)
        suma = np.bincount(horas, weights=v, minlength=24)
        cuenta = np.bincount(horas, minlength=24)
        if np.any(cuenta == 0):
            raise ValueError("El historial no cubre las 24 horas del día")
        return suma / cuenta

    def sustituir(nombre, propio, defecto):
        if propio is None:
            return defecto
        propio = np.asarray(propio, dtype=float)
        if propio.shape != (24,):
            raise ValueError(f"{nombre} debe tener 24 valores horarios")
        return propio

    obs = Observaciones(
        temperatura=sustituir("temperatura", temperatura, perfil(o.temperatura)),
        humedad=sustituir("humedad", humedad, perfil(o.humedad)),
        # media geométrica: el modelo usa ln ACT y ln AREA
        actividad=sustituir("actividad", actividad, np.exp(perfil(np.log(o.actividad)))),
        area=np.exp(perfil(np.log(o.area))),
    )
    return Escenario(fecha=fecha, horas=np.arange(24), observaciones=obs, pv=perfil(sel.pv), dias_usados=len(candidatos))


def prob_en_margen(sigma_f: np.ndarray, delta: float, factor_calibracion: float = 1.0) -> np.ndarray:
    z = delta / (factor_calibracion * np.asarray(sigma_f, dtype=float) * math.sqrt(2))
    return np.vectorize(math.erf)(z)


def pronosticar_dia(
    modelo: ModeloAjustado,
    escenario: Escenario,
    delta: float = 0.10,
    factor_calibracion: float = 1.0,
    factor_duan: float | None = None,
) -> PronosticoDia:
    p = modelo.pronosticar(escenario.observaciones)
    duan = factor_duan if factor_duan is not None else math.exp(modelo.sigma2 / 2)
    return PronosticoDia(
        fecha=escenario.fecha,
        horas=escenario.horas,
        demanda_kwh=np.exp(p.ln_consumo) * duan,
        ln_demanda=p.ln_consumo,
        sigma_f=p.sigma_f,
        probabilidad_en_margen=prob_en_margen(p.sigma_f, delta, factor_calibracion),
        pv_kwh=np.maximum(escenario.pv, 0.0),
        delta=delta,
        factor_calibracion=factor_calibracion,
    )


def a_contrato(
    pronosticos: list[PronosticoDia],
    model_name: str = "ASHRAE-3P-log-linear",
    model_version: str = "0.1.0",
    notes: str | None = None,
) -> dict:
    """Cuerpo JSON para POST /api/v1/forecasts (1–168 intervalos horarios, ordenados y con zona horaria)."""
    puntos = []
    for pron in sorted(pronosticos, key=lambda x: x.fecha):
        base = np.datetime64(pron.fecha, "h")
        for h, d, g, pr in zip(pron.horas, pron.demanda_kwh, pron.pv_kwh, pron.probabilidad_en_margen):
            local = (base + np.timedelta64(int(h), "h")).astype(object).replace(tzinfo=ZONA_MANAGUA)
            puntos.append({
                "interval_start": local.isoformat(),
                "demand_kwh": round(float(d), 3),
                "pv_generation_kwh": round(float(g), 3),
                "probability_within_margin": round(min(max(float(pr), 0.0), 1.0), 4),
            })
    if not 1 <= len(puntos) <= MAX_PUNTOS_CONTRATO:
        raise ValueError(f"El contrato admite de 1 a {MAX_PUNTOS_CONTRATO} intervalos; hay {len(puntos)}")
    instantes = [p["interval_start"] for p in puntos]
    if len(set(instantes)) != len(instantes):
        raise ValueError("Hay intervalos duplicados en el pronóstico")
    cuerpo = {"model_name": model_name, "model_version": model_version, "source": "statistics-service", "points": puntos}
    if notes:
        cuerpo["notes"] = notes[:2000]
    return cuerpo
