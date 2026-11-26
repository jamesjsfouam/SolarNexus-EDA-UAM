"""Telemetry ingestion and historical measurement endpoints."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Measurement
from ..schemas import MeasurementBatchCreate, MeasurementRead
router = APIRouter(prefix="/measurements", tags=["Telemetry"])
@router.post("/batch", response_model=list[MeasurementRead], status_code=201)
def create_measurements(payload: MeasurementBatchCreate, db: Session = Depends(get_db)) -> list[Measurement]:
    records = [Measurement(**record.model_dump()) for record in payload.records]
    db.add_all(records)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ya existe una medición para uno de los intervalos enviados") from exc
    for record in records:
        db.refresh(record)
    return records
@router.get("", response_model=list[MeasurementRead])
def list_measurements(
    start: datetime | None = Query(default=None, description="Inicio inclusivo; debe incluir zona horaria"),
    end: datetime | None = Query(default=None, description="Fin inclusivo; debe incluir zona horaria"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[Measurement]:
    if start is not None and (start.tzinfo is None or start.utcoffset() is None):
        raise HTTPException(status_code=422, detail="start debe incluir zona horaria")
    if end is not None and (end.tzinfo is None or end.utcoffset() is None):
        raise HTTPException(status_code=422, detail="end debe incluir zona horaria")
    if start is not None and end is not None and start > end:
        raise HTTPException(status_code=422, detail="start no puede ser posterior a end")
    stmt = select(Measurement).order_by(Measurement.interval_start.desc()).limit(limit).offset(offset)
    if start is not None:
        stmt = stmt.where(Measurement.interval_start >= start)
    if end is not None:
        stmt = stmt.where(Measurement.interval_start <= end)
    return list(db.scalars(stmt).all())
@router.get("/latest", response_model=MeasurementRead)
def latest_measurement(db: Session = Depends(get_db)) -> Measurement:
    item = db.scalar(select(Measurement).order_by(Measurement.interval_start.desc()).limit(1))
    if item is None:
        raise HTTPException(status_code=404, detail="Todavía no hay mediciones registradas")
    return item
