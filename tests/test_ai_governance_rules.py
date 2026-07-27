"""Regras gerais de governança de IA (sem cenário específico de entrevista)."""

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from innovation_governance_hub.database import Base
from innovation_governance_hub.domain.enums import AIStatus, RiskLevel
from innovation_governance_hub.exceptions import ValidationError
from innovation_governance_hub.persistence.models import (
    AIGovernanceDecision,
    AIUseCase,
)
from innovation_governance_hub.services.ai_governance_service import (
    AIUseCaseService,
    adoption,
    review_overdue,
)
from innovation_governance_hub.services.automation_service import AutomationService
from scripts import prepare_interview_demo, seed_demo


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


def _case(**overrides) -> AIUseCase:
    data = {
        "code": "IA-900",
        "name": "Caso genérico",
        "responsible_area": "Operações",
        "objective": "Apoiar análise",
        "ai_tool": "Ferramenta",
        "model_or_provider": "Provedor",
        "data_description": "Dados sintéticos",
        "uses_personal_data": False,
        "risk_level": RiskLevel.MEDIUM,
        "risk_mitigation": "Revisão periódica",
        "expected_impact": "Ganho potencial",
        "evaluation_status": AIStatus.EVALUATING,
        "owner": "Responsável",
        "estimated_users": 100,
        "active_users": 40,
    }
    data.update(overrides)
    return AIUseCase(**data)


def test_adoption_is_active_over_estimated():
    assert adoption(_case(estimated_users=200, active_users=50)) == pytest.approx(25.0)


def test_adoption_with_zero_estimated_is_safe():
    assert adoption(_case(estimated_users=0, active_users=0)) == 0.0


def test_active_users_cannot_exceed_estimated(session):
    with pytest.raises(ValidationError):
        AIUseCaseService(session).save(
            {
                "code": "IA-950",
                "name": "Excesso",
                "estimated_users": 10,
                "active_users": 50,
                "evaluation_status": AIStatus.EVALUATING,
            }
        )


def test_high_risk_unapproved_case_raises_legitimate_alert(session):
    case = _case(
        code="IA-951",
        risk_level=RiskLevel.HIGH,
        evaluation_status=AIStatus.EVALUATING,
        governance_approved=False,
        active_users=90,
        estimated_users=100,
    )
    session.add(case)
    session.flush()
    alerts = AutomationService(session).run(persist=False)
    risk_alerts = [
        alert
        for alert in alerts
        if alert.notification_type == "ia_risco_sem_aprovacao" and alert.entity_id == case.id
    ]
    assert risk_alerts, "risco alto sem aprovação deve gerar alerta"
    for alert in risk_alerts:
        combined = f"{alert.title} {alert.message}".lower()
        assert "adoção" not in combined and "adocao" not in combined
    assert case.governance_approved is False, "o alerta não aprova o caso automaticamente"


def test_human_decision_creates_history_without_auto_approval(session):
    case = _case(code="IA-952", risk_level=RiskLevel.HIGH, evaluation_status=AIStatus.EVALUATING)
    session.add(case)
    session.flush()
    AIUseCaseService(session).save(
        {
            "code": case.code,
            "name": case.name,
            "evaluation_status": AIStatus.REVIEW,
            "justification": "Encaminhado para revisão formal.",
            "actor": "Comitê",
        },
        case.id,
    )
    session.flush()
    history = session.scalars(
        select(AIGovernanceDecision).where(AIGovernanceDecision.ai_use_case_id == case.id)
    ).all()
    assert history
    assert case.governance_approved is False


def test_restricted_approval_requires_restrictions(session):
    case = _case(code="IA-953", governance_approved=True, policy_accepted=True)
    session.add(case)
    session.flush()
    with pytest.raises(ValidationError):
        AIUseCaseService(session).save(
            {
                "code": case.code,
                "name": case.name,
                "evaluation_status": AIStatus.RESTRICTED,
                "restrictions": "",
                "actor": "Comitê",
            },
            case.id,
        )


def test_rejection_requires_justification(session):
    case = _case(code="IA-954")
    session.add(case)
    session.flush()
    with pytest.raises(ValidationError):
        AIUseCaseService(session).save(
            {
                "code": case.code,
                "name": case.name,
                "evaluation_status": AIStatus.REJECTED,
                "justification": "",
                "actor": "Comitê",
            },
            case.id,
        )


def test_review_overdue_is_detectable():
    overdue = _case(next_review_date=date(2000, 1, 1))
    upcoming = _case(next_review_date=date.today() + timedelta(days=30))
    assert review_overdue(overdue) is True
    assert review_overdue(upcoming) is False


def test_seed_generates_plausible_ai_case_distribution(seeded_session):
    cases = list(seeded_session.scalars(select(AIUseCase)).all())
    assert len(cases) == 12
    for case in cases:
        assert 0 <= adoption(case) <= 100
        assert case.active_users <= case.estimated_users
    unapproved_high_risk = [
        case
        for case in cases
        if case.risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL}
        and case.evaluation_status not in {AIStatus.APPROVED, AIStatus.RESTRICTED}
    ]
    assert unapproved_high_risk, "deve haver ao menos um caso de risco alto sem aprovação"


def test_interview_preparation_uses_shared_seed(seeded_session):
    import inspect

    source = inspect.getsource(prepare_interview_demo.prepare)
    assert "seed" in source
    assert "IA-007" not in source
