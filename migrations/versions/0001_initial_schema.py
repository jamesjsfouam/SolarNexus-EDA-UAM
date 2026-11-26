"""Initial SolarNexus persistence schema.
Revision ID: 0001_initial
Revises:
"""
from alembic import op
import sqlalchemy as sa
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("campus_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("campus_name", sa.String(length=160), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"))
    op.create_table("measurements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("interval_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("temperature_c", sa.Float(), nullable=False),
        sa.Column("humidity_pct", sa.Float(), nullable=False),
        sa.Column("activity_index", sa.Float(), nullable=False),
        sa.Column("conditioned_area_m2", sa.Float(), nullable=False),
        sa.Column("consumption_kwh", sa.Float(), nullable=True),
        sa.Column("pv_generation_kwh", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("interval_start", name="uq_measurement_interval_start"))
    op.create_index("ix_measurements_interval_start", "measurements", ["interval_start"], unique=False)
    op.create_table("forecast_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("model_version", sa.String(length=80), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"))
    op.create_table("forecast_points",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("forecast_run_id", sa.Integer(), nullable=False),
        sa.Column("interval_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("demand_kwh", sa.Float(), nullable=False),
        sa.Column("pv_generation_kwh", sa.Float(), nullable=False),
        sa.Column("probability_within_margin", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["forecast_run_id"], ["forecast_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("forecast_run_id", "interval_start", name="uq_forecast_run_interval"))
    op.create_index("ix_forecast_points_forecast_run_id", "forecast_points", ["forecast_run_id"], unique=False)
    op.create_table("dispatch_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("forecast_run_id", sa.Integer(), nullable=False),
        sa.Column("battery_capacity_kwh", sa.Float(), nullable=False),
        sa.Column("battery_power_kw", sa.Float(), nullable=False),
        sa.Column("initial_soc_kwh", sa.Float(), nullable=False),
        sa.Column("min_soc_kwh", sa.Float(), nullable=False),
        sa.Column("charge_efficiency", sa.Float(), nullable=False),
        sa.Column("final_soc_kwh", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["forecast_run_id"], ["forecast_runs.id"]),
        sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_dispatch_runs_forecast_run_id", "dispatch_runs", ["forecast_run_id"], unique=False)
    op.create_table("dispatch_points",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dispatch_run_id", sa.Integer(), nullable=False),
        sa.Column("interval_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("regime", sa.String(length=32), nullable=False),
        sa.Column("demand_kwh", sa.Float(), nullable=False),
        sa.Column("pv_generation_kwh", sa.Float(), nullable=False),
        sa.Column("probability_within_margin", sa.Float(), nullable=False),
        sa.Column("grid_import_kwh", sa.Float(), nullable=False),
        sa.Column("battery_charge_kwh", sa.Float(), nullable=False),
        sa.Column("battery_discharge_kwh", sa.Float(), nullable=False),
        sa.Column("export_kwh", sa.Float(), nullable=False),
        sa.Column("soc_after_kwh", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["dispatch_run_id"], ["dispatch_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_dispatch_points_dispatch_run_id", "dispatch_points", ["dispatch_run_id"], unique=False)

def downgrade() -> None:
    op.drop_index("ix_dispatch_points_dispatch_run_id", table_name="dispatch_points")
    op.drop_table("dispatch_points")
    op.drop_index("ix_dispatch_runs_forecast_run_id", table_name="dispatch_runs")
    op.drop_table("dispatch_runs")
    op.drop_index("ix_forecast_points_forecast_run_id", table_name="forecast_points")
    op.drop_table("forecast_points")
    op.drop_table("forecast_runs")
    op.drop_index("ix_measurements_interval_start", table_name="measurements")
    op.drop_table("measurements")
    op.drop_table("campus_config")
