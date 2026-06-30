import os
from collections.abc import Generator

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

_engine = None
_engine_url: str | None = None


def _migrate_columns(engine) -> None:
    with engine.connect() as conn:
        rows = conn.execute(text("PRAGMA table_info(ticket)")).fetchall()
        existing = {row[1] for row in rows}
        if "deadline" not in existing:
            conn.execute(text("ALTER TABLE ticket ADD COLUMN deadline DATETIME"))
        if "status_since" not in existing:
            conn.execute(text("ALTER TABLE ticket ADD COLUMN status_since DATETIME"))
        conn.commit()


def _get_engine():
    global _engine, _engine_url
    url = os.environ.get("DATABASE_URL", "sqlite:///triagebot.db")
    if _engine is None or _engine_url != url:
        _engine = create_engine(url, connect_args={"check_same_thread": False})
        _engine_url = url
        SQLModel.metadata.create_all(_engine)
        _migrate_columns(_engine)
    return _engine


def init_db() -> None:
    _get_engine()


def get_engine():
    return _get_engine()


def get_session() -> Generator[Session, None, None]:
    with Session(_get_engine()) as session:
        yield session
