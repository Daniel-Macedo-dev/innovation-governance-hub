from datetime import date
from decimal import Decimal

import streamlit as st

from innovation_governance_hub.exceptions import DomainError, GateBlockedError
from innovation_governance_hub.ui.context import app_services
from innovation_governance_hub.ui.formatting import brl
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
        [
            "Resumo",
            "Gate atual",
            "Priorização",
            "Indicadores",
            "Pendências",
            "Documentos",
            "Linha do tempo",
        ]
    )
    with tabs[0]:
        st.write(item["problem_description"])
        if item["proposed_solution"]:
            st.write(f"Solução proposta: {item['proposed_solution']}")
        st.caption(
            f"Área: {item['requesting_area']} · Responsável: {item['owner']} · "
            f"Estágio: {item['current_stage']} · Status: {item['status']}"
        )
        cost_columns = st.columns(3)
        cost_columns[0].metric("Custo planejado", brl(item["planned_cost"]))
        cost_columns[1].metric(
            "Custo realizado",
            brl(item["actual_cost"]),
            help="Soma das despesas com status Realizado vinculadas à iniciativa.",
        )
        cost_columns[2].metric("Benefício esperado", brl(item["expected_benefit"]))
        with st.expander("Editar iniciativa"):
            with st.form(f"edit_{initiative_id}"):
                name = st.text_input("Nome", value=str(item["name"]))
                area = st.text_input("Área solicitante", value=str(item["requesting_area"]))
                owner = st.text_input("Responsável", value=str(item["owner"]))
                problem = st.text_area("Problema", value=str(item["problem_description"]))
                solution = st.text_area("Solução proposta", value=str(item["proposed_solution"]))
                priority = st.selectbox(
                    "Prioridade",
                    ["Baixa", "Média", "Alta", "Crítica"],
                    index=["Baixa", "Média", "Alta", "Crítica"].index(str(item["priority"]))
                    if item["priority"] in {"Baixa", "Média", "Alta", "Crítica"}
                    else 1,
                )
                status_options = ["Ativa", "Em espera", "Bloqueada", "Concluída"]
                status = st.selectbox(
                    "Status",
                    status_options,
                    index=status_options.index(str(item["status"]))
                    if item["status"] in status_options
                    else 0,
                )
                deadline = st.date_input("Prazo", value=item["deadline"])
                planned = st.number_input(
                    "Custo planejado (R$)", min_value=0.0, value=float(item["planned_cost"])
                )
                benefit = st.number_input(
                    "Benefício esperado (R$)",
                    min_value=0.0,
                    value=float(item["expected_benefit"]),
                )
                notes = st.text_area("Observações", value=str(item["notes"]))
                actor = st.text_input("Alterado por", value="Usuário local")
                if st.form_submit_button("Salvar alterações"):
                    try:
                        with app_services() as services:
                            services.initiatives.update(
                                initiative_id,
                                {
                                    "name": name,
                                    "requesting_area": area,
                                    "owner": owner,
                                    "problem_description": problem,
                                    "proposed_solution": solution,
                                    "priority": priority,
                                    "status": status,
                                    "deadline": deadline,
                                    "planned_cost": planned,
                                    "expected_benefit": Decimal(str(benefit)),
                                    "notes": notes,
                                    "actor": actor,
                                },
                            )
                        st.success("Iniciativa atualizada.")
                        st.rerun()
                    except DomainError as exc:
                        st.error(str(exc))
        with st.expander("Arquivar iniciativa"):
            reason = st.text_input("Motivo do arquivamento", key=f"archive_reason_{initiative_id}")
            if st.button("Arquivar", key=f"archive_{initiative_id}"):
                try:
                    with app_services() as services:
                        services.gates.archive(initiative_id, "Usuário local", reason)
                    st.success("Iniciativa arquivada.")
                    st.rerun()
                except DomainError as exc:
                    st.error(str(exc))
    with tabs[1]:
        st.write(
            "Critérios do estágio atual. Os automáticos refletem os dados cadastrados; "
            "os manuais exigem evidência registrada. O avanço bloqueado fica auditado."
        )
        for criterion in data["criteria"]:
            icon = "✅" if criterion["completed"] else "⬜"
            kind = str(criterion["evaluation_type"])
            st.write(f"{icon} {criterion['name']} · {kind}")
            if kind != "Automática":
                with st.form(f"criterion_{criterion['id']}"):
                    completed = st.checkbox(
                        "Critério atendido",
                        value=bool(criterion["completed"]),
                        key=f"crit_done_{criterion['id']}",
                    )
                    evidence = st.text_input("Evidência", value=str(criterion["evidence"] or ""))
                    if st.form_submit_button("Salvar critério"):
                        try:
                            with app_services() as services:
                                services.gates.set_manual_check(
                                    initiative_id,
                                    int(str(criterion["id"])),
                                    completed,
                                    evidence,
                                    "Usuário local",
                                )
                            st.success("Critério atualizado.")
                            st.rerun()
                        except DomainError as exc:
                            st.error(str(exc))
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
        if not data["actions"]:
            st.info("Nenhuma pendência vinculada a esta iniciativa.")
        for action in data["actions"]:
            st.write(
                f"**{action['description']}** — {action['owner']} · {action['deadline']} · {action['status']}"
            )
    with tabs[5]:
        uploaded = st.file_uploader(
            "Anexar documento (PDF, DOCX, XLSX, PNG, JPG ou TXT até 10 MB)",
            type=["pdf", "docx", "xlsx", "png", "jpg", "jpeg", "txt"],
            key=f"document_{initiative_id}",
        )
        document_type = st.selectbox(
            "Tipo do documento",
            ["Descoberta", "Business case", "Evidência", "Ata", "Outros"],
            key=f"document_type_{initiative_id}",
        )
        description = st.text_input("Descrição do documento", key=f"document_desc_{initiative_id}")
        if uploaded is not None and st.button("Salvar documento", key=f"doc_save_{initiative_id}"):
            try:
                with app_services() as services:
                    services.documents.save(
                        initiative_id,
                        uploaded.name,
                        uploaded.getvalue(),
                        document_type,
                        description,
                        "Usuário local",
                    )
                st.success("Documento anexado.")
                st.rerun()
            except DomainError as exc:
                st.error(str(exc))
        if not data["documents"]:
            st.info("Nenhum documento anexado.")
        for document in data["documents"]:
            columns = st.columns([4, 1])
            columns[0].write(
                f"**{document['original_filename']}** · {document['document_type']} · "
                f"{document['uploaded_at']} · {document['uploaded_by']}"
                + (f" — {document['description']}" if document["description"] else "")
            )
            if columns[1].button("Remover", key=f"doc_delete_{document['id']}"):
                try:
                    with app_services() as services:
                        services.documents.delete(int(str(document["id"])), "Usuário local")
                    st.rerun()
                except DomainError as exc:
                    st.error(str(exc))
    with tabs[6]:
        for event in data["events"]:
            st.write(f"**{event['summary']}**")
            st.caption(f"{event['occurred_at']} · {event['actor']}")
