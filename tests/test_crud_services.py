from datetime import date
from decimal import Decimal

import pytest

from innovation_governance_hub.exceptions import ValidationError
from innovation_governance_hub.persistence.models import Initiative
from innovation_governance_hub.services.ai_governance_service import AIUseCaseService
from innovation_governance_hub.services.budget_service import BudgetService


def initiative():
    return Initiative(
        code="INI-CRUD",
        name="CRUD",
        problem_description="Problema",
        proposed_solution="Solução",
        requesting_area="Área",
        owner="Pessoa",
        priority="Média",
        expected_impact_level="Médio",
        expected_impact_description="",
        complexity="Média",
        created_date=date.today(),
        deadline=None,
        status="Ativa",
        current_stage="Ideia",
        planned_cost=Decimal("10"),
        expected_benefit=Decimal("20"),
        notes="",
    )


def ai_data():
    return {
        "code": "IA-CRUD",
        "name": "Caso CRUD",
        "responsible_area": "Tecnologia",
        "objective": "Teste",
        "ai_tool": "Ferramenta",
        "model_or_provider": "Local",
        "data_description": "Dados fictícios",
        "uses_personal_data": False,
        "risk_level": "Baixo",
        "risk_mitigation": "Revisão",
        "expected_impact": "Teste",
        "evaluation_status": "Rascunho",
        "owner": "Pessoa",
        "next_review_date": None,
        "policy_accepted": False,
        "governance_approved": False,
        "estimated_users": 10,
        "active_users": 5,
        "notes": "",
    }


def test_ai_crud_and_adoption_bounds(session):
    service = AIUseCaseService(session)
    case = service.save(ai_data())
    assert case.id
    changed = ai_data()
    changed["name"] = "Editado"
    service.save(changed, case.id)
    assert case.name == "Editado"
    invalid = ai_data()
    invalid["active_users"] = 11
    with pytest.raises(ValidationError):
        service.save(invalid)
    with pytest.raises(ValidationError, match="preservam histórico"):
        service.delete(case.id)
    assert session.get(type(case), case.id) is case


def test_expense_crud_and_positive_amount(session):
    item = initiative()
    session.add(item)
    session.flush()
    service = BudgetService(session)
    data = {
        "initiative_id": item.id,
        "competence_date": date.today(),
        "category": "Consultoria",
        "description": "Teste",
        "supplier": "Fornecedor",
        "tool_name": "",
        "cost_type": "Pontual",
        "financial_status": "Realizado",
        "amount": Decimal("100"),
    }
    expense = service.save_expense(data)
    assert expense.amount == Decimal("100")
    data["amount"] = Decimal("120")
    service.save_expense(data, expense.id)
    assert expense.amount == Decimal("120")
    data["amount"] = 0
    with pytest.raises(ValidationError):
        service.save_expense(data)
    service.delete_expense(expense.id)
    session.flush()
    assert session.get(type(expense), expense.id) is None
