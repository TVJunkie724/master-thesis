"""Database adapter integrity and transaction-boundary tests."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from src.models.database import Base, create_database_engine


def test_sqlite_engine_enforces_foreign_keys(tmp_path):
    engine = create_database_engine(f"sqlite:///{tmp_path / 'integrity.db'}")
    Base.metadata.create_all(bind=engine)

    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1

    with engine.begin() as connection, pytest.raises(IntegrityError):
        connection.execute(
            text(
                "INSERT INTO digital_twins (id, user_id, name, state) "
                "VALUES ('orphan', 'missing-user', 'Orphan', 'DRAFT')"
            )
        )


def test_sqlite_engine_configures_busy_timeout(tmp_path):
    engine = create_database_engine(f"sqlite:///{tmp_path / 'timeout.db'}")

    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA busy_timeout")).scalar_one() == 30_000
