"""O seed deve conter um caso de IA que permita leitura crítica sem que a
interface entregue a interpretação: os dados sustentam a análise, o sistema
apenas aponta a decisão formal pendente."""

from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from innovation_governance_hub.database import Base
from innovation_governance_hub.persistence.models import AIGovernanceDecision, AIUseCase
from innovation_governance_hub.services.ai_governance_service import AIUseCaseService, adoption
from innovation_governance_hub.services.automation_service import AutomationService
from innovation_governance_hub.services.executive_committee_service import (
    ExecutiveCommitteeService,
)
from innovation_governance_hub.services.ui_query_services import AIGovernanceQueryService
from scripts import prepare_interview_demo, seed_demo

ATTENTION_CASE_CODE = "IA-007"
PENDING_STATUSES = {"Rascunho", "Em avaliação", "Em revisão"}


@pytest.fixture
def seeded_session(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'seed.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(seed_demo, "SessionLocal", factory)
    monkeypatch.setattr(seed_demo, "init_db", lambda: None)
    seed_demo.seed()
    with factory() as session:
        yield session


def _attention_case(session) -> AIUseCase:
    case = session.scalar(select(AIUseCase).where(AIUseCase.code == ATTENTION_CASE_CODE))
    assert case is not None, f"{ATTENTION_CASE_CODE} deve existir no seed"
    return case


def test_attention_case_data_is_plausible_and_valid(seeded_session):
    case = _attention_case(seeded_session)
    assert case.estimated_users > 0
    assert 0 < case.active_users <= case.estimated_users
    assert 70 <= adoption(case) <= 85
    assert case.risk_level in {"Alto", "Crítico"}
    assert case.evaluation_status in PENDING_STATUSES
    assert case.governance_approved is False
    assert case.policy_accepted is False
    assert case.next_review_date is not None
    assert case.owner.strip()
    assert case.data_description.strip()
    assert case.risk_mitigation.strip()
    assert case.uses_personal_data is True


def test_attention_case_is_unique_in_the_range(seeded_session):
    matching = [
        case
        for case in seeded_session.scalars(select(AIUseCase)).all()
        if 70 <= adoption(case) <= 85
        and case.risk_level in {"Alto", "Crítico"}
        and case.evaluation_status in PENDING_STATUSES
        and not case.governance_approved
    ]
    assert [case.code for case in matching] == [ATTENTION_CASE_CODE]


def test_adoption_comes_from_the_formula(seeded_session):
    case = _attention_case(seeded_session)
    expected = case.active_users / case.estimated_users * 100
    assert adoption(case) == pytest.approx(expected)
    assert adoption(case) == pytest.approx(78.9, abs=0.1)
    listed = AIGovernanceQueryService(seeded_session).list()
    row = next(item for item in listed if item["code"] == ATTENTION_CASE_CODE)
    assert row["adoption"] == pytest.approx(expected)
    assert row["governance_approved"] is False


def test_governance_flags_the_case_without_mentioning_adoption(seeded_session):
    case = _attention_case(seeded_session)
    alerts = AutomationService(seeded_session).run(persist=False)
    related = [
        alert
        for alert in alerts
        if alert.notification_type == "ia_risco_sem_aprovacao" and alert.entity_id == case.id
    ]
    assert related, "o alerta normal de alto risco pendente deve existir"
    for alert in related:
        combined = f"{alert.title} {alert.message}".lower()
        assert "adoção" not in combined and "adocao" not in combined
    brief = ExecutiveCommitteeService(seeded_session).brief()
    decisions = [item for item in brief.decisions if item.entity == case.name]
    assert decisions, "o Comitê deve pedir decisão para o caso"
    for decision in decisions:
        assert "adoção" not in decision.reason.lower()
        assert "adoção" not in decision.recommendation.lower()


def test_case_accepts_human_decision_with_history(seeded_session):
    case = _attention_case(seeded_session)
    AIUseCaseService(seeded_session).save(
        {
            "code": case.code,
            "name": case.name,
            "evaluation_status": "Em revisão",
            "justification": "Encaminhado para revisão formal da governança.",
            "actor": "Comitê fictício",
        },
        case.id,
    )
    seeded_session.flush()
    history = seeded_session.scalars(
        select(AIGovernanceDecision).where(AIGovernanceDecision.ai_use_case_id == case.id)
    ).all()
    assert history, "a decisão humana deve gerar histórico"
    assert case.governance_approved is False, "nada é aprovado automaticamente"


def test_public_texts_do_not_reveal_the_reading():
    forbidden = [
        "erro proposital",
        "inconsistência plantada",
        "uso cresceu antes",
        "adoção alta não substitui",
        "caso criado para entrevista",
        "pegadinha",
        "descoberta planejada",
        "momento ensaiado",
    ]
    roots = [Path("README.md"), Path("docs"), Path("src"), Path("pages"), Path("scripts")]
    offenders = []
    for root in roots:
        files = [root] if root.is_file() else sorted(root.rglob("*"))
        for path in files:
            if path.suffix not in {".md", ".py"}:
                continue
            text = path.read_text(encoding="utf-8").lower()
            for phrase in forbidden:
                if phrase in text:
                    offenders.append(f"{path}: {phrase}")
    assert not offenders, offenders


def test_scenario_comes_from_shared_seed_not_interview_logic():
    import inspect

    source = inspect.getsource(prepare_interview_demo.prepare)
    assert "seed" in source, "o banco da entrevista deve nascer do mesmo seed"
    assert ATTENTION_CASE_CODE not in source, "sem lógica específica do caso na preparação"
