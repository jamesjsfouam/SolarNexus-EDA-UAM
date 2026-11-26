"""Validated request and response contracts exposed by the API."""
from __future__ import annotations
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator
PositiveEnergy = Annotated[float, Field(ge=0, le=10_000_000)]
def ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("La fecha debe incluir zona horaria, por ejemplo -06:00 o Z")
    return value.astimezone(timezone.utc)
class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

class ResponseModel(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

class ORMModel(ResponseModel):
    model_config = ConfigDict(from_attributes=True, allow_inf_nan=False)

    @field_serializer("*", when_used="json")
    def serialize_datetimes(self, value):
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.isoformat().replace("+00:00", "Z")
        return value
class HealthRead(ResponseModel):
    status: str
    database: str
    version: str
class CampusConfigUpdate(RequestModel):
    campus_name: str = Field(min_length=2, max_length=160)
    timezone: str = Field(default="America/Managua", min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Debe ser una zona horaria IANA válida") from exc
        return value
class CampusConfigRead(ORMModel):
    id: int
    campus_name: str
    timezone: str
    description: str | None
    updated_at: datetime
class MeasurementCreate(RequestModel):
    interval_start: datetime
    temperature_c: float = Field(ge=-20, le=65)
    humidity_pct: float = Field(ge=0, le=100)
    activity_index: float = Field(ge=0, le=1)
    conditioned_area_m2: float = Field(gt=0, le=10_000_000)
    consumption_kwh: PositiveEnergy | None = None
    pv_generation_kwh: PositiveEnergy | None = None
    source: str = Field(default="manual", min_length=1, max_length=80)
    @field_validator("interval_start")
    @classmethod
    def validate_interval_start(cls, value: datetime) -> datetime:
        return ensure_aware(value)
class MeasurementBatchCreate(RequestModel):
    records: list[MeasurementCreate] = Field(min_length=1, max_length=1000)
    @model_validator(mode="after")
    def unique_timestamps(self):
        timestamps = [item.interval_start for item in self.records]
        if len(set(timestamps)) != len(timestamps):
            raise ValueError("El lote contiene intervalos duplicados")
        return self
class MeasurementRead(ORMModel):
    id: int
    interval_start: datetime
    temperature_c: float
    humidity_pct: float
    activity_index: float
    conditioned_area_m2: float
    consumption_kwh: float | None
    pv_generation_kwh: float | None
    source: str
    created_at: datetime
class ForecastPointCreate(RequestModel):
    interval_start: datetime
    demand_kwh: PositiveEnergy
    pv_generation_kwh: PositiveEnergy
    probability_within_margin: float = Field(ge=0, le=1)
    @field_validator("interval_start")
    @classmethod
    def validate_interval_start(cls, value: datetime) -> datetime:
        return ensure_aware(value)
class ForecastRunCreate(RequestModel):
    model_name: str = Field(min_length=1, max_length=120)
    model_version: str = Field(min_length=1, max_length=80)
    source: str = Field(default="statistics-service", min_length=1, max_length=80)
    notes: str | None = Field(default=None, max_length=2000)
    points: list[ForecastPointCreate] = Field(min_length=1, max_length=168)
    @model_validator(mode="after")
    def validate_points(self):
        timestamps = [item.interval_start for item in self.points]
        if len(set(timestamps)) != len(timestamps):
            raise ValueError("El pronóstico contiene intervalos duplicados")
        if timestamps != sorted(timestamps):
            raise ValueError("Los intervalos del pronóstico deben venir ordenados")
        return self
class ForecastPointRead(ORMModel):
    id: int
    interval_start: datetime
    demand_kwh: float
    pv_generation_kwh: float
    probability_within_margin: float
class ForecastRunRead(ORMModel):
    id: int
    model_name: str
    model_version: str
    source: str
    generated_at: datetime
    notes: str | None
    points: list[ForecastPointRead]
class BatteryConfig(RequestModel):
    capacity_kwh: float = Field(gt=0, le=10_000_000)
    power_kw: float = Field(gt=0, le=10_000_000)
    initial_soc_kwh: float = Field(ge=0)
    min_soc_kwh: float = Field(default=0, ge=0)
    charge_efficiency: float = Field(default=0.95, gt=0, le=1)
    peak_start_hour: int = Field(default=14, ge=0, le=23)
    peak_end_hour: int = Field(default=17, ge=1, le=24)
    alpha: float = Field(default=0.05, gt=0, lt=1)
    delta: float = Field(default=0.10, gt=0)
    @model_validator(mode="after")
    def validate_battery(self):
        if self.min_soc_kwh > self.initial_soc_kwh:
            raise ValueError("La reserva mínima no puede superar el SOC inicial")
        if self.initial_soc_kwh > self.capacity_kwh:
            raise ValueError("El SOC inicial no puede superar la capacidad")
        if self.peak_start_hour >= self.peak_end_hour:
            raise ValueError("La ventana pico debe tener inicio anterior al final")
        return self
class DispatchPlanCreate(RequestModel):
    forecast_run_id: int = Field(gt=0)
    battery: BatteryConfig
class DispatchPointRead(ORMModel):
    id: int
    interval_start: datetime
    regime: str
    demand_kwh: float
    pv_generation_kwh: float
    probability_within_margin: float
    grid_import_kwh: float
    battery_charge_kwh: float
    battery_discharge_kwh: float
    export_kwh: float
    soc_after_kwh: float
class DispatchRunRead(ORMModel):
    id: int
    forecast_run_id: int
    battery_capacity_kwh: float
    battery_power_kw: float
    initial_soc_kwh: float
    min_soc_kwh: float
    charge_efficiency: float
    final_soc_kwh: float
    created_at: datetime
    points: list[DispatchPointRead]


class MeshNodeCreate(RequestModel):
    name: str = Field(min_length=1, max_length=80)
    generation_kwh: PositiveEnergy
    demand_kwh: PositiveEnergy

class MeshLinkCreate(RequestModel):
    origin: str = Field(min_length=1, max_length=80)
    destination: str = Field(min_length=1, max_length=80)
    capacity_kwh: float = Field(gt=0, le=10_000_000)
    transfer_cost_per_kwh: float = Field(ge=0, le=1_000_000)
    loss_fraction: float = Field(default=0, ge=0, lt=1)
    switch_cost: float = Field(default=0, ge=0, le=1_000_000)

class MeshSolveCreate(RequestModel):
    nodes: list[MeshNodeCreate] = Field(min_length=1, max_length=50)
    links: list[MeshLinkCreate] = Field(default_factory=list, max_length=500)
    central_cycling_cost_per_kwh: float = Field(ge=0, le=1_000_000)

    @model_validator(mode="after")
    def validate_network(self):
        names = [node.name for node in self.nodes]
        if len(names) != len(set(names)):
            raise ValueError("Los nombres de nodos deben ser únicos")
        known = set(names)
        edges = set()
        for link in self.links:
            if link.origin not in known or link.destination not in known:
                raise ValueError("Cada enlace debe conectar nodos declarados")
            if link.origin == link.destination:
                raise ValueError("Un enlace no puede conectarse consigo mismo")
            key = (link.origin, link.destination)
            if key in edges:
                raise ValueError("No se permiten enlaces dirigidos duplicados")
            edges.add(key)
        return self

class MeshFlowRead(ResponseModel):
    origin: str
    destination: str
    energy_kwh: float

class MeshSwitchRead(ResponseModel):
    origin: str
    destination: str

class MeshSolveRead(ResponseModel):
    flows: list[MeshFlowRead]
    switches_closed: list[MeshSwitchRead]
    central_supply_kwh: dict[str, float]
    curtailment_kwh: dict[str, float]
    shadow_prices: dict[str, float]
    total_cost: float


class DashboardSummaryRead(ResponseModel):
    campus_name: str
    timezone: str
    measurement_count: int
    latest_measurement: MeasurementRead | None
    forecast_run_id: int | None
    forecast_points_count: int
    forecast_demand_kwh: float | None
    forecast_pv_generation_kwh: float | None
    dispatch_run_id: int | None
    dispatch_points_count: int
    grid_import_kwh: float
    battery_charge_kwh: float
    battery_discharge_kwh: float
    export_kwh: float
    final_soc_kwh: float | None
