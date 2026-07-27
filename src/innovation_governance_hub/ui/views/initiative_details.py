from datetime import date
from decimal import Decimal

import streamlit as st

from innovation_governance_hub.exceptions import DomainError, GateBlockedError
from innovation_governance_hub.ui.context import app_services
from innovation_governance_hub.ui.navigation import selected
from innovation_governance_hub.ui.theme import status_label


def initiative_details() -> None:
    with app_services(read_only=True) as services:
        items = services.pipeline_query.list()
    options = {f"{item['code']} — {item['name']}": int(str(item["id"])) for item in items}
    if not options:
        st.info("Cadastre uma iniciativa para consultar detalhes.")
        return
    ids = list(options.values())
    chosen = selected("selected_initiative_id", ids, ids[0])
    labels = list(options)
    label = st.selectbox("Iniciativa", labels, index=ids.index(chosen) if chosen in ids else 0)
    initiative_id = options[label]
    st.session_state["selected_initiative_id"] = initiative_id
    with app_services(read_only=True) as services:
        data = services.initiative_query.load(initiative_id)
    if not data:
        st.error("Iniciativa não encontrada.")
        return
    item = data["initiative"]
    tabs = st.tabs(
        ["Resumo", "Gate atual", "Priorização", "Indicadores", "Pendências", "Linha do tempo"]
    )
    with tabs[0]:
        st.write(item["problem_description"])
        st.caption(
            f"Área: {item['requesting_area']} · Responsável: {item['owner']} · Estágio: {item['current_stage']}"
        )
    with tabs[1]:
        st.write("O avanço aplica critérios configurados e registra tentativas bloqueadas.")
        if st.button("Tentar avançar gate"):
            try:
                with app_services() as services:
                    services.gates.advance(initiative_id, "Usuário local")
                st.success("Gate avançado.")
                st.rerun()
            except GateBlockedError as exc:
                st.error(f"Critérios pendentes: {', '.join(exc.missing)}")
            except DomainError as exc:
                st.error(str(exc))
    with tabs[2]:
        current = data["assessment"] or {}
        st.caption(
            "Pesos de valor: 30% alinhamento, 30% valor esperado, 20% urgência e 20% confiança. Esforço: 60% complexidade e 40% risco."
        )
        with st.form(f"priority_{initiative_id}"):
            values = {
                field: st.slider(label_text, 1, 5, int(current.get(field, 3)))
                for field, label_text in (
                    ("strategic_alignment", "Alinhamento estratégico"),
                    ("expected_value", "Valor esperado"),
                    ("urgency", "Urgência"),
                    ("confidence", "Confiança"),
                    ("complexity", "Complexidade"),
                    ("execution_risk", "Risco de execução"),
                )
            }
            rationale = st.text_area("Justificativa", value=str(current.get("rationale", "")))
            assessor = st.text_input("Avaliador", value=str(current.get("assessed_by", "")))
            if st.form_submit_button("Salvar avaliação"):
                try:
                    with app_services() as services:
                        result = services.prioritization.save(
                            initiative_id, {**values, "rationale": rationale}, assessor
                        )
                    st.success(
                        f"Score {result.score} · {result.quadrant}. A prioridade operacional não foi alterada."
                    )
                    st.rerun()
                except DomainError as exc:
                    st.error(str(exc))
        if current:
            with app_services(read_only=True) as services:
                health = {
                    value.initiative_id: value.status for value in services.executive.brief().health
                }
                row = next(
                    (
                        value
                        for value in services.prioritization_query.portfolio(health)
                        if value.initiative_id == initiative_id
                    ),
                    None,
                )
            if row:
                st.metric("Score atual", row.score)
                st.write(
                    f"Quadrante: **{row.quadrant}** · Valor: {row.value} · Esforço: {row.effort}"
                )
    with tabs[3]:
        for indicator in data["indicators"]:
            st.markdown(f"### {indicator['name']} — {status_label(str(indicator['status']))}")
            st.write(
                f"Baseline: {indicator['baseline_value']} · Atual: {indicator['current_value']} · Meta: {indicator['target_value']} {indicator['unit']}"
            )
            if indicator["progress_percent"] is not None:
                st.progress(
                    max(0.0, min(1.0, float(indicator["progress_percent"]) / 100)),
                    text=f"{indicator['progress_percent']}%",
                )
        with st.expander("Cadastrar ou atualizar indicador"):
            existing = {str(value["name"]): value for value in data["indicators"]}
            choice = st.selectbox("Indicador existente", ["Novo", *existing])
            base = existing.get(choice, {})
            with st.form(f"indicator_{initiative_id}"):
                name = st.text_input("Nome do indicador", value=str(base.get("name", "")))
                unit = st.selectbox(
                    "Unidade",
                    ["Percentual", "Real", "Dias", "Horas", "Quantidade", "Índice"],
                    index=0,
                )
                baseline = st.number_input("Baseline", value=float(base.get("baseline_value") or 0))
                current_value = st.number_input(
                    "Valor atual", value=float(base.get("current_value") or 0)
                )
                target = st.number_input("Meta", value=float(base.get("target_value") or 0))
                direction = st.selectbox("Direção", ["Aumentar", "Reduzir", "Manter faixa"])
                owner = st.text_input(
                    "Responsável pelo indicador", value=str(base.get("owner", ""))
                )
                measurement = st.date_input(
                    "Data de medição", value=base.get("measurement_date") or date.today()
                )
                if st.form_submit_button("Salvar indicador"):
                    try:
                        with app_services() as services:
                            services.indicators.save(
                                initiative_id,
                                {
                                    "name": name,
                                    "description": "",
                                    "unit": unit,
                                    "baseline_value": Decimal(str(baseline)),
                                    "current_value": Decimal(str(current_value)),
                                    "target_value": Decimal(str(target)),
                                    "direction": direction,
                                    "owner": owner,
                                    "measurement_date": measurement,
                                    "notes": "",
                                },
                                "Usuário local",
                                int(base["id"]) if base else None,
                            )
                        st.success("Indicador salvo.")
                        st.rerun()
                    except DomainError as exc:
                        st.error(str(exc))
    with tabs[4]:
        for action in data["actions"]:
            st.write(
                f"**{action['description']}** — {action['owner']} · {action['deadline']} · {action['status']}"
            )
    with tabs[5]:
        for event in data["events"]:
            st.write(f"**{event['summary']}**")
            st.caption(f"{event['occurred_at']} · {event['actor']}")
