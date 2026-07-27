import streamlit as st

from innovation_governance_hub.config import get_settings
from innovation_governance_hub.ui.context import app_services


def executive_committee() -> None:
    period = st.selectbox(
        "Mudanças desde", (7, 15, 30), index=1, format_func=lambda value: f"Últimos {value} dias"
    )
    with app_services() as services:
        brief = services.executive.brief(period)
    settings = get_settings()
    st.caption(
        f"{settings.demo_company_name} · Posição em {brief.position_date} · Dados totalmente fictícios"
    )
    st.info(brief.narrative)
    columns = st.columns(4)
    columns[0].metric("Iniciativas ativas", brief.active_initiatives)
    columns[1].metric("Decisões pendentes", len(brief.decisions))
    columns[2].metric("Itens críticos", sum(item.status == "Crítica" for item in brief.health))
    columns[3].metric("Próximas ações", len(brief.next_actions))
    st.subheader("Decisões requeridas")
    if not brief.decisions:
        st.success("Nenhuma decisão pendente para os critérios configurados.")
    for item in brief.decisions:
        with st.expander(f"{item.severity} · {item.kind} · {item.entity}"):
            st.write(item.reason)
            st.caption(f"Responsável: {item.owner} · Prazo: {item.deadline}")
            st.write(f"Ação recomendada: {item.recommendation}")
    st.subheader("Saúde do portfólio")
    st.dataframe(
        [
            {"Iniciativa": item.name, "Saúde": item.status, "Motivos": "; ".join(item.reasons)}
            for item in brief.health
        ],
        use_container_width=True,
        hide_index=True,
    )
    left, right = st.columns(2)
    with left:
        st.subheader("Resumo financeiro")
        for metric in brief.financial:
            st.metric(metric.label, metric.value)
    with right:
        st.subheader("Governança de IA")
        for metric in brief.ai:
            st.metric(metric.label, metric.value)
    st.subheader("Indicadores de resultado")
    indicator_columns = st.columns(len(brief.indicators))
    for column, metric in zip(indicator_columns, brief.indicators, strict=True):
        column.metric(metric.label, metric.value)
    st.subheader("Próximas ações")
    st.dataframe(
        [
            {
                "Pendência": item.entity,
                "Situação": item.reason,
                "Responsável": item.owner,
                "Prazo": item.deadline,
            }
            for item in brief.next_actions
        ],
        use_container_width=True,
        hide_index=True,
    )
    st.subheader("Mudanças desde a última revisão")
    for change in brief.changes:
        st.write(f"• {change}")
    st.download_button(
        "Baixar resumo (Markdown)",
        data=f"# Comitê de Inovação\n\n> Dados fictícios.\n\n{brief.narrative}\n",
        file_name="resumo_comite_inovacao.md",
        mime="text/markdown",
    )
