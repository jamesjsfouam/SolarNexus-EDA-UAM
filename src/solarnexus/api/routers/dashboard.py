"""Aggregated read model for the frontend dashboard."""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload
from ..database import get_db
from ..models import CampusConfig, DispatchRun, ForecastRun, Measurement
from ..schemas import DashboardSummaryRead, MeasurementRead

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/summary", response_model=DashboardSummaryRead)
def dashboard_summary(db: Session = Depends(get_db)) -> DashboardSummaryRead:
    campus = db.scalar(select(CampusConfig).where(CampusConfig.id == 1))
    campus_name = campus.campus_name if campus else "Universidad Americana (UAM)"
    campus_timezone = campus.timezone if campus else "America/Managua"
    measurement_count = db.scalar(select(func.count()).select_from(Measurement)) or 0
    latest_measurement = db.scalar(
        select(Measurement).order_by(Measurement.interval_start.desc(), Measurement.id.desc()).limit(1)
    )
    forecast = db.scalar(
        select(ForecastRun).options(selectinload(ForecastRun.points))
        .order_by(ForecastRun.generated_at.desc(), ForecastRun.id.desc()).limit(1)
    )
    dispatch = db.scalar(
        select(DispatchRun).options(selectinload(DispatchRun.points))
        .order_by(DispatchRun.created_at.desc(), DispatchRun.id.desc()).limit(1)
    )
    return DashboardSummaryRead(
        campus_name=campus_name,
        timezone=campus_timezone,
        measurement_count=measurement_count,
        latest_measurement=MeasurementRead.model_validate(latest_measurement) if latest_measurement else None,
        forecast_run_id=forecast.id if forecast else None,
        forecast_points_count=len(forecast.points) if forecast else 0,
        forecast_demand_kwh=sum(point.demand_kwh for point in forecast.points) if forecast else None,
        forecast_pv_generation_kwh=sum(point.pv_generation_kwh for point in forecast.points) if forecast else None,
        dispatch_run_id=dispatch.id if dispatch else None,
        dispatch_points_count=len(dispatch.points) if dispatch else 0,
        grid_import_kwh=sum(point.grid_import_kwh for point in dispatch.points) if dispatch else 0.0,
        battery_charge_kwh=sum(point.battery_charge_kwh for point in dispatch.points) if dispatch else 0.0,
        battery_discharge_kwh=sum(point.battery_discharge_kwh for point in dispatch.points) if dispatch else 0.0,
        export_kwh=sum(point.export_kwh for point in dispatch.points) if dispatch else 0.0,
        final_soc_kwh=dispatch.final_soc_kwh if dispatch else None,
    )
