"""Persist dispatch peak-window and confidence parameters.

Revision ID: 0002_dispatch_config
Revises: 0001_initial
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_dispatch_config"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "dispatch_runs",
        sa.Column("peak_start_hour", sa.Integer(), server_default="14", nullable=False),
    )
    op.add_column(
        "dispatch_runs",
        sa.Column("peak_end_hour", sa.Integer(), server_default="17", nullable=False),
    )
    op.add_column(
        "dispatch_runs",
        sa.Column("alpha", sa.Float(), server_default="0.05", nullable=False),
    )
    op.add_column(
        "dispatch_runs",
        sa.Column("delta", sa.Float(), server_default="0.10", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("dispatch_runs", "delta")
    op.drop_column("dispatch_runs", "alpha")
    op.drop_column("dispatch_runs", "peak_end_hour")
    op.drop_column("dispatch_runs", "peak_start_hour")
