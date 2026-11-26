"""Componente estadístico de SolarNexus.

Responsabilidad (docs/API_CONTRACT.md del backend): ajustar y validar el modelo
econométrico 3P y producir pronósticos de demanda con una probabilidad calibrada
de caer dentro del margen, en el formato que acepta POST /api/v1/forecasts.

Módulos:
    metricas      CV(RMSE), NMBE, R² y criterios ASHRAE Guideline 14.
    diagnosticos  Durbin-Watson, Breusch-Godfrey, Breusch-Pagan, Jarque-Bera y errores HAC.
    validacion    Backtest día a día y calibración de la probabilidad en el margen.
    pronostico    Escenario de regresores, pronóstico y conversión al contrato del backend.
    cliente       Lectura de mediciones y envío de pronósticos a la API del backend.
"""

from .diagnosticos import Diagnosticos, diagnosticar
from .metricas import CRITERIOS_ASHRAE, Metricas, calcular_metricas
from .pronostico import PronosticoDia, a_contrato, escenario_climatologico, pronosticar_dia
from .validacion import ReporteValidacion, validar

__all__ = [
    "CRITERIOS_ASHRAE",
    "Diagnosticos",
    "Metricas",
    "PronosticoDia",
    "ReporteValidacion",
    "a_contrato",
    "calcular_metricas",
    "diagnosticar",
    "escenario_climatologico",
    "pronosticar_dia",
    "validar",
]
