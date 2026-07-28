"""Visão Geral renderizada: cards compactos sem reticências e cenário preservado."""

from streamlit.testing.v1 import AppTest

from scripts.seed_demo import seed


def test_overview_cards_are_compact_without_ellipsis(monkeypatch):
    monkeypatch.setenv("DEMO_REFERENCE_DATE", "2026-07-27")
    from innovation_governance_hub.config import get_settings

    get_settings.cache_clear()
    # Garante esquema atual no banco ligado ao engine da aplicação (evita arquivo legado local).
    from innovation_governance_hub.database import Base, engine

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    seed()  # popula o banco de teste ligado ao engine
    app = AppTest.from_file("app.py", default_timeout=30).run()
    get_settings.cache_clear()

    assert not app.exception
    assert app.title[0].value == "Visão Geral"
    metrics = app.metric
    assert len(metrics) == 6
    for metric in metrics:
        assert "…" not in str(metric.value)
        assert "..." not in str(metric.value)
    by_label = {metric.label: metric for metric in metrics}
    assert by_label["Orçamento"].help
    assert by_label["Gasto realizado"].help
    assert any(
        ("milhão" in str(metric.value)) or ("mil" in str(metric.value)) for metric in metrics
    )
