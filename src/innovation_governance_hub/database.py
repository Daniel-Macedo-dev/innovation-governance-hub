from collections.abc import Generator
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from innovation_governance_hub.config import get_settings


class Base(DeclarativeBase):
    pass


def build_engine(url: str | None = None) -> Engine:
    database_url = url or get_settings().database_url
    if database_url.startswith("sqlite:///") and ":memory:" not in database_url:
        Path(database_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(database_url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def configure_sqlite(dbapi_connection: object, _record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    return engine


engine = build_engine()
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def init_db(target: Engine | None = None) -> None:
    from innovation_governance_hub.persistence import models  # noqa: F401

    Base.metadata.create_all(target or engine)


def session_scope() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
