from datetime import date, datetime
from decimal import Decimal

import pytest

from innovation_governance_hub.domain.enums import EvaluationType, Stage
from innovation_governance_hub.exceptions import GateBlockedError, ValidationError
from innovation_governance_hub.persistence.models import (
    AIUseCase,
    AnnualBudget,
    Expense,
    GateCriterionDefinition,
    Initiative,
    StageTransition,
)
from innovation_governance_hub.services.ai_governance_service import adoption, validate_approval
from innovation_governance_hub.services.budget_service import BudgetService
from innovation_governance_hub.services.gate_service import GateService


def initiative(**changes):
    values = dict(
        code="INI-999",
        name="Teste",
        problem_description="Problema",
        proposed_solution="Solução",
        requesting_area="Área",
        owner="Dona",
        priority="Alta",
        expected_impact_level="Alto",
        expected_impact_description="Impacto",
        complexity="Média",
        created_date=date.today(),
        deadline=date.today(),
        status="Ativa",
        current_stage="Ideia",
        planned_cost=Decimal("100"),
        expected_benefit=Decimal("200"),
        notes="",
        last_activity_at=datetime.now(),
    )
    values.update(changes)
    return Initiative(**values)


def test_gate_blocked_and_recorded(session):
    item = initiative(problem_description="")
    session.add(item)
    session.flush()
    session.add(
        GateCriterionDefinition(
            code="IDEA_PROBLEM",
            name="Problema definido",
            description="",
            stage=Stage.IDEA,
            mandatory=True,
            evaluation_type=EvaluationType.AUTOMATIC,
            display_order=1,
            active=True,
        )
    )
    session.flush()
    with pytest.raises(GateBlockedError):
        GateService(session).advance(item.id, "Teste")
    assert session.query(StageTransition).one().successful is False


def test_gate_advance_when_complete(session):
    item = initiative()
    session.add(item)
    session.flush()
    session.add(
        GateCriterionDefinition(
            code="IDEA_PROBLEM",
            name="Problema definido",
            description="",
            stage=Stage.IDEA,
            mandatory=True,
            evaluation_type=EvaluationType.AUTOMATIC,
            display_order=1,
            active=True,
        )
    )
    session.flush()
    GateService(session).advance(item.id, "Teste")
    assert item.current_stage == Stage.SCREENING


def test_budget_decimal_and_zero(session):
    item = initiative()
    session.add_all([item, AnnualBudget(year=2026, planned_amount=Decimal("1000"), notes="")])
    session.flush()
    session.add(
        Expense(
            initiative_id=item.id,
            competence_date=date(2026, 1, 1),
            category="Outros",
            description="Teste",
            supplier="",
            tool_name="",
            cost_type="Pontual",
            financial_status="Realizado",
            amount=Decimal("250.50"),
        )
    )
    session.flush()
    totals = BudgetService(session).totals(2026)
    assert totals["actual"] == Decimal("250.50")
    assert totals["balance"] == Decimal("749.50")
    assert BudgetService(session).totals(2025)["consumed_percent"] == 0


def test_ai_adoption_and_approval():
    case = AIUseCase(
        code="IA-X",
        name="X",
        responsible_area="A",
        objective="O",
        ai_tool="T",
        model_or_provider="P",
        data_description="",
        uses_personal_data=False,
        risk_level="Alto",
        risk_mitigation="",
        expected_impact="",
        evaluation_status="Rascunho",
        owner="",
        next_review_date=None,
        policy_accepted=False,
        governance_approved=False,
        estimated_users=0,
        active_users=999,
        notes="",
    )
    assert adoption(case) == 0
    with pytest.raises(ValidationError):
        validate_approval(case, "Aprovado")
    case.estimated_users, case.active_users = 10, 20
    assert adoption(case) == 100
