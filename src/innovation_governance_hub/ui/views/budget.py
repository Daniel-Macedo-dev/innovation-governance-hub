from decimal import Decimal

import streamlit as st

from innovation_governance_hub.domain.clock import business_date
from innovation_governance_hub.exceptions import DomainError
from innovation_governance_hub.ui.components import Metric, metric_row
from innovation_governance_hub.ui.context import app_services
from innovation_governance_hub.ui.formatting import brl, compact_brl


def _money_metric(label: str, amount: object) -> Metric:
    return Metric(label, compact_brl(amount), help=f"Valor exato: {brl(amount)}")  # type: ignore[arg-type]


CATEGORIES = [
    "Ferramentas e software",
    "Fornecedores",
    "Consultoria",
    "Infraestrutura",
    "Treinamento",
    "Outros",
]


def budget() -> None:
    year = st.number_input("Ano", 2020, 2100, business_date().year)
    with app_services(read_only=True) as services:
        data = services.budget_query.load(int(year))
    value = data["projection"]
    with st.expander("Definir orçamento anual"):
        with st.form("annual_budget"):
            amount = st.number_input(
                "Orçamento planejado (R$)", min_value=0.0, value=float(value["planned"])
            )
            notes = st.text_input("Observações")
            actor = st.text_input("Definido por", value="Usuário local")
            if st.form_submit_button("Salvar orçamento"):
                try:
                    with app_services() as services:
                        services.budget.set_annual_budget(
                            int(year), Decimal(str(amount)), notes, actor
                        )
                    st.success("Orçamento anual salvo.")
                    st.rerun()
                except DomainError as exc:
                    st.error(str(exc))
    with st.expander("Registrar despesa"):
        initiative_options = {"Sem vínculo": None} | {
            f"{item['code']} — {item['name']}": int(str(item["id"])) for item in data["initiatives"]
        }
        with st.form("new_expense"):
            linked = st.selectbox("Iniciativa vinculada", list(initiative_options))
            competence = st.date_input("Data de competência", value=business_date())
            category = st.selectbox("Categoria", CATEGORIES)
            description = st.text_input("Descrição")
            supplier = st.text_input("Fornecedor")
            tool = st.text_input("Ferramenta")
            cost_type = st.selectbox("Tipo de custo", ["Pontual", "Recorrente"])
            financial_status = st.selectbox("Status financeiro", ["Realizado", "Previsto"])
            amount = st.number_input("Valor (R$)", min_value=0.0)
            actor = st.text_input("Registrado por", value="Usuário local")
            if st.form_submit_button("Registrar despesa"):
                try:
                    with app_services() as services:
                        services.budget.save_expense(
                            {
                                "initiative_id": initiative_options[linked],
                                "competence_date": competence,
                                "category": category,
                                "description": description,
                                "supplier": supplier,
                                "tool_name": tool,
                                "cost_type": cost_type,
                                "financial_status": financial_status,
                                "amount": Decimal(str(amount)),
                                "actor": actor,
                            }
                        )
                    st.success("Despesa registrada.")
                    st.rerun()
                except DomainError as exc:
                    st.error(str(exc))
    metric_row(
        [
            _money_metric("Planejado", value["planned"]),
            _money_metric("Realizado", value["actual"]),
            _money_metric("Previsto", value["forecast"]),
            _money_metric("Comprometido", value["committed"]),
            _money_metric("Saldo após compromissos", value["balance_after_commitments"]),
            _money_metric("Projeção até dezembro", value["year_end_projection"]),
        ]
    )
    st.caption(
        "Projeção simples: realizado + previsto + média dos três últimos meses aplicada aos "
        "meses futuros. Origem: despesas por competência e orçamento anual cadastrado."
    )
    if data["over_budget"]:
        st.subheader("Iniciativas acima do custo planejado")
        st.dataframe(
            [
                {
                    "Código": item["code"],
                    "Iniciativa": item["name"],
                    "Planejado": brl(item["planned_cost"]),
                    "Realizado": brl(item["actual_cost"]),
                }
                for item in data["over_budget"]
            ],
            use_container_width=True,
            hide_index=True,
        )
    if data["categories"]:
        st.subheader("Custos por categoria")
        st.dataframe(
            [
                {
                    "Categoria": item["category"],
                    "Realizado": brl(item["actual"]),
                    "Previsto": brl(item["forecast"]),
                    "Total": brl(item["total"]),
                }
                for item in data["categories"]
            ],
            use_container_width=True,
            hide_index=True,
        )
    st.subheader("Despesas do período")
    st.dataframe(
        [
            {
                "Data": row["competence_date"],
                "Categoria": row["category"],
                "Descrição": row["description"],
                "Ferramenta": row["tool_name"] or "—",
                "Recorrência": row["cost_type"],
                "Status": row["financial_status"],
                "Valor": brl(row["amount"]),
            }
            for row in data["expenses"]
        ],
        use_container_width=True,
        hide_index=True,
    )
