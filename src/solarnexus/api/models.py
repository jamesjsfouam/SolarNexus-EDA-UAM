"""Persistence models for telemetry, forecasts and dispatch results."""
from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base
def utc_now() -> datetime:
    return datetime.now(timezone.utc)
class CampusConfig(Base):
    __tablename__ = "campus_config"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    campus_name: Mapped[str] = mapped_column(String(160), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="America/Managua")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
class Measurement(Base):
    __tablename__ = "measurements"
    __table_args__ = (UniqueConstraint("interval_start", name="uq_measurement_interval_start"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    interval_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    temperature_c: Mapped[float] = mapped_column(Float, nullable=False)
    humidity_pct: Mapped[float] = mapped_column(Float, nullable=False)
    activity_index: Mapped[float] = mapped_column(Float, nullable=False)
    conditioned_area_m2: Mapped[float] = mapped_column(Float, nullable=False)
    consumption_kwh: Mapped[float | None] = mapped_column(Float, nullable=True)
    pv_generation_kwh: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(80), nullable=False, default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
class ForecastRun(Base):
    __tablename__ = "forecast_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    model_version: Mapped[str] = mapped_column(String(80), nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False, default="statistics-service")
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    points: Mapped[list[ForecastPoint]] = relationship(back_populates="run", cascade="all, delete-orphan", order_by="ForecastPoint.interval_start")
class ForecastPoint(Base):
    __tablename__ = "forecast_points"
    __table_args__ = (UniqueConstraint("forecast_run_id", "interval_start", name="uq_forecast_run_interval"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    forecast_run_id: Mapped[int] = mapped_column(ForeignKey("forecast_runs.id", ondelete="CASCADE"), index=True)
    interval_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    demand_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    pv_generation_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    probability_within_margin: Mapped[float] = mapped_column(Float, nullable=False)
    run: Mapped[ForecastRun] = relationship(back_populates="points")
class DispatchRun(Base):
    __tablename__ = "dispatch_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    forecast_run_id: Mapped[int] = mapped_column(ForeignKey("forecast_runs.id"), nullable=False, index=True)
    battery_capacity_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    battery_power_kw: Mapped[float] = mapped_column(Float, nullable=False)
    initial_soc_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    min_soc_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    charge_efficiency: Mapped[float] = mapped_column(Float, nullable=False)
    peak_start_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=14)
    peak_end_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=17)
    alpha: Mapped[float] = mapped_column(Float, nullable=False, default=0.05)
    delta: Mapped[float] = mapped_column(Float, nullable=False, default=0.10)
    final_soc_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    points: Mapped[list[DispatchPoint]] = relationship(back_populates="run", cascade="all, delete-orphan", order_by="DispatchPoint.interval_start")
class DispatchPoint(Base):
    __tablename__ = "dispatch_points"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dispatch_run_id: Mapped[int] = mapped_column(ForeignKey("dispatch_runs.id", ondelete="CASCADE"), index=True)
    interval_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    regime: Mapped[str] = mapped_column(String(32), nullable=False)
    demand_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    pv_generation_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    probability_within_margin: Mapped[float] = mapped_column(Float, nullable=False)
    grid_import_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    battery_charge_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    battery_discharge_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    export_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    soc_after_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    run: Mapped[DispatchRun] = relationship(back_populates="points")
