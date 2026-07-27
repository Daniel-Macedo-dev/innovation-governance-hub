from datetime import date
from decimal import Decimal

import pytest

from innovation_governance_hub.exceptions import ValidationError
from innovation_governance_hub.persistence.models import (
    Initiative,
    InitiativeAssessment,
    InitiativeIndicator,
)
from innovation_governance_hub.services.indicator_service import IndicatorService
from innovation_governance_hub.services.prioritization_service import PrioritizationService


def initiative(session):
    item = Initiative(
        code="INI-001",
        name="Teste",
        problem_description="Problema",
        requesting_area="Área",
        owner="Pessoa",
        priority="Alta",
        expected_impact_level="Alto",
        complexity="Média",
        created_date=date(2026, 1, 1),
        status="Ativa",
        current_stage="Ideia",
        planned_cost=Decimal(100),
        expected_benefit=Decimal(200),
    )
    session.add(item)
    session.flush()
    return item


def assessment(item, value: int, effort: int) -> InitiativeAssessment:
    return InitiativeAssessment(
        initiative_id=item.id,
        strategic_alignment=value,
        expected_value=value,
        urgency=value,
        confidence=value,
        complexity=effort,
        execution_risk=effort,
        rationale="Transparente",
        assessed_by="Daniel",
    )


def test_priority_score_bounds_weights_and_quadrants(session):
    item = initiative(session)
    low = PrioritizationService.calculate(assessment(item, 1, 5))
    high = PrioritizationService.calculate(assessment(item, 5, 1))
    assert low.score == 0 and low.quadrant == "Reconsiderar"
    assert high.score == 100 and high.quadrant == "Priorizar"
    assert sum(PrioritizationService.VALUE_WEIGHTS.values()) == 1
    assert sum(PrioritizationService.EFFORT_WEIGHTS.values()) == 1
    with pytest.raises(ValidationError):
        PrioritizationService.calculate(assessment(item, 0, 2))


def test_priority_save_updates_and_audits(session):
    item = initiative(session)
    service = PrioritizationService(session)
    data = {
        "strategic_alignment": 5,
        "expected_value": 4,
        "urgency": 4,
        "confidence": 4,
        "complexity": 2,
        "execution_risk": 2,
        "rationale": "Valor relevante",
    }
    assert service.save(item.id, data, "Daniel").score > 70
    data["complexity"] = 5
    assert service.save(item.id, data, "Daniel").score < 80
    assert len(service.list_ranked()) == 1


@pytest.mark.parametrize(
    ("direction", "current", "expected"),
    [
        ("Aumentar", Decimal(90), "No caminho"),
        ("Reduzir", Decimal(60), "Atenção"),
        ("Aumentar", Decimal(20), "Fora do esperado"),
    ],
)
def test_indicator_status_directions(session, direction, current, expected):
    item = initiative(session)
    indicator = InitiativeIndicator(
        initiative_id=item.id,
        name="Tempo",
        unit="Horas",
        baseline_value=Decimal(100) if direction == "Reduzir" else Decimal(0),
        target_value=Decimal(20) if direction == "Reduzir" else Decimal(100),
        current_value=current,
        direction=direction,
        owner="Pessoa",
    )
    session.add(indicator)
    session.flush()
    assert IndicatorService.status(indicator).status == expected


def test_indicator_missing_and_equal_target(session):
    item = initiative(session)
    missing = InitiativeIndicator(
        initiative_id=item.id,
        name="Índice",
        unit="Índice",
        baseline_value=Decimal(0),
        target_value=Decimal(0),
        current_value=None,
        direction="Aumentar",
        owner="Pessoa",
    )
    session.add(missing)
    session.flush()
    assert IndicatorService.status(missing).status == "Sem medição"
    missing.current_value = Decimal(0)
    assert IndicatorService.status(missing).progress_percent == 100
