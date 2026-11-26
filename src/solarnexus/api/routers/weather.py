"""Weather context for SolarNexus, powered by Open-Meteo."""
from __future__ import annotations
import os
import time
from typing import Any
import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/weather", tags=["Weather"])
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
DEFAULT_LATITUDE = float(os.getenv("SOLARNEXUS_WEATHER_LATITUDE", "12.1328"))
DEFAULT_LONGITUDE = float(os.getenv("SOLARNEXUS_WEATHER_LONGITUDE", "-86.2504"))
DEFAULT_TIMEZONE = os.getenv("SOLARNEXUS_WEATHER_TIMEZONE", "America/Managua")
CACHE_TTL_SECONDS = max(0, int(os.getenv("SOLARNEXUS_WEATHER_CACHE_TTL", "600")))
_cache: dict[tuple[float, float, str], tuple[float, dict[str, Any]]] = {}

async def fetch_open_meteo(params: dict[str, Any]) -> dict[str, Any]:
    """Fetch upstream forecast with a bounded timeout."""
    async with httpx.AsyncClient(timeout=httpx.Timeout(8.0, connect=4.0)) as client:
        response = await client.get(OPEN_METEO_URL, params=params)
        response.raise_for_status()
        return response.json()

def _at(values: Any, index: int):
    return values[index] if isinstance(values, list) and index < len(values) else None

@router.get("", summary="Current weather and 24-hour solar forecast")
async def get_weather(
    latitude: float = Query(DEFAULT_LATITUDE, ge=-90, le=90),
    longitude: float = Query(DEFAULT_LONGITUDE, ge=-180, le=180),
    timezone: str = Query(DEFAULT_TIMEZONE, min_length=1, max_length=64),
) -> dict[str, Any]:
    """Return current conditions and the next 24 hourly weather/irradiance points."""
    key = (round(latitude, 4), round(longitude, 4), timezone)
    now = time.monotonic()
    cached = _cache.get(key)
    if cached and now - cached[0] < CACHE_TTL_SECONDS:
        return {**cached[1], "cached": True}
    params = {
        "latitude": latitude, "longitude": longitude, "timezone": timezone,
        "forecast_days": 2,
        "current": ["temperature_2m", "relative_humidity_2m", "apparent_temperature",
            "is_day", "precipitation", "weather_code", "cloud_cover", "wind_speed_10m",
            "wind_direction_10m"],
        "hourly": ["temperature_2m", "relative_humidity_2m", "precipitation_probability",
            "precipitation", "weather_code", "cloud_cover", "wind_speed_10m",
            "shortwave_radiation", "direct_radiation", "diffuse_radiation"],
    }
    try:
        upstream = await fetch_open_meteo(params)
        current, hourly = upstream.get("current"), upstream.get("hourly")
        if not isinstance(current, dict) or not isinstance(hourly, dict):
            raise ValueError("Respuesta meteorológica incompleta")
        times = hourly.get("time", [])
        if not isinstance(times, list) or not times:
            raise ValueError("No hay datos horarios")
        result = {
            "provider": "Open-Meteo",
            "location": {"latitude": upstream.get("latitude", latitude),
                "longitude": upstream.get("longitude", longitude),
                "timezone": upstream.get("timezone", timezone), "elevation_m": upstream.get("elevation")},
            "current": {
                "time": current.get("time"), "temperature_c": current.get("temperature_2m"),
                "feels_like_c": current.get("apparent_temperature"),
                "humidity_pct": current.get("relative_humidity_2m"),
                "precipitation_mm": current.get("precipitation"), "weather_code": current.get("weather_code"),
                "cloud_cover_pct": current.get("cloud_cover"), "wind_speed_kmh": current.get("wind_speed_10m"),
                "wind_direction_deg": current.get("wind_direction_10m"), "is_day": current.get("is_day")},
            "hourly": [{
                "time": times[i], "temperature_c": _at(hourly.get("temperature_2m"), i),
                "humidity_pct": _at(hourly.get("relative_humidity_2m"), i),
                "precipitation_probability_pct": _at(hourly.get("precipitation_probability"), i),
                "precipitation_mm": _at(hourly.get("precipitation"), i),
                "weather_code": _at(hourly.get("weather_code"), i),
                "cloud_cover_pct": _at(hourly.get("cloud_cover"), i),
                "wind_speed_kmh": _at(hourly.get("wind_speed_10m"), i),
                "shortwave_radiation_w_m2": _at(hourly.get("shortwave_radiation"), i),
                "direct_radiation_w_m2": _at(hourly.get("direct_radiation"), i),
                "diffuse_radiation_w_m2": _at(hourly.get("diffuse_radiation"), i)}
                for i in range(min(24, len(times)))],
            "units": {"temperature": "°C", "precipitation": "mm", "wind_speed": "km/h", "radiation": "W/m²"},
            "updated_at": current.get("time"), "cached": False}
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=502,
            detail="No fue posible obtener el pronóstico meteorológico. Inténtalo de nuevo más tarde.") from exc
    _cache[key] = (now, result)
    return result
