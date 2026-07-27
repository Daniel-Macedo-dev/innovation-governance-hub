from datetime import date
from decimal import Decimal

from innovation_governance_hub.persistence.models import AnnualBudget
from innovation_governance_hub.services.budget_service import BudgetService


def expense(month, amount, status="Realizado"):
    return {
        "initiative_id": None,
        "competence_date": date(2026, month, 1),
        "category": "Consultoria",
        "description": f"Despesa {month}",
        "supplier": "Demo",
        "tool_name": "",
        "cost_type": "Pontual",
        "financial_status": status,
        "amount": Decimal(amount),
        "actor": "Daniel",
    }


def test_partial_year_projection_and_commitments(session):
    session.add(AnnualBudget(year=2026, planned_amount=Decimal("1200"), notes=""))
    service = BudgetService(session)
    for month, amount in [(1, "100"), (2, "200"), (3, "300")]:
        service.save_expense(expense(month, amount))
    service.save_expense(expense(8, "150", "Previsto"))
    result = service.projection(2026, date(2026, 3, 20))
    assert result["monthly_average"] == Decimal("200")
    assert result["recent_three_month_average"] == Decimal("200")
    assert result["committed"] == Decimal("750")
    assert result["balance_after_commitments"] == Decimal("450")
    assert result["year_end_projection"] == Decimal("2550")


def test_projection_handles_empty_zero_and_complete_year(session):
    service = BudgetService(session)
    empty = service.projection(2026, date(2026, 4, 1))
    assert empty["year_end_projection"] == 0
    assert empty["variance_percent"] == 0
    service.save_expense(expense(12, "120"))
    complete = service.projection(2026, date(2026, 12, 31))
    assert complete["future_months"] == 0
    assert complete["year_end_projection"] == Decimal("120")
