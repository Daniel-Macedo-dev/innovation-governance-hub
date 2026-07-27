import pandas as pd
import plotly.express as px
import streamlit as st

from innovation_governance_hub.config import get_settings
from innovation_governance_hub.ui.context import app_services
from innovation_governance_hub.ui.navigation import INITIATIVE, go


def executive_committee() -> None:
    period = st.selectbox(
        "Mudanças desde", (7, 15, 30), index=1, format_func=lambda value: f"Últimos {value} dias"
    )
    with app_services(read_only=True) as services:
        brief = services.executive.brief(period)
        health_by_id = {item.initiative_id: item.status for item in brief.health}
        priorities = services.prioritization_query.portfolio(health_by_id)
        workbook = services.export.committee(period)
    settings = get_settings()
    st.caption(
        f"{settings.demo_company_name} · Posição em {brief.position_date} · Dados totalmente fictícios"
    )
    st.info(brief.narrative)
    columns = st.columns(6)
    columns[0].metric("Iniciativas ativas", brief.active_initiatives)
    columns[1].metric("Decisões pendentes", len(brief.decisions))
    columns[2].metric("Itens críticos", sum(item.status == "Crítica" for item in brief.health))
    columns[3].metric("Próximas ações", len(brief.next_actions))
    planned = next((item.value for item in brief.financial if item.label == "Orçamento anual"), "—")
    columns[4].metric("Orçamento anual", planned)
    columns[5].metric(
        "IA em atenção",
        next((item.value for item in brief.ai if item.label == "Alto ou crítico risco"), "0"),
    )
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
    st.subheader("Priorização do Portfólio")
    areas = st.multiselect("Área", sorted({item.area for item in priorities}))
    themes = st.multiselect("Tema estratégico", sorted({item.theme for item in priorities}))
    stages = st.multiselect("Estágio", sorted({item.stage for item in priorities}))
    health_filter = st.multiselect("Saúde", sorted({item.health for item in priorities}))
    operational_priority = st.multiselect(
        "Prioridade operacional", sorted({item.priority for item in priorities})
    )
    st.markdown("**Indicadores de resultado**")
    indicator_columns = st.columns(len(brief.indicators))
    for column, metric in zip(indicator_columns, brief.indicators, strict=True):
        column.metric(metric.label, metric.value)
    filtered = [
        item
        for item in priorities
        if (not areas or item.area in areas)
        and (not themes or item.theme in themes)
        and (not stages or item.stage in stages)
        and (not health_filter or item.health in health_filter)
        and (not operational_priority or item.priority in operational_priority)
    ]
    frame = pd.DataFrame(
        [
            {
                "id": item.initiative_id,
                "Código": item.code,
                "Iniciativa": item.name,
                "Área": item.area,
                "Tema": item.theme,
                "Estágio": item.stage,
                "Saúde": item.health,
                "Score": item.score,
                "Valor": item.value,
                "Esforço": item.effort,
                "Risco": item.risk,
                "Custo": float(item.planned_cost),
                "Quadrante": item.quadrant,
                "Responsável": item.owner,
            }
            for item in filtered
        ]
    )
    if not frame.empty:
        chart = px.scatter(
            frame,
            x="Esforço",
            y="Valor",
            size="Custo",
            color="Saúde",
            hover_data=["Código", "Iniciativa", "Área", "Score", "Risco", "Estágio", "Quadrante"],
            title="Valor × Esforço",
        )
        chart.add_vline(x=3, line_dash="dash", line_color="#6E7781")
        chart.add_hline(y=3, line_dash="dash", line_color="#6E7781")
        chart.add_annotation(x=1.4, y=4.8, text="Priorizar", showarrow=False)
        chart.add_annotation(x=4.6, y=4.8, text="Planejar", showarrow=False)
        chart.add_annotation(x=1.4, y=1.2, text="Avaliar", showarrow=False)
        chart.add_annotation(x=4.6, y=1.2, text="Reconsiderar", showarrow=False)
        st.plotly_chart(chart, use_container_width=True)
        st.dataframe(
            frame[
                [
                    "Código",
                    "Iniciativa",
                    "Tema",
                    "Score",
                    "Valor",
                    "Esforço",
                    "Saúde",
                    "Estágio",
                    "Responsável",
                ]
            ],
            use_container_width=True,
            hide_index=True,
            height=260,
        )
        options = {f"{item.code} — {item.name}": item.initiative_id for item in filtered}
        target = st.selectbox("Abrir iniciativa priorizada", options)
        if st.button("Ver priorização e indicadores"):
            go(INITIATIVE, options[target])
    else:
        st.info("Nenhuma avaliação corresponde aos filtros selecionados.")
    left, right = st.columns(2)
    with left:
        st.subheader("Resumo financeiro")
        for metric in brief.financial:
            st.metric(metric.label, metric.value)
    with right:
        st.subheader("Governança de IA")
        for metric in brief.ai:
            st.metric(metric.label, metric.value)
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
    st.download_button(
        "Baixar pacote executivo (Excel)",
        data=workbook,
        file_name="relatorio_comite_inovacao.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
