import streamlit as st

from innovation_governance_hub.exceptions import DomainError
from innovation_governance_hub.ui.context import app_services
from innovation_governance_hub.ui.navigation import INITIATIVE, go


def meetings() -> None:
    with app_services(read_only=True) as services:
        data = services.meeting_query.load()
        initiatives = services.pipeline_query.list()
    initiative_options = {
        f"{item['code']} — {item['name']}": int(str(item["id"])) for item in initiatives
    }
    with st.expander("Registrar reunião"):
        if not initiative_options:
            st.info("Cadastre uma iniciativa antes de registrar reuniões.")
        else:
            with st.form("new_meeting"):
                initiative_label = st.selectbox("Iniciativa", list(initiative_options))
                title = st.text_input("Título da reunião")
                meeting_date = st.date_input("Data da reunião")
                participants = st.text_input("Participantes (separados por ponto e vírgula)")
                minutes_text = st.text_area("Ata da reunião")
                executive_summary = st.text_area(
                    "Resumo executivo (manual, opcional)",
                    help="Escrito e editável por você; não há geração automática.",
                )
                decisions_text = st.text_area("Decisões (uma por linha)")
                actor = st.text_input("Registrado por", value="Usuário local")
                if st.form_submit_button("Registrar reunião"):
                    try:
                        with app_services() as services:
                            services.meetings.create(
                                initiative_options[initiative_label],
                                title,
                                meeting_date,
                                participants,
                                minutes_text,
                                executive_summary,
                                [
                                    line.strip()
                                    for line in decisions_text.splitlines()
                                    if line.strip()
                                ],
                                [],
                                actor,
                            )
                        st.success("Reunião registrada.")
                        st.rerun()
                    except DomainError as exc:
                        st.error(str(exc))
    st.subheader("Reuniões registradas")
    decisions_by_meeting: dict[int, list[str]] = {}
    for decision in data["decisions"]:
        decisions_by_meeting.setdefault(int(str(decision["meeting_id"])), []).append(
            str(decision["description"])
        )
    if not data["meetings"]:
        st.info("Nenhuma reunião registrada.")
    for meeting in data["meetings"]:
        with st.expander(f"{meeting['meeting_date']} — {meeting['title']}"):
            st.caption(f"Participantes: {meeting['participants'] or '—'}")
            if meeting["executive_summary"]:
                st.markdown(f"**Resumo executivo:** {meeting['executive_summary']}")
            st.markdown("**Ata:**")
            st.write(meeting["minutes_text"])
            recorded = decisions_by_meeting.get(int(str(meeting["id"])), [])
            if recorded:
                st.markdown("**Decisões:**")
                for description in recorded:
                    st.write(f"• {description}")
    st.subheader("Pendências")
    if data["meetings"]:
        meetings_by_label = {
            f"{item['meeting_date']} — {item['title']}": item for item in data["meetings"]
        }
        with st.expander("Cadastrar pendência"):
            with st.form("new_action"):
                meeting_label = st.selectbox("Reunião vinculada", meetings_by_label)
                description = st.text_input("Descrição da pendência")
                owner = st.text_input("Responsável pela pendência")
                deadline = st.date_input("Prazo da pendência")
                actor = st.text_input("Registrado por", value="Usuário local")
                if st.form_submit_button("Cadastrar pendência"):
                    meeting = meetings_by_label[meeting_label]
                    try:
                        with app_services() as services:
                            services.meetings.create_action(
                                int(str(meeting["id"])),
                                int(str(meeting["initiative_id"])),
                                description,
                                owner,
                                deadline,
                                actor,
                            )
                        st.success("Pendência cadastrada.")
                        st.rerun()
                    except DomainError as exc:
                        st.error(str(exc))
    statuses = st.multiselect(
        "Status",
        ["Aberta", "Em andamento", "Concluída", "Cancelada"],
        default=["Aberta", "Em andamento"],
    )
    shown = [item for item in data["actions"] if not statuses or item["status"] in statuses]
    for item in shown:
        with st.expander(f"{item['description']} · {item['owner']} · {item['status']}"):
            with st.form(f"action_{item['id']}"):
                description = st.text_input("Descrição", value=str(item["description"]))
                owner = st.text_input("Responsável", value=str(item["owner"]))
                deadline = st.date_input("Prazo", value=item["deadline"])
                status = st.selectbox(
                    "Situação",
                    ["Aberta", "Em andamento", "Concluída"],
                    index=["Aberta", "Em andamento", "Concluída"].index(str(item["status"]))
                    if item["status"] in {"Aberta", "Em andamento", "Concluída"}
                    else 0,
                )
                actor = st.text_input("Alterado por", value="Usuário local")
                if st.form_submit_button("Salvar pendência"):
                    with app_services() as services:
                        services.meetings.update_action(
                            int(str(item["id"])),
                            {
                                "description": description,
                                "owner": owner,
                                "deadline": deadline,
                                "status": status,
                            },
                            actor,
                        )
                    st.success("Pendência atualizada.")
                    st.rerun()
            reason = st.text_input("Justificativa ou motivo", key=f"reason_{item['id']}")
            col1, col2, col3 = st.columns(3)
            try:
                if col1.button("Concluir", key=f"complete_{item['id']}"):
                    with app_services() as services:
                        services.meetings.update_action(
                            int(str(item["id"])), {"status": "Concluída"}, "Usuário local"
                        )
                    st.rerun()
                if col2.button("Cancelar", key=f"cancel_{item['id']}"):
                    with app_services() as services:
                        services.meetings.cancel_action(
                            int(str(item["id"])), "Usuário local", reason
                        )
                    st.rerun()
                if col3.button("Reabrir", key=f"reopen_{item['id']}"):
                    with app_services() as services:
                        services.meetings.reopen_action(
                            int(str(item["id"])), "Usuário local", reason
                        )
                    st.rerun()
            except DomainError as exc:
                st.error(str(exc))
            if st.button("Abrir iniciativa", key=f"initiative_{item['id']}"):
                go(INITIATIVE, int(str(item["initiative_id"])))
