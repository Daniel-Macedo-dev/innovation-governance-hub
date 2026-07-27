from datetime import date, datetime
from decimal import Decimal

from innovation_governance_hub.config import Settings
from innovation_governance_hub.persistence.models import (
    AnnualBudget,
    Expense,
    GateCriterionDefinition,
    Initiative,
)
from innovation_governance_hub.services.automation_service import AutomationService


def initiative():
    return Initiative(
        code="INI-AUTO",
        name="Automação",
        problem_description="Problema",
        proposed_solution="Solução",
        requesting_area="Área",
        owner="Pessoa",
        priority="Alta",
        expected_impact_level="Alto",
        expected_impact_description="Impacto",
        complexity="Média",
        created_date=date.today(),
        deadline=None,
        status="Ativa",
        current_stage="Descoberta",
        planned_cost=Decimal("1000"),
        expected_benefit=Decimal("2000"),
        notes="",
        last_activity_at=datetime.now(),
    )


def test_annual_budget_and_document_alerts(session):
    item = initiative()
    session.add_all(
        [
            item,
            AnnualBudget(year=date.today().year, planned_amount=Decimal("100"), notes=""),
            GateCriterionDefinition(
                code="DISC_DOCUMENT",
                name="Documento de descoberta anexado",
                description="Documento obrigatório",
                stage="Descoberta",
                mandatory=True,
                evaluation_type="Automática",
                display_order=1,
                active=True,
            ),
        ]
    )
    session.flush()
    session.add(
        Expense(
            initiative_id=item.id,
            competence_date=date.today(),
            category="Consultoria",
            description="Custo",
            supplier="",
            tool_name="",
            cost_type="Pontual",
            financial_status="Realizado",
            amount=Decimal("90"),
        )
    )
    session.flush()
    alerts = AutomationService(session, Settings(annual_budget_warning_percent=85)).run(
        persist=False
    )
    kinds = {alert.notification_type for alert in alerts}
    assert "orcamento_anual_proximo" in kinds
    assert "documentacao_pendente" in kinds
