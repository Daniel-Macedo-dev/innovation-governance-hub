import pandas as pd
import plotly.express as px
import streamlit as st

from innovation_governance_hub.ui.components import metric_row
from innovation_governance_hub.ui.context import app_services
from innovation_governance_hub.ui.formatting import brl


def overview() -> None:
    with app_services(read_only=True) as services:
        data = services.overview_query.load()
    budget = data["budget"]
    metric_row(
        [
            ("Iniciativas", len(data["initiatives"])),
            ("Projetos ativos", data["active"]),
            ("Atrasados", data["overdue"]),
            ("Orçamento", brl(budget["planned"])),
            ("Gasto realizado", brl(budget["actual"])),
            ("Casos de IA", data["ai_total"]),
        ]
    )
    frame = pd.DataFrame(data["initiatives"])
    if not frame.empty:
        st.plotly_chart(
            px.histogram(
                frame, x="current_stage", color="requesting_area", title="Iniciativas por estágio"
            ),
            use_container_width=True,
        )
    st.caption("Leitura executiva sem atualização automática de alertas.")
