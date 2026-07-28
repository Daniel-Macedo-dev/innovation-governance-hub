import pandas as pd
import plotly.express as px
import streamlit as st

from innovation_governance_hub.domain.clock import business_date
from innovation_governance_hub.services.ui_query_services import AreaDeliveryMetric
from innovation_governance_hub.ui.components import Metric, metric_row
from innovation_governance_hub.ui.context import app_services
from innovation_governance_hub.ui.formatting import brl, compact_brl

BAR_COLOR = "#3E6D9C"


def _area_frame(metrics: list[AreaDeliveryMetric]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Área": metric.area,
                "Ativos": metric.active,
                "No prazo": metric.on_time,
                "Atrasados": metric.overdue,
                "Sem prazo": metric.no_deadline,
                "% no prazo": metric.on_time_percentage,
                "rotulo_percentual": f"{metric.on_time_percentage:.1f}%".replace(".", ","),
            }
            for metric in metrics
        ]
    )


def _active_by_area_chart(frame: pd.DataFrame, order: list[str]):
    chart = px.bar(
        frame,
        x="Área",
        y="Ativos",
        title="Projetos ativos por área",
        text="Ativos",
        category_orders={"Área": order},
        color_discrete_sequence=[BAR_COLOR],
    )
    chart.update_traces(
        textposition="outside",
        cliponaxis=False,
        hovertemplate="%{x}<br>Ativos: %{y}<extra></extra>",
    )
    chart.update_layout(
        yaxis_title="Projetos ativos", showlegend=False, margin={"t": 70, "r": 20, "b": 60, "l": 55}
    )
    return chart


def _on_time_by_area_chart(frame: pd.DataFrame, order: list[str]):
    chart = px.bar(
        frame,
        x="Área",
        y="% no prazo",
        title="Projetos dentro do prazo por área",
        text="rotulo_percentual",
        category_orders={"Área": order},
        color_discrete_sequence=[BAR_COLOR],
        custom_data=["Ativos", "No prazo", "Atrasados", "Sem prazo", "rotulo_percentual"],
    )
    chart.update_traces(
        textposition="outside",
        cliponaxis=False,
        hovertemplate=(
            "%{x}<br>Ativos: %{customdata[0]}<br>No prazo: %{customdata[1]}"
            "<br>Atrasados: %{customdata[2]}<br>Sem prazo: %{customdata[3]}"
            "<br>% no prazo: %{customdata[4]}<extra></extra>"
        ),
    )
    chart.update_yaxes(
        title_text="% dentro do prazo",
        range=[0, 115],
        tickmode="array",
        tickvals=[0, 20, 40, 60, 80, 100],
        ticksuffix="%",
    )
    chart.update_layout(showlegend=False, margin={"t": 70, "r": 20, "b": 60, "l": 55})
    return chart


def overview() -> None:
    with app_services(read_only=True) as services:
        data = services.overview_query.load()
    budget = data["budget"]
    metric_row(
        [
            Metric("Iniciativas", len(data["initiatives"])),
            Metric("Projetos ativos", data["active"]),
            Metric("Atrasados", data["overdue"]),
            Metric(
                "Orçamento",
                compact_brl(budget["planned"]),
                help=f"Valor exato: {brl(budget['planned'])}",
            ),
            Metric(
                "Gasto realizado",
                compact_brl(budget["actual"]),
                help=f"Valor exato: {brl(budget['actual'])}",
            ),
            Metric("Casos de IA", data["ai_total"]),
        ]
    )
    metrics: list[AreaDeliveryMetric] = data["area_delivery"]
    if metrics:
        frame = _area_frame(metrics)
        order = [metric.area for metric in metrics]
        left, right = st.columns(2)
        with left:
            st.plotly_chart(_active_by_area_chart(frame, order), use_container_width=True)
        with right:
            st.plotly_chart(_on_time_by_area_chart(frame, order), use_container_width=True)
        st.caption(
            "Projeto ativo: iniciativa que não está concluída nem arquivada. "
            "Percentual dentro do prazo: ativos com prazo igual ou posterior à data de negócio "
            "÷ total de ativos da área × 100; iniciativas sem prazo reduzem o percentual. "
            f"Posição em {business_date():%d/%m/%Y}."
        )
    initiatives = pd.DataFrame(data["initiatives"])
    if not initiatives.empty:
        st.plotly_chart(
            px.histogram(
                initiatives,
                x="current_stage",
                color="requesting_area",
                title="Iniciativas por estágio",
                labels={
                    "current_stage": "Estágio",
                    "requesting_area": "Área solicitante",
                },
            ).update_yaxes(title_text="Iniciativas"),
            use_container_width=True,
        )
    st.caption("Leitura executiva sem atualização automática de alertas.")
