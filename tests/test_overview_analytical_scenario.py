"""Cenário analítico da Visão Geral: o portfólio permite comparar volume e prazo.

Os dados nascem do seed compartilhado. A interface apenas apresenta; a leitura
crítica é humana. Os testes validam relações, não a área escolhida.
"""

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from innovation_governance_hub.database import Base
from innovation_governance_hub.services.ui_query_services import OverviewQueryService
from scripts import seed_demo

REVEALING_PHRASES = (
    "erro proposital",
    "inconsistência plantada",
    "descoberta para entrevista",
    "ponto de atenção encontrado",
    "área com mais projetos",
    "volume alto não significa",
    "analise esta área",
    "insight automático",
    "maior volume, menor desempenho",
    "área crítica",
)


@pytest.fixture
def seeded_session(tmp_path, monkeypatch):
    monkeypatch.setenv("DEMO_REFERENCE_DATE", "2026-07-27")
    from innovation_governance_hub.config import get_settings

    get_settings.cache_clear()
    engine = create_engine(f"sqlite:///{tmp_path / 'seed.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(seed_demo, "SessionLocal", factory)
    monkeypatch.setattr(seed_demo, "init_db", lambda: None)
    seed_demo.seed()
    with factory() as session:
        yield session
    get_settings.cache_clear()


def test_single_leader_in_active_volume(seeded_session):
    data = OverviewQueryService(seeded_session).load()
    metrics = data["area_delivery"]
    assert len(metrics) >= 3
    leader, second = metrics[0], metrics[1]
    assert leader.active > second.active, "deve existir uma única área líder em volume"


def test_leader_is_not_the_best_in_deadline(seeded_session):
    metrics = OverviewQueryService(seeded_session).load()["area_delivery"]
    leader = metrics[0]
    better = [m for m in metrics if m.on_time_percentage > leader.on_time_percentage]
    assert better, "a área líder em volume não deve liderar o cumprimento de prazo"


def test_a_smaller_area_has_clearly_higher_deadline_rate(seeded_session):
    metrics = OverviewQueryService(seeded_session).load()["area_delivery"]
    leader = metrics[0]
    contrast = [
        m
        for m in metrics[1:]
        if m.active < leader.active and m.on_time_percentage - leader.on_time_percentage >= 20
    ]
    assert contrast, "deve haver área de menor volume com prazo ao menos 20 p.p. superior"


def test_metrics_are_mathematically_consistent(seeded_session):
    data = OverviewQueryService(seeded_session).load()
    metrics = data["area_delivery"]
    for metric in metrics:
        assert metric.active == metric.on_time + metric.overdue + metric.no_deadline
        assert metric.active >= 0
        assert 0 <= metric.on_time_percentage <= 100
    assert sum(m.active for m in metrics) == data["active"]
    assert sum(m.overdue for m in metrics) == data["overdue"]


def test_scenario_reproduces_in_isolated_interview_database(tmp_path, monkeypatch):
    """O banco novo comum e o banco de entrevista recebem a mesma distribuição."""
    monkeypatch.setenv("DEMO_REFERENCE_DATE", "2026-07-27")
    from innovation_governance_hub.config import get_settings

    get_settings.cache_clear()
    leaders = []
    for name in ("normal.db", "interview.db"):
        engine = create_engine(f"sqlite:///{tmp_path / name}")
        Base.metadata.create_all(engine)
        factory = sessionmaker(engine, expire_on_commit=False)
        monkeypatch.setattr(seed_demo, "SessionLocal", factory)
        monkeypatch.setattr(seed_demo, "init_db", lambda: None)
        seed_demo.seed()
        with factory() as session:
            metrics = OverviewQueryService(session).load()["area_delivery"]
            leaders.append((metrics[0].area, metrics[0].active, metrics[0].on_time_percentage))
    get_settings.cache_clear()
    assert leaders[0] == leaders[1]


def test_overview_view_has_no_interpretive_text_or_env_branching():
    source = Path("src/innovation_governance_hub/ui/views/overview.py").read_text(encoding="utf-8")
    lowered = source.lower()
    for phrase in REVEALING_PHRASES:
        assert phrase not in lowered, phrase
    assert "app_env" not in lowered
    assert "add_annotation" not in lowered  # sem anotação apontando o contraste


def test_public_docs_stay_neutral():
    roots = [Path("README.md"), Path("docs")]
    offenders = []
    for root in roots:
        files = [root] if root.is_file() else sorted(root.rglob("*.md"))
        for path in files:
            lowered = path.read_text(encoding="utf-8").lower()
            for phrase in REVEALING_PHRASES:
                if phrase in lowered:
                    offenders.append(f"{path}: {phrase}")
    assert not offenders, offenders
