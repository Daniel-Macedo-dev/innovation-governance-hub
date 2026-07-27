import json
from datetime import date
from decimal import Decimal

import pytest

from innovation_governance_hub.exceptions import GateBlockedError
from innovation_governance_hub.persistence.models import AuditEvent, GateCriterionDefinition
from innovation_governance_hub.services.audit_service import AuditService
from innovation_governance_hub.services.gate_service import GateService
from innovation_governance_hub.services.initiative_service import InitiativeService


def initiative_data():
    return {
        "name": "Auditável",
        "problem_description": "Problema",
        "proposed_solution": "Solução",
        "requesting_area": "Operações",
        "owner": "Daniel",
        "priority": "Alta",
        "expected_impact_level": "Alto",
        "expected_impact_description": "Impacto",
        "complexity": "Média",
        "deadline": date(2026, 12, 1),
        "planned_cost": Decimal("100.50"),
        "actor": "Daniel",
    }


def test_creation_update_and_serialization_are_audited(session):
    service = InitiativeService(session)
    item = service.create(initiative_data())
    changed = initiative_data() | {"name": "Revisada"}
    service.update(item.id, changed)
    events = AuditService(session).timeline("Iniciativa", item.id, newest_first=False)
    assert [event.event_type for event in events] == ["initiative.created", "initiative.updated"]
    assert json.loads(events[1].changes_json)["name"]["after"] == "Revisada"
    AuditService(session).record(
        event_type="safe",
        entity_type="Teste",
        entity_id=1,
        action="teste",
        actor="Sistema",
        summary="Seguro",
        changes={"amount": Decimal("1.20"), "date": date(2026, 7, 27), "api_key": "never-store"},
    )
    payload = json.loads(session.query(AuditEvent).filter_by(event_type="safe").one().changes_json)
    assert payload == {"amount": "1.20", "date": "2026-07-27"}


def test_blocked_gate_is_audited(session):
    item = InitiativeService(session).create(initiative_data())
    item.expected_impact_level = ""
    session.add(
        GateCriterionDefinition(
            code="IDEA_IMPACT",
            name="Impacto definido",
            stage="Ideia",
            mandatory=True,
            evaluation_type="Automática",
            display_order=1,
            active=True,
        )
    )
    session.flush()
    with pytest.raises(GateBlockedError):
        GateService(session).advance(item.id, "Daniel")
    event = AuditService(session).timeline("Iniciativa", item.id)[0]
    assert event.event_type == "gate.blocked"
    assert "missing_criteria" in event.metadata_json
