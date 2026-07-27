from collections.abc import Generator
from pathlib import Path

from sqlalchemy import Engine, create_engine, event, inspect, text
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

    selected = target or engine
    Base.metadata.create_all(selected)
    if selected.dialect.name == "sqlite" and inspect(selected).has_table("initiatives"):
        initiative_columns = {
            column["name"] for column in inspect(selected).get_columns("initiatives")
        }
        if "strategic_theme" not in initiative_columns:
            with selected.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE initiatives ADD COLUMN strategic_theme VARCHAR(120) NOT NULL DEFAULT ''"
                    )
                )
    if selected.dialect.name == "sqlite" and inspect(selected).has_table("import_batches"):
        existing_import = {
            column["name"] for column in inspect(selected).get_columns("import_batches")
        }
        import_additions = {
            "original_filename": "VARCHAR(255) NOT NULL DEFAULT ''",
            "created_count": "INTEGER NOT NULL DEFAULT 0",
            "updated_count": "INTEGER NOT NULL DEFAULT 0",
        }
        with selected.begin() as connection:
            for name, definition in import_additions.items():
                if name not in existing_import:
                    connection.execute(
                        text(f"ALTER TABLE import_batches ADD COLUMN {name} {definition}")
                    )
    if selected.dialect.name == "sqlite" and inspect(selected).has_table("notification_logs"):
        existing = {column["name"] for column in inspect(selected).get_columns("notification_logs")}
        additions = {
            "lifecycle_status": "VARCHAR(30) NOT NULL DEFAULT 'Novo'",
            "acknowledged_at": "DATETIME",
            "acknowledged_by": "VARCHAR(120)",
            "resolved_at": "DATETIME",
            "resolved_by": "VARCHAR(120)",
            "resolution_note": "TEXT NOT NULL DEFAULT ''",
        }
        with selected.begin() as connection:
            for name, definition in additions.items():
                if name not in existing:
                    connection.execute(
                        text(f"ALTER TABLE notification_logs ADD COLUMN {name} {definition}")
                    )


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
