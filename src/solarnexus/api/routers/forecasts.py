"""Ingestion and retrieval of forecasts produced by the statistics component."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from ..database import get_db
from ..models import ForecastPoint, ForecastRun
from ..schemas import ForecastRunCreate, ForecastRunRead
router = APIRouter(prefix="/forecasts", tags=["Forecasts"])
@router.post("", response_model=ForecastRunRead, status_code=201)
def create_forecast(payload: ForecastRunCreate, db: Session = Depends(get_db)) -> ForecastRun:
    run = ForecastRun(
        model_name=payload.model_name,
        model_version=payload.model_version,
        source=payload.source,
        notes=payload.notes,
        points=[ForecastPoint(**point.model_dump()) for point in payload.points],
    )
    db.add(run)
    db.commit()
    return db.scalar(select(ForecastRun).options(selectinload(ForecastRun.points)).where(ForecastRun.id == run.id))
@router.get("/latest", response_model=ForecastRunRead)
def latest_forecast(db: Session = Depends(get_db)) -> ForecastRun:
    run = db.scalar(
        select(ForecastRun).options(selectinload(ForecastRun.points))
        .order_by(ForecastRun.generated_at.desc(), ForecastRun.id.desc()).limit(1)
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Todavía no hay pronósticos registrados")
    return run
@router.get("/{forecast_id}", response_model=ForecastRunRead)
def get_forecast(forecast_id: int, db: Session = Depends(get_db)) -> ForecastRun:
    run = db.scalar(select(ForecastRun).options(selectinload(ForecastRun.points)).where(ForecastRun.id == forecast_id))
    if run is None:
        raise HTTPException(status_code=404, detail="Pronóstico no encontrado")
    return run
