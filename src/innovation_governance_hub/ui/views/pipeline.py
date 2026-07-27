import streamlit as st

from innovation_governance_hub.exceptions import DomainError
from innovation_governance_hub.ui.context import app_services
from innovation_governance_hub.ui.formatting import br_date, brl
from innovation_governance_hub.ui.navigation import INITIATIVE, go


def pipeline() -> None:
    with app_services(read_only=True) as services:
        items = services.pipeline_query.list()
    with st.expander("Cadastrar iniciativa"):
        with st.form("new_initiative"):
            name = st.text_input("Nome")
            area = st.text_input("Área solicitante")
            owner = st.text_input("Responsável")
            problem = st.text_area("Problema")
            cost = st.number_input("Custo planejado", min_value=0.0)
            if st.form_submit_button("Cadastrar"):
                try:
                    with app_services() as services:
                        services.initiatives.create(
                            {
                                "name": name,
                                "requesting_area": area,
                                "owner": owner,
                                "problem_description": problem,
                                "planned_cost": cost,
                                "priority": "Média",
                                "expected_impact_level": "Médio",
                                "complexity": "Média",
                                "actor": "Usuário local",
                            }
                        )
                    st.success("Iniciativa cadastrada.")
                    st.rerun()
                except DomainError as exc:
                    st.error(str(exc))
    stages = sorted({str(item["current_stage"]) for item in items})
    selected_stages = st.multiselect("Estágio", stages)
    shown = [
        item for item in items if not selected_stages or item["current_stage"] in selected_stages
    ]
    st.dataframe(
        [
            {
                "Código": item["code"],
                "Nome": item["name"],
                "Área": item["requesting_area"],
                "Estágio": item["current_stage"],
                "Status": item["status"],
                "Prazo": br_date(item["deadline"]),
                "Planejado": brl(item["planned_cost"]),
                "Realizado": brl(item["actual_cost"]),
            }
            for item in shown
        ],
        use_container_width=True,
        hide_index=True,
    )
    options = {f"{item['code']} — {item['name']}": int(str(item["id"])) for item in shown}
    if options:
        target = st.selectbox("Abrir iniciativa", options)
        if st.button("Ver detalhes"):
            go(INITIATIVE, options[target])
