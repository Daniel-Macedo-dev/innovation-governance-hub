import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

os.environ["DATABASE_URL"] = "sqlite:///data/test_hub.db"

from innovation_governance_hub.database import Base  # noqa: E402
from innovation_governance_hub.persistence import models  # noqa: E402,F401


@pytest.fixture
def session(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")

    @event.listens_for(engine, "connect")
    def fk(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine) as value:
        yield value
