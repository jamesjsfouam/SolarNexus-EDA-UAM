"""Cliente HTTP mínimo (solo biblioteca estándar) para la API del backend.

- GET  /api/v1/measurements  → SerieCampus (hora local de Managua, humedad en fracción)
- POST /api/v1/forecasts     → envía el pronóstico en el formato del contrato

Conversión de unidades (docs/API_CONTRACT.md):
- humidity_pct viene en %, el modelo usa fracción.
- activity_index puede ser 0, pero el modelo usa ln ACT: se acota a ACTIVIDAD_MINIMA.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

import numpy as np

from ..datos import SerieCampus
from ..oraculo import Observaciones
from .pronostico import ZONA_MANAGUA

ACTIVIDAD_MINIMA = 0.01
PAGINA = 1000
TIEMPO_ESPERA_S = 30


class ErrorAPI(RuntimeError):
    pass


def _url(base: str, ruta: str, params: dict | None = None) -> str:
    partes = urllib.parse.urlparse(base)
    if partes.scheme not in ("http", "https") or not partes.netloc:
        raise ValueError(f"URL de API no válida: {base!r} (usa http:// o https://)")
    url = base.rstrip("/") + ruta
    return url + ("?" + urllib.parse.urlencode(params) if params else "")


def _peticion(url: str, datos: dict | None = None) -> object:
    cuerpo = None if datos is None else json.dumps(datos).encode("utf-8")
    req = urllib.request.Request(url, data=cuerpo, method="GET" if datos is None else "POST",
                                 headers={"Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIEMPO_ESPERA_S) as r:  # noqa: S310 (esquema validado en _url)
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detalle = e.read().decode("utf-8", "replace")[:500]
        raise ErrorAPI(f"HTTP {e.code} en {url}: {detalle}") from None
    except urllib.error.URLError as e:
        raise ErrorAPI(f"No se pudo conectar con {url}: {e.reason}") from None


def mediciones_a_serie(registros: list[dict]) -> SerieCampus:
    """Convierte registros de /measurements (cualquier orden) en una serie horaria local."""
    filas = [r for r in registros if r.get("consumption_kwh") is not None]
    if len(filas) < 24:
        raise ValueError("Hacen falta al menos 24 mediciones con consumo")
    locales = []
    for r in filas:
        instante = datetime.fromisoformat(r["interval_start"].replace("Z", "+00:00"))
        if instante.tzinfo is None:
            raise ValueError("Las mediciones deben traer zona horaria")
        locales.append(np.datetime64(instante.astimezone(ZONA_MANAGUA).replace(tzinfo=None), "h"))
    fechas = np.array(locales)
    orden = np.argsort(fechas, kind="stable")
    if np.any(np.diff(fechas[orden]) == np.timedelta64(0, "h")):
        raise ValueError("Hay mediciones repetidas para la misma hora")

    def col(nombre: str, defecto: float | None = None) -> np.ndarray:
        return np.array([float(r[nombre] if r.get(nombre) is not None else defecto) for r in filas])[orden]

    return SerieCampus(
        fechas=fechas[orden],
        observaciones=Observaciones(
            temperatura=col("temperature_c"),
            humedad=col("humidity_pct") / 100,
            actividad=np.maximum(col("activity_index"), ACTIVIDAD_MINIMA),
            area=col("conditioned_area_m2"),
            consumo=col("consumption_kwh"),
        ),
        pv=col("pv_generation_kwh", 0.0),
    )


def leer_mediciones(base: str, inicio: datetime | None = None, fin: datetime | None = None) -> SerieCampus:
    """Descarga todas las mediciones del rango (paginando de 1000 en 1000)."""
    params: dict = {"limit": PAGINA}
    for nombre, valor in (("start", inicio), ("end", fin)):
        if valor is not None:
            if valor.tzinfo is None:
                valor = valor.replace(tzinfo=ZONA_MANAGUA)
            params[nombre] = valor.isoformat()
    registros: list[dict] = []
    while True:
        lote = _peticion(_url(base, "/api/v1/measurements", {**params, "offset": len(registros)}))
        if not isinstance(lote, list):
            raise ErrorAPI("Respuesta inesperada de /measurements")
        registros.extend(lote)
        if len(lote) < PAGINA:
            break
    return mediciones_a_serie(registros)


def enviar_pronostico(base: str, cuerpo: dict) -> dict:
    """POST /api/v1/forecasts. Devuelve la respuesta del backend (incluye el id del pronóstico)."""
    respuesta = _peticion(_url(base, "/api/v1/forecasts"), cuerpo)
    if not isinstance(respuesta, dict):
        raise ErrorAPI("Respuesta inesperada de /forecasts")
    return respuesta
