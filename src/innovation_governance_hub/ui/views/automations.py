from datetime import date, timedelta

import streamlit as st

from innovation_governance_hub.exceptions import DomainError
from innovation_governance_hub.ui.context import app_services
from innovation_governance_hub.ui.navigation import AI_CASE, INITIATIVE, go

# Rótulos legíveis para os identificadores persistidos de entidade.
ENTITY_LABELS = {
    "Iniciativa": "Iniciativa",
    "CasoIA": "Caso de IA",
    "Pendencia": "Pendência",
    "OrcamentoAnual": "Orçamento anual",
}


def automations() -> None:
    st.caption(
        "Verificações internas calculam alertas de prazo, orçamento, gates, governança de IA e pendências. "
        "A execução é sempre explícita: abrir dashboards não gera nem altera alertas."
    )
    if st.button("Executar verificações"):
        with app_services() as services:
            alerts = services.automations.run()
        st.success(f"{len(alerts)} alertas detectados.")
        st.rerun()
    with app_services(read_only=True) as services:
        items = services.automation_query.list()
    statuses = st.multiselect("Status", ["Novo", "Reconhecido", "Resolvido", "Ignorado"])
    severities = st.multiselect("Severidade", sorted({str(item["severity"]) for item in items}))
    types = st.multiselect("Tipo", sorted({str(item["notification_type"]) for item in items}))
    entity_values = sorted({str(item["entity_type"]) for item in items})
    label_by_value = {value: ENTITY_LABELS.get(value, value) for value in entity_values}
    entity_labels = st.multiselect("Entidade", list(label_by_value.values()))
    entities = {value for value, label in label_by_value.items() if label in entity_labels}
    period = st.selectbox(
        "Período", (7, 15, 30, 90), index=2, format_func=lambda value: f"{value} dias"
    )
    cutoff = date.today() - timedelta(days=period)
    shown = [
        item
        for item in items
        if (not statuses or item["lifecycle_status"] in statuses)
        and (not severities or item["severity"] in severities)
        and (not types or item["notification_type"] in types)
        and (not entities or item["entity_type"] in entities)
        and item["detected_at"].date() >= cutoff
    ]
    counts = {
        status: sum(item["lifecycle_status"] == status for item in items)
        for status in ("Novo", "Reconhecido", "Resolvido", "Ignorado")
    }
    columns = st.columns(4)
    for column, (status, count) in zip(columns, counts.items(), strict=True):
        column.metric(status, count)
    severity_counts = {
        severity: sum(item["severity"] == severity for item in items)
        for severity in sorted({str(item["severity"]) for item in items})
    }
    st.caption(
        "Última execução local: "
        + (str(max((item["detected_at"] for item in items), default="Sem execução")))
        + " · "
        + " · ".join(f"{severity}: {count}" for severity, count in severity_counts.items())
    )
    for item in shown:
        with st.expander(f"{item['severity']} · {item['title']} · {item['lifecycle_status']}"):
            st.write(item["message"])
            actor = st.text_input(
                "Responsável", value="Usuário local", key=f"alert_actor_{item['id']}"
            )
            note = st.text_area("Nota ou justificativa", key=f"alert_note_{item['id']}")
            cols = st.columns(4)
            try:
                if cols[0].button("Reconhecer", key=f"ack_{item['id']}"):
                    with app_services() as services:
                        services.notifications.acknowledge(int(str(item["id"])), actor)
                    st.rerun()
                if cols[1].button("Resolver", key=f"resolve_{item['id']}"):
                    with app_services() as services:
                        services.notifications.close(int(str(item["id"])), actor, note)
                    st.rerun()
                if cols[2].button("Ignorar", key=f"ignore_{item['id']}"):
                    with app_services() as services:
                        services.notifications.close(
                            int(str(item["id"])), actor, note, ignored=True
                        )
                    st.rerun()
                if cols[3].button("Reabrir", key=f"alert_reopen_{item['id']}"):
                    with app_services() as services:
                        services.notifications.reopen(int(str(item["id"])), actor, note)
                    st.rerun()
            except DomainError as exc:
                st.error(str(exc))
            if item["entity_type"] == "Iniciativa" and st.button(
                "Abrir iniciativa", key=f"alert_open_{item['id']}"
            ):
                go(INITIATIVE, int(str(item["entity_id"])))
            if item["entity_type"] == "CasoIA" and st.button(
                "Abrir caso de IA", key=f"alert_ai_{item['id']}"
            ):
                go(AI_CASE, int(str(item["entity_id"])))
    st.caption(
        "Nenhum alerta é apagado: resolução, descarte e reabertura ficam registrados na auditoria."
    )
