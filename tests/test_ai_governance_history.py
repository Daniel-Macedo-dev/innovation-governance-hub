from datetime import date

import pytest
from sqlalchemy import select

from innovation_governance_hub.domain.enums import AIStatus
from innovation_governance_hub.exceptions import ValidationError
from innovation_governance_hub.persistence.models import AIGovernanceDecision
from innovation_governance_hub.services.ai_governance_service import AIUseCaseService


def data(status="Em avaliação"):
    return {
        "code": "IA-900",
        "name": "Assistente",
        "responsible_area": "Operações",
        "objective": "Apoiar análise",
        "ai_tool": "Ferramenta demo",
        "model_or_provider": "Local",
        "data_description": "Dados fictícios",
        "uses_personal_data": False,
        "risk_level": "Baixo",
        "risk_mitigation": "Revisão humana",
        "expected_impact": "Agilidade",
        "evaluation_status": status,
        "owner": "Daniel",
        "next_review_date": date(2026, 12, 1),
        "policy_accepted": True,
        "governance_approved": status in (AIStatus.APPROVED, AIStatus.RESTRICTED),
        "estimated_users": 10,
        "active_users": 2,
        "notes": "Justificativa",
        "actor": "Daniel",
        "justification": "Decisão documentada",
    }


def test_decisions_are_append_only(session):
    service = AIUseCaseService(session)
    case = service.save(data())
    service.save(data(AIStatus.APPROVED), case.id)
    service.suspend(case.id, "Daniel", "Risco operacional identificado")
    history = list(session.scalars(select(AIGovernanceDecision).order_by(AIGovernanceDecision.id)))
    assert [item.new_status for item in history] == ["Em avaliação", "Aprovado", "Suspenso"]
    with pytest.raises(ValidationError, match="preservam histórico"):
        service.delete(case.id)


def test_restriction_rejection_and_suspension_require_context(session):
    service = AIUseCaseService(session)
    restricted = data(AIStatus.RESTRICTED)
    with pytest.raises(ValidationError, match="descrição das restrições"):
        service.save(restricted)
    rejected = data(AIStatus.REJECTED) | {"justification": "", "notes": ""}
    with pytest.raises(ValidationError, match="exige justificativa"):
        service.save(rejected)
