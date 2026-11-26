"""FastAPI application entry point for SolarNexus."""
from __future__ import annotations
import hmac
import math
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .. import __version__
from .database import init_db
from .routers import dashboard, dispatch, forecasts, measurements, mesh, system

API_KEY = os.getenv("SOLARNEXUS_API_KEY", "").strip()
ENVIRONMENT = os.getenv("SOLARNEXUS_ENV", "development").lower()
if ENVIRONMENT == "production" and len(API_KEY) < 32:
    raise RuntimeError("En producción debe configurarse SOLARNEXUS_API_KEY con al menos 32 caracteres")

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(
    title="SolarNexus API",
    description="Backend REST de SolarNexus: telemetría, pronósticos estadísticos y planificación de despacho.",
    version=__version__, docs_url="/docs", redoc_url="/redoc", lifespan=lifespan,
)

origins = [v.strip() for v in os.getenv(
    "SOLARNEXUS_CORS_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173",
).split(",") if v.strip()]
app.add_middleware(
    CORSMiddleware, allow_origins=origins, allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)


def _sanitize_error_value(value):
    """Make Pydantic error payloads JSON-safe, including NaN/Infinity inputs."""
    if isinstance(value, float) and not math.isfinite(value):
        return repr(value)
    if isinstance(value, dict):
        return {str(key): _sanitize_error_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize_error_value(item) for item in value]
    if isinstance(value, Exception):
        return str(value)
    return value


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": _sanitize_error_value(exc.errors())},
    )

@app.middleware("http")
async def api_key_guard(request: Request, call_next):
    """Optional shared-secret protection for service-to-service access."""
    protected = request.url.path.startswith("/api/v1/") and request.url.path != "/api/v1/health"
    if protected and API_KEY:
        supplied = request.headers.get("X-API-Key", "")
        if not hmac.compare_digest(supplied, API_KEY):
            return JSONResponse(status_code=401, content={"detail": "API key ausente o inválida"},
                headers={"WWW-Authenticate": "ApiKey"})
    return await call_next(request)

app.include_router(system.router, prefix="/api/v1")
app.include_router(measurements.router, prefix="/api/v1")
app.include_router(forecasts.router, prefix="/api/v1")
app.include_router(dispatch.router, prefix="/api/v1")
app.include_router(mesh.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")

@app.get("/", tags=["System"])
def root() -> dict[str, str]:
    return {"name": "SolarNexus API", "version": __version__, "docs": "/docs", "api": "/api/v1"}
