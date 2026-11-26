"""Fuentes externas de clima mientras no haya datos de la estación Copérnico.

- Open-Meteo Forecast: pronóstico horario de 1 a 16 días (temperatura, humedad, radiación).
- Open-Meteo Historical Forecast: pronósticos tal como se emitieron en el pasado; sirve para
  validar el modelo *ex ante* con la misma incertidumbre que tendrá en operación.
- Open-Meteo Archive: reanálisis ERA5 (historial).
- NASA POWER (horario): historial de temperatura, humedad y radiación desde 2001.

Todas son gratuitas y sin clave. Open-Meteo es gratuito para uso no comercial y pide citar
la fuente (CC BY 4.0). NASA POWER publica la radiación con unos días de retraso.

Todas las series se devuelven en hora local de Managua (UTC−6), con la humedad en fracción.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .cliente import _peticion, _url

# Campus UAM, Managua (aproximado; la resolución de estas fuentes es de 10 a 50 km).
LAT_UAM = 12.10
LON_UAM = -86.25

URL_OPEN_METEO = "https://api.open-meteo.com"
URL_OPEN_METEO_PASADOS = "https://historical-forecast-api.open-meteo.com"
URL_OPEN_METEO_ARCHIVO = "https://archive-api.open-meteo.com"
URL_NASA_POWER = "https://power.larc.nasa.gov"

FUENTES = ("open-meteo", "open-meteo-pasados", "open-meteo-archivo", "nasa-power")
_VARIABLES_OM = "temperature_2m,relative_humidity_2m,shortwave_radiation"
_DIAS_POR_PETICION_POWER = 366
_HORAS_UTC_A_MANAGUA = np.timedelta64(-6, "h")


@dataclass(frozen=True)
class Clima:
    fuente: str
    fechas: np.ndarray       # datetime64[h], hora local de Managua
    temperatura: np.ndarray  # °C
    humedad: np.ndarray      # fracción [0, 1]
    radiacion: np.ndarray    # W/m² (media horaria de la radiación global horizontal)

    def __len__(self) -> int:
        return len(self.fechas)

    def dia(self, fecha: str) -> Clima:
        m = self.fechas.astype("datetime64[D]") == np.datetime64(fecha, "D")
        return Clima(self.fuente, self.fechas[m], self.temperatura[m], self.humedad[m], self.radiacion[m])

    def perfil_24h(self, fecha: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """(temperatura, humedad, radiación) de las 24 horas de `fecha`; NaN donde no hay dato."""
        d = self.dia(fecha)
        t, h, r = (np.full(24, np.nan) for _ in range(3))
        horas = (d.fechas - d.fechas.astype("datetime64[D]")).astype(int)
        t[horas], h[horas], r[horas] = d.temperatura, d.humedad, d.radiacion
        return t, h, r

    def a_csv(self) -> str:
        filas = ["fecha,temperatura,humedad,radiacion"]
        for f, t, h, r in zip(self.fechas, self.temperatura, self.humedad, self.radiacion):
            filas.append(f"{f},{t:.2f},{h:.4f},{r:.1f}")
        return "\n".join(filas) + "\n"


def _limpiar(valores, relleno: float | None = None) -> np.ndarray:
    a = np.array([np.nan if v is None else float(v) for v in valores])
    if relleno is not None:
        a[a == relleno] = np.nan
    return a


def _open_meteo(base: str, ruta: str, params: dict, fuente: str) -> Clima:
    d = _peticion(_url(base, ruta, {
        "latitude": params.pop("lat"), "longitude": params.pop("lon"),
        "hourly": _VARIABLES_OM, "timezone": "America/Managua", **params,
    }))
    if not isinstance(d, dict) or "hourly" not in d:
        motivo = d.get("reason") if isinstance(d, dict) else None
        raise ValueError(f"Respuesta inesperada de Open-Meteo{': ' + motivo if motivo else ''}")
    h = d["hourly"]
    return Clima(
        fuente=fuente,
        fechas=np.array([np.datetime64(t, "h") for t in h["time"]]),
        temperatura=_limpiar(h["temperature_2m"]),
        humedad=_limpiar(h["relative_humidity_2m"]) / 100,
        radiacion=_limpiar(h["shortwave_radiation"]),
    )


def open_meteo_pronostico(dias: int = 3, lat: float = LAT_UAM, lon: float = LON_UAM, base: str | None = None) -> Clima:
    """Pronóstico horario desde hoy (hora de Managua) para `dias` días (1–16)."""
    if not 1 <= dias <= 16:
        raise ValueError("Open-Meteo pronostica de 1 a 16 días")
    return _open_meteo(base or URL_OPEN_METEO, "/v1/forecast", {"lat": lat, "lon": lon, "forecast_days": dias}, "open-meteo")


def open_meteo_historico(
    inicio: str, fin: str, pronosticos_pasados: bool = True,
    lat: float = LAT_UAM, lon: float = LON_UAM, base: str | None = None,
) -> Clima:
    """Historial entre `inicio` y `fin` (AAAA-MM-DD, inclusive).

    pronosticos_pasados=True usa los pronósticos tal como se emitieron (validación ex ante);
    False usa el reanálisis ERA5 (lo que ocurrió).
    """
    if np.datetime64(inicio, "D") > np.datetime64(fin, "D"):
        raise ValueError("inicio debe ser anterior o igual a fin")
    if pronosticos_pasados:
        return _open_meteo(base or URL_OPEN_METEO_PASADOS, "/v1/forecast",
                           {"lat": lat, "lon": lon, "start_date": inicio, "end_date": fin}, "open-meteo-pasados")
    return _open_meteo(base or URL_OPEN_METEO_ARCHIVO, "/v1/archive",
                       {"lat": lat, "lon": lon, "start_date": inicio, "end_date": fin}, "open-meteo-archivo")


def nasa_power(inicio: str, fin: str, lat: float = LAT_UAM, lon: float = LON_UAM, base: str | None = None) -> Clima:
    """Serie horaria de NASA POWER entre `inicio` y `fin` (inclusive), convertida de UTC a Managua."""
    d0, d1 = np.datetime64(inicio, "D"), np.datetime64(fin, "D")
    if d0 > d1:
        raise ValueError("inicio debe ser anterior o igual a fin")
    # Se pide un día más en UTC para cubrir las 18–23 h locales del último día.
    d1_utc = d1 + np.timedelta64(1, "D")
    partes = []
    tramo = d0
    while tramo <= d1_utc:
        hasta = min(tramo + np.timedelta64(_DIAS_POR_PETICION_POWER - 1, "D"), d1_utc)
        r = _peticion(_url(base or URL_NASA_POWER, "/api/temporal/hourly/point", {
            "parameters": "T2M,RH2M,ALLSKY_SFC_SW_DWN", "community": "RE",
            "latitude": lat, "longitude": lon,
            "start": str(tramo).replace("-", ""), "end": str(hasta).replace("-", ""),
            "format": "JSON", "time-standard": "UTC",
        }))
        try:
            p = r["properties"]["parameter"]
            relleno = float(r.get("header", {}).get("fill_value", -999.0))
        except (KeyError, TypeError):
            raise ValueError("Respuesta inesperada de NASA POWER") from None
        claves = sorted(p["T2M"])
        utc = np.array([np.datetime64(f"{k[:4]}-{k[4:6]}-{k[6:8]}T{k[8:10]}", "h") for k in claves])
        partes.append((
            utc + _HORAS_UTC_A_MANAGUA,
            _limpiar([p["T2M"][k] for k in claves], relleno),
            _limpiar([p["RH2M"][k] for k in claves], relleno) / 100,
            _limpiar([p["ALLSKY_SFC_SW_DWN"][k] for k in claves], relleno),
        ))
        tramo = hasta + np.timedelta64(1, "D")
    fechas, t, h, r = (np.concatenate(x) for x in zip(*partes))
    m = (fechas.astype("datetime64[D]") >= d0) & (fechas.astype("datetime64[D]") <= d1)
    return Clima("nasa-power", fechas[m], t[m], h[m], r[m])


def obtener(fuente: str, inicio: str, fin: str, lat: float = LAT_UAM, lon: float = LON_UAM) -> Clima:
    """Punto de entrada único para la línea de comandos."""
    if fuente == "open-meteo":
        hoy = np.datetime64("today", "D")
        dias = int((np.datetime64(fin, "D") - hoy).astype(int)) + 1
        if np.datetime64(inicio, "D") < hoy:
            raise ValueError("open-meteo solo da el pronóstico desde hoy; para fechas pasadas usa open-meteo-pasados")
        return open_meteo_pronostico(max(1, min(dias, 16)), lat, lon)
    if fuente == "open-meteo-pasados":
        return open_meteo_historico(inicio, fin, True, lat, lon)
    if fuente == "open-meteo-archivo":
        return open_meteo_historico(inicio, fin, False, lat, lon)
    if fuente == "nasa-power":
        return nasa_power(inicio, fin, lat, lon)
    raise ValueError(f"Fuente desconocida: {fuente}. Opciones: {', '.join(FUENTES)}")


def pv_desde_radiacion(radiacion_w_m2: np.ndarray, kwp: float, rendimiento: float = 0.80) -> np.ndarray:
    """Producción horaria estimada (kWh) = kWp × GHI/1000 × PR.

    Aproximación con radiación horizontal: a 12° N los paneles van casi planos. El factor de
    rendimiento (PR ≈ 0,75–0,85) recoge temperatura, suciedad, cableado e inversor.
    """
    if kwp <= 0 or not 0 < rendimiento <= 1:
        raise ValueError("kwp debe ser > 0 y el rendimiento estar en (0, 1]")
    return kwp * np.clip(np.asarray(radiacion_w_m2, dtype=float), 0, None) / 1000 * rendimiento
