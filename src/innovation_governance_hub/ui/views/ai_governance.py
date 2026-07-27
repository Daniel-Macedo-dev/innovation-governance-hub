from datetime import date, timedelta

import streamlit as st

from innovation_governance_hub.exceptions import DomainError
from innovation_governance_hub.ui.context import app_services
from innovation_governance_hub.ui.navigation import selected

RISK_LEVELS = ["Baixo", "Médio", "Alto", "Crítico"]
DECISION_STATUSES = [
    "Em avaliação",
    "Em revisão",
    "Aprovado",
    "Aprovado com restrições",
    "Rejeitado",
    "Suspenso",
]


def _register_form() -> None:
    with st.expander("Cadastrar caso de IA"):
        with st.form("new_ai_case"):
            code = st.text_input("Código (ex.: IA-013)")
            name = st.text_input("Nome do caso")
            area = st.text_input("Área responsável")
            owner = st.text_input("Responsável")
            objective = st.text_area("Objetivo")
            tool = st.text_input("Ferramenta ou solução avaliada")
            provider = st.text_input("Provedor ou modelo proposto")
            data_description = st.text_area("Descrição dos dados envolvidos")
            uses_personal = st.checkbox("Utiliza dados pessoais")
            risk = st.selectbox("Nível de risco", RISK_LEVELS, index=1)
            mitigation = st.text_area("Mitigações previstas")
            impact = st.text_area("Impacto esperado")
            estimated = st.number_input("Usuários estimados", min_value=0, value=0)
            active = st.number_input("Usuários ativos", min_value=0, value=0)
            review = st.date_input("Próxima revisão", value=date.today() + timedelta(days=90))
            notes = st.text_area("Observações")
            actor = st.text_input("Cadastrado por", value="Usuário local")
            if st.form_submit_button("Cadastrar caso"):
                try:
                    with app_services() as services:
                        services.ai_governance.save(
                            {
                                "code": code,
                                "name": name,
                                "responsible_area": area,
                                "owner": owner,
                                "objective": objective,
                                "ai_tool": tool,
                                "model_or_provider": provider,
                                "data_description": data_description,
                                "uses_personal_data": uses_personal,
                                "risk_level": risk,
                                "risk_mitigation": mitigation,
                                "expected_impact": impact,
                                "evaluation_status": "Em avaliação",
                                "estimated_users": int(estimated),
                                "active_users": int(active),
                                "next_review_date": review,
                                "notes": notes,
                                "actor": actor,
                            }
                        )
                    st.success("Caso de IA cadastrado para avaliação.")
                    st.rerun()
                except DomainError as exc:
                    st.error(str(exc))


def _decision_form(detail: dict[str, object]) -> None:
    st.markdown("**Registrar decisão de governança**")
    st.caption(
        "A avaliação e a aprovação são sempre decisões humanas registradas com justificativa; "
        "o sistema apenas valida a consistência e guarda o histórico."
    )
    with st.form(f"decision_{detail['id']}"):
        status = st.selectbox(
            "Novo status",
            DECISION_STATUSES,
            index=DECISION_STATUSES.index(str(detail["evaluation_status"]))
            if str(detail["evaluation_status"]) in DECISION_STATUSES
            else 0,
        )
        governance_approved = st.checkbox(
            "Aprovação da governança", value=bool(detail["governance_approved"])
        )
        policy_accepted = st.checkbox(
            "Aceite das políticas de uso", value=bool(detail["policy_accepted"])
        )
        restrictions = st.text_area("Restrições (obrigatórias para aprovação com restrições)")
        justification = st.text_area("Justificativa da decisão")
        review_value = detail["next_review_date"]
        if not isinstance(review_value, date):
            review_value = date.today() + timedelta(days=90)
        review = st.date_input("Próxima revisão", value=review_value)
        actor = st.text_input("Decidido por", value="Usuário local")
        if st.form_submit_button("Registrar decisão"):
            try:
                with app_services() as services:
                    services.ai_governance.save(
                        {
                            "code": detail["code"],
                            "name": detail["name"],
                            "evaluation_status": status,
                            "governance_approved": governance_approved,
                            "policy_accepted": policy_accepted,
                            "next_review_date": review,
                            "restrictions": restrictions,
                            "justification": justification,
                            "actor": actor,
                        },
                        int(str(detail["id"])),
                    )
                st.success("Decisão registrada no histórico de governança.")
                st.rerun()
            except DomainError as exc:
                st.error(str(exc))


