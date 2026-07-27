from decimal import Decimal

import pytest

from innovation_governance_hub.exceptions import ValidationError
from innovation_governance_hub.services.initiative_service import InitiativeService


def data():
    return {
        "name": "Nova",
        "problem_description": "Problema",
        "proposed_solution": "Solução",
        "requesting_area": "Operações",
        "owner": "Pessoa",
        "priority": "Alta",
        "expected_impact_level": "Alto",
        "expected_impact_description": "Impacto",
        "complexity": "Média",
        "deadline": None,
        "planned_cost": Decimal("100"),
    }


def test_create_and_update_initiative(session):
    service = InitiativeService(session)
    item = service.create(data())
    assert item.code == "INI-001"
    changed = data()
    changed["name"] = "Editada"
    service.update(item.id, changed)
    assert item.name == "Editada"


def test_rejects_incomplete_or_negative(session):
    invalid = data()
    invalid["owner"] = ""
    with pytest.raises(ValidationError):
        InitiativeService(session).create(invalid)
    invalid = data()
    invalid["planned_cost"] = -1
    with pytest.raises(ValidationError):
        InitiativeService(session).create(invalid)
