"""SolarNexus-EDA-UAM: despacho energético predictivo para el campus UAM (Managua).

Módulos:
    config     Parámetros del sistema (ventana pico, umbrales, batería).
    balance    Ecuaciones de balance energético (base y extendida).
    oraculo    Motor econométrico 3P log-lineal, selección por AIC y pronóstico.
    despacho   Controlador de baterías: carga, peak shaving y exportación.
    mesh       Red mesh DC: enrutamiento panel a panel y precios sombra (MILP).
    datos      Generador de datos sintéticos para pruebas y demostraciones.
"""

from .balance import FlujosEnergia
from .config import Parametros
from .despacho import Bateria, ControladorDespacho, Regimen
from .mesh import Enlace, Nodo, RedMeshDC
from .oraculo import ModeloAjustado, Observaciones, Pronostico, ajustar, seleccionar_por_aic

__all__ = [
    "Bateria",
    "ControladorDespacho",
    "Enlace",
    "FlujosEnergia",
    "ModeloAjustado",
    "Nodo",
    "Observaciones",
    "Parametros",
    "Pronostico",
    "RedMeshDC",
    "Regimen",
    "ajustar",
    "seleccionar_por_aic",
]

__version__ = "0.1.0"
