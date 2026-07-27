"""Métricas de execução por área da Visão Geral (unitário, sem banco)."""

from datetime import date

from innovation_governance_hub.persistence.models import Initiative
from innovation_governance_hub.services.ui_query_services import (
    _area_delivery_metrics,
    _is_active,
)

REFERENCE = date(2026, 7, 27)


def _initiative(area: str, status: str, deadline: date | None) -> Initiative:
    return Initiative(requesting_area=area, status=status, deadline=deadline)


def _by_area(metrics):
    return {metric.area: metric for metric in metrics}


def test_only_active_initiatives_are_counted():
    initiatives = [
        _initiative("Operações", "Ativa", date(2026, 12, 1)),
        _initiative("Operações", "Bloqueada", date(2026, 12, 1)),
        _initiative("Operações", "Concluída", date(2026, 12, 1)),
        _initiative("Operações", "Arquivada", date(2026, 12, 1)),
    ]
    metrics = _by_area(_area_delivery_metrics(initiatives, REFERENCE))
    assert metrics["Operações"].active == 2  # ativa + bloqueada; concluída/arquivada excluídas


def test_deadline_classification_uses_reference_not_today():
    initiatives = [
        _initiative("A", "Ativa", date(2026, 7, 26)),  # anterior -> atrasada
        _initiative("A", "Ativa", REFERENCE),  # igual -> no prazo
        _initiative("A", "Ativa", date(2026, 7, 28)),  # futuro -> no prazo
        _initiative("A", "Ativa", None),  # sem prazo
    ]
    metric = _by_area(_area_delivery_metrics(initiatives, REFERENCE))["A"]
    assert (metric.active, metric.on_time, metric.overdue, metric.no_deadline) == (4, 2, 1, 1)


def test_percentage_integer_decimal_and_zero_and_single():
    single_on_time = _by_area(
        _area_delivery_metrics([_initiative("A", "Ativa", date(2026, 12, 1))], REFERENCE)
    )["A"]
    assert single_on_time.on_time_percentage == 100.0

    three = _by_area(
        _area_delivery_metrics(
            [
                _initiative("A", "Ativa", date(2026, 12, 1)),
                _initiative("A", "Ativa", date(2026, 12, 1)),
                _initiative("A", "Ativa", date(2026, 1, 1)),
            ],
            REFERENCE,
        )
    )["A"]
    assert three.on_time_percentage == 66.7  # 2/3

    empty = [metric for metric in _area_delivery_metrics([], REFERENCE)]
    assert empty == []


def test_no_deadline_reduces_percentage():
    metric = _by_area(
        _area_delivery_metrics(
            [
                _initiative("A", "Ativa", date(2026, 12, 1)),
                _initiative("A", "Ativa", None),
            ],
            REFERENCE,
        )
    )["A"]
    assert metric.on_time_percentage == 50.0


def test_ordering_is_volume_desc_then_alphabetical():
    initiatives = (
        [_initiative("Beta", "Ativa", date(2026, 12, 1)) for _ in range(2)]
        + [_initiative("Alfa", "Ativa", date(2026, 12, 1)) for _ in range(2)]
        + [_initiative("Gama", "Ativa", date(2026, 12, 1)) for _ in range(3)]
    )
    metrics = _area_delivery_metrics(initiatives, REFERENCE)
    assert [metric.area for metric in metrics] == ["Gama", "Alfa", "Beta"]


def test_blank_area_is_grouped_not_dropped():
    metric = _by_area(
        _area_delivery_metrics([_initiative("", "Ativa", date(2026, 12, 1))], REFERENCE)
    )
    assert "Área não informada" in metric


def test_is_active_helper():
    assert _is_active(_initiative("A", "Ativa", None)) is True
    assert _is_active(_initiative("A", "Concluída", None)) is False
    assert _is_active(_initiative("A", "Arquivada", None)) is False
