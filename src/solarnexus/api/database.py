"""Database configuration and Alembic migration management."""
from __future__ import annotations
import os
from pathlib import Path
from collections.abc import Generator
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.getenv("SOLARNEXUS_DATABASE_URL", "sqlite:///./solarnexus.db")
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

def init_db() -> None:
    """Apply versioned Alembic migrations before serving requests."""
    from . import models  # noqa: F401 - register ORM metadata for Alembic autogeneration
    config_path = Path(os.getenv("SOLARNEXUS_ALEMBIC_CONFIG", "alembic.ini")).resolve()
    if not config_path.is_file():
        raise RuntimeError(f"No se encontró la configuración de Alembic: {config_path}")
    config = Config(str(config_path))
    config.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))
    command.upgrade(config, "head")

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
