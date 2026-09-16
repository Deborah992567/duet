"""SQLAlchemy engine/session management.

The rest of the application talks only to this module (or repositories) so the
MariaDB -> other database migration stays contained.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def _engine_kwargs() -> dict:
    kwargs: dict = {"pool_pre_ping": True, "pool_recycle": 1800}
    if settings.database_url.startswith("mysql"):
        kwargs["pool_size"] = 20
        kwargs["max_overflow"] = 40
        # MariaDB is strict about default timestamps.
        kwargs["connect_args"] = {"charset": "utf8mb4", "init_command": "SET time_zone='+00:00'"}
    else:
        kwargs["connect_args"] = {"check_same_thread": False}
    return kwargs


engine = create_engine(settings.database_url, **_engine_kwargs())
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a scoped session."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()