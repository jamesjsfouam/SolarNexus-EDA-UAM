"""Health and campus configuration endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from ... import __version__
from ..database import get_db
from ..models import CampusConfig
from ..schemas import CampusConfigRead, CampusConfigUpdate, HealthRead
router = APIRouter(tags=["System"])
@router.get("/health", response_model=HealthRead)
def health(db: Session = Depends(get_db)) -> HealthRead:
    db.execute(text("SELECT 1"))
    return HealthRead(status="ok", database="connected", version=__version__)
@router.get("/campus", response_model=CampusConfigRead)
def get_campus(db: Session = Depends(get_db)) -> CampusConfig:
    config = db.scalar(select(CampusConfig).where(CampusConfig.id == 1))
    if config is None:
        config = CampusConfig(id=1, campus_name="Universidad Americana (UAM)", timezone="America/Managua")
        db.add(config)
        db.commit()
        db.refresh(config)
    return config
@router.put("/campus", response_model=CampusConfigRead)
def update_campus(payload: CampusConfigUpdate, db: Session = Depends(get_db)) -> CampusConfig:
    config = db.scalar(select(CampusConfig).where(CampusConfig.id == 1))
    if config is None:
        config = CampusConfig(id=1, **payload.model_dump())
        db.add(config)
    else:
        for key, value in payload.model_dump().items():
            setattr(config, key, value)
    db.commit()
    db.refresh(config)
    return config