def ai_governance() -> None:
    st.caption(
        "Governança dos casos de uso de IA da organização: risco, dados, adoção e aprovação. "
        "O produto não executa IA; ele controla as iniciativas de IA avaliadas pelo comitê."
    )
    _register_form()
    with app_services(read_only=True) as services:
        items = services.ai_query.list()
    st.dataframe(
        [
            {
                "Código": item["code"],
                "Nome": item["name"],
                "Risco": item["risk_level"],
                "Status": item["evaluation_status"],
                "Aprovado pela governança": "Sim" if item["governance_approved"] else "Não",
                "Dados pessoais": "Sim" if item["uses_personal_data"] else "Não",
                "Adoção": f"{item['adoption']:.1f}%",
                "Revisão vencida": "Sim" if item["review_overdue"] else "Não",
            }
            for item in items
        ],
        use_container_width=True,
        hide_index=True,
    )
    if not items:
        st.info("Nenhum caso de IA cadastrado.")
        return
    ids = [int(str(item["id"])) for item in items]
    target = selected("selected_ai_case_id", ids, ids[0])
    options = {f"{item['code']} — {item['name']}": int(str(item["id"])) for item in items}
    labels = list(options)
    label = st.selectbox("Caso de IA", labels, index=ids.index(target) if target in ids else 0)
    with app_services(read_only=True) as services:
        detail = services.ai_query.detail(options[label])
    if not detail:
        st.error("Caso de IA não encontrado.")
        return
    st.subheader(f"{detail['code']} — {detail['name']}")
    metrics = st.columns(4)
    metrics[0].metric("Nível de risco", str(detail["risk_level"]))
    metrics[1].metric("Status da avaliação", str(detail["evaluation_status"]))
    metrics[2].metric("Aprovação da governança", "Sim" if detail["governance_approved"] else "Não")
    metrics[3].metric(
        "Adoção",
        f"{detail['adoption']:.1f}%",
        help="Cálculo: usuários ativos ÷ usuários estimados × 100.",
    )
    st.write(
        f"Responsável: **{detail['owner'] or '—'}** · Área: {detail['responsible_area']} · "
        f"Usuários: {detail['active_users']} ativos de {detail['estimated_users']} estimados · "
        f"Próxima revisão: {detail['next_review_date'] or 'Não definida'}"
        + (" (vencida)" if detail["review_overdue"] else "")
    )
    st.write(f"Objetivo: {detail['objective'] or '—'}")
    st.write(
        f"Ferramenta: {detail['ai_tool'] or '—'} · Provedor proposto: "
        f"{detail['model_or_provider'] or '—'}"
    )
    st.write(
        f"Dados: {detail['data_description'] or '—'} · Dados pessoais: "
        f"{'Sim' if detail['uses_personal_data'] else 'Não'}"
    )
    st.write(f"Mitigações: {detail['risk_mitigation'] or 'Não registradas'}")
    if detail["notes"]:
        st.write(f"Observações: {detail['notes']}")
    _decision_form(detail)
    decisions = detail["decisions"]
    if decisions:
        st.markdown("**Histórico decisório**")
        st.dataframe(
            [
                {
                    "Data": item["decided_at"],
                    "De": item["previous_status"] or "—",
                    "Para": item["new_status"],
                    "Risco": item["risk_level"],
                    "Governança": "Sim" if item["governance_approved"] else "Não",
                    "Responsável": item["responsible"],
                    "Justificativa": item["justification"] or "—",
                    "Restrições": item["restrictions"] or "—",
                }
                for item in decisions
            ],
            use_container_width=True,
            hide_index=True,
        )
