from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker

from src.config import settings


def create_database_engine(database_url: str) -> Engine:
    """Create an engine with backend-specific integrity and concurrency settings."""
    is_sqlite = database_url.startswith("sqlite:")
    connect_args = {"check_same_thread": False, "timeout": 30} if is_sqlite else {}
    database_engine = create_engine(database_url, connect_args=connect_args)

    if is_sqlite:
        @event.listens_for(database_engine, "connect")
        def configure_sqlite_connection(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA busy_timeout=30000")
            finally:
                cursor.close()

    return database_engine


engine = create_database_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
