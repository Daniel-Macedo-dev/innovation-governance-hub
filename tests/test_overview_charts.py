"""Contrato das figuras Plotly da Visão Geral (sem prender a pixels internos)."""

from innovation_governance_hub.services.ui_query_services import AreaDeliveryMetric
from innovation_governance_hub.ui.views.overview import (
    _active_by_area_chart,
    _area_frame,
    _on_time_by_area_chart,
)

METRICS = [
    AreaDeliveryMetric("Operações", active=5, on_time=3, overdue=2, no_deadline=0),
    AreaDeliveryMetric("Pessoas", active=3, on_time=3, overdue=0, no_deadline=0),
    AreaDeliveryMetric("Financeiro", active=3, on_time=2, overdue=0, no_deadline=1),
]
ORDER = [m.area for m in METRICS]


def _frame():
    return _area_frame(METRICS)


def test_on_time_chart_leaves_headroom_for_outside_labels():
    chart = _on_time_by_area_chart(_frame(), ORDER)
    assert chart.layout.title.text == "Projetos dentro do prazo por área"
    # Espaço acima de 100 apenas para o rótulo externo, sem sugerir >100%.
    assert tuple(chart.layout.yaxis.range) == (0, 115)
    assert max(chart.layout.yaxis.tickvals) == 100
    trace = chart.data[0]
    assert trace.textposition == "outside"
    assert trace.cliponaxis is False


def test_on_time_chart_keeps_percentages_and_tooltip():
    chart = _on_time_by_area_chart(_frame(), ORDER)
    labels = list(chart.data[0].text)
    assert "100,0%" in labels
    assert "60,0%" in labels  # Operações 3/5
    assert "66,7%" in labels  # Financeiro 2/3
    hovertemplate = chart.data[0].hovertemplate
    for field in ("Ativos", "No prazo", "Atrasados", "Sem prazo", "% no prazo"):
        assert field in hovertemplate


def test_on_time_chart_is_neutral():
    chart = _on_time_by_area_chart(_frame(), ORDER)
    assert len(chart.layout.annotations) == 0
    colors = {trace.marker.color for trace in chart.data}
    assert len(colors) == 1  # cor única, sem destaque por área


def test_active_chart_contract():
    chart = _active_by_area_chart(_frame(), ORDER)
    assert chart.layout.title.text == "Projetos ativos por área"
    trace = chart.data[0]
    assert trace.cliponaxis is False
    assert list(chart.layout.xaxis.categoryarray) == ORDER


def test_both_charts_share_area_order():
    active = _active_by_area_chart(_frame(), ORDER)
    on_time = _on_time_by_area_chart(_frame(), ORDER)
    assert list(active.layout.xaxis.categoryarray) == list(on_time.layout.xaxis.categoryarray)
