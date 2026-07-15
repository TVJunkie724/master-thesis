"""Database schema initialization boundary."""

from sqlalchemy.engine import Engine

from migrations.runner import run_migrations
from src.models.database import Base


def initialize_database_schema(engine: Engine, database_url: str) -> list[str]:
    """Create missing tables, then upgrade existing SQLite tables explicitly."""
    Base.metadata.create_all(bind=engine)
    return run_migrations(database_url)
