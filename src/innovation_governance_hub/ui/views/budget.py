import streamlit as st

from innovation_governance_hub.domain.clock import business_date
from innovation_governance_hub.ui.components import metric_row
from innovation_governance_hub.ui.context import app_services
from innovation_governance_hub.ui.formatting import brl


def budget() -> None:
    year = st.number_input("Ano", 2020, 2100, business_date().year)
    with app_services(read_only=True) as services:
        data = services.budget_query.load(int(year))
    value = data["projection"]
    metric_row(
        [
            ("Planejado", brl(value["planned"])),
            ("Realizado", brl(value["actual"])),
            ("Previsto", brl(value["forecast"])),
            ("Comprometido", brl(value["committed"])),
            ("Saldo após compromissos", brl(value["balance_after_commitments"])),
            ("Projeção até dezembro", brl(value["year_end_projection"])),
        ]
    )
    st.caption(
        "Projeção simples demonstrativa: realizado + previsto + média recente nos meses futuros."
    )
    st.dataframe(
        [
            {
                "Data": row["competence_date"],
                "Categoria": row["category"],
                "Descrição": row["description"],
                "Status": row["financial_status"],
                "Valor": brl(row["amount"]),
            }
            for row in data["expenses"]
        ],
        use_container_width=True,
        hide_index=True,
    )
