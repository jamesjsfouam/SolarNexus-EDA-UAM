"""Energy dispatch planning endpoints backed by the existing dispatch engine."""
from datetime import timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from ...config import Parametros
from ...despacho import Bateria, ControladorDespacho
from ..database import get_db
from ..models import CampusConfig, DispatchPoint, DispatchRun, ForecastRun
from ..schemas import DispatchPlanCreate, DispatchRunRead
router = APIRouter(prefix="/dispatch", tags=["Dispatch"])
def _loaded_run(db: Session, run_id: int) -> ForecastRun:
    run = db.scalar(select(ForecastRun).options(selectinload(ForecastRun.points)).where(ForecastRun.id == run_id))
    if run is None:
        raise HTTPException(status_code=404, detail="El pronóstico solicitado no existe")
    if not run.points:
        raise HTTPException(status_code=422, detail="El pronóstico no contiene intervalos")
    return run
@router.post("/plan", response_model=DispatchRunRead, status_code=201)
def create_dispatch_plan(payload: DispatchPlanCreate, db: Session = Depends(get_db)) -> DispatchRun:
    forecast = _loaded_run(db, payload.forecast_run_id)
    points = sorted(forecast.points, key=lambda item: item.interval_start)
    for point in points:
        timestamp = point.interval_start
        if timestamp.minute != 0 or timestamp.second != 0 or timestamp.microsecond != 0:
            raise HTTPException(status_code=422, detail="El motor actual requiere intervalos alineados a la hora")
    for previous, current in zip(points, points[1:]):
        if current.interval_start - previous.interval_start != timedelta(hours=1):
            raise HTTPException(status_code=422, detail="Los intervalos deben ser consecutivos y de una hora")
    campus = db.scalar(select(CampusConfig).where(CampusConfig.id == 1))
    timezone_name = campus.timezone if campus is not None else "America/Managua"
    try:
        campus_timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(status_code=500, detail="La zona horaria del campus no es válida") from exc
    local_hours = []
    for point in points:
        stamp = point.interval_start
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        local_hours.append(stamp.astimezone(campus_timezone).hour)

    cfg = payload.battery
    try:
        battery = Bateria(capacidad_kwh=cfg.capacity_kwh, potencia_max_kw=cfg.power_kw,
            soc_kwh=cfg.initial_soc_kwh, soc_min_kwh=cfg.min_soc_kwh, eficiencia_carga=cfg.charge_efficiency)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    params = Parametros(hora_pico_inicio=cfg.peak_start_hour, hora_pico_fin=cfg.peak_end_hour, alpha=cfg.alpha, delta=cfg.delta)
    controller = ControladorDespacho(battery, params)
    plan = controller.planificar(
        horas=local_hours,
        consumo=[point.demand_kwh for point in points],
        pv=[point.pv_generation_kwh for point in points],
        prob_en_margen=[point.probability_within_margin for point in points],
    )
    run = DispatchRun(forecast_run_id=forecast.id, battery_capacity_kwh=cfg.capacity_kwh,
        battery_power_kw=cfg.power_kw, initial_soc_kwh=cfg.initial_soc_kwh,
        min_soc_kwh=cfg.min_soc_kwh, charge_efficiency=cfg.charge_efficiency,
        peak_start_hour=cfg.peak_start_hour, peak_end_hour=cfg.peak_end_hour,
        alpha=cfg.alpha, delta=cfg.delta,
        final_soc_kwh=battery.soc_kwh, points=[])
    for forecast_point, decision in zip(points, plan):
        flows = decision.flujos
        if not flows.cuadra():
            raise HTTPException(status_code=500, detail="El despacho produjo un balance energético inconsistente")
        run.points.append(DispatchPoint(interval_start=forecast_point.interval_start,
            regime=decision.regimen.value, demand_kwh=flows.consumo, pv_generation_kwh=flows.pv,
            probability_within_margin=decision.prob_en_margen, grid_import_kwh=flows.red,
            battery_charge_kwh=flows.b_carga, battery_discharge_kwh=flows.b_descarga,
            export_kwh=flows.exportacion, soc_after_kwh=decision.soc_final_kwh))
    db.add(run)
    db.commit()
    return db.scalar(select(DispatchRun).options(selectinload(DispatchRun.points)).where(DispatchRun.id == run.id))

@router.get("/latest", response_model=DispatchRunRead)
def latest_dispatch_plan(db: Session = Depends(get_db)) -> DispatchRun:
    run = db.scalar(
        select(DispatchRun)
        .options(selectinload(DispatchRun.points))
        .order_by(DispatchRun.created_at.desc(), DispatchRun.id.desc())
        .limit(1)
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Todavía no hay planes de despacho")
    return run

@router.get("/{dispatch_id}", response_model=DispatchRunRead)
def get_dispatch_plan(dispatch_id: int, db: Session = Depends(get_db)) -> DispatchRun:
    run = db.scalar(select(DispatchRun).options(selectinload(DispatchRun.points)).where(DispatchRun.id == dispatch_id))
    if run is None:
        raise HTTPException(status_code=404, detail="Plan de despacho no encontrado")
    return run
