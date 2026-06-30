import os
from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

_engine = None
_engine_url: str | None = None


def _get_engine():
    global _engine, _engine_url
    url = os.environ.get("DATABASE_URL", "sqlite:///triagebot.db")
    if _engine is None or _engine_url != url:
        _engine_url = url
        _engine = create_engine(url, connect_args={"check_same_thread": False})
        SQLModel.metadata.create_all(_engine)
    return _engine


def init_db() -> None:
    _get_engine()


def get_engine():
    return _get_engine()


def get_session() -> Generator[Session, None, None]:
    with Session(_get_engine()) as session:
        yield session
