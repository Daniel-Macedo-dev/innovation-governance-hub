from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import select

from innovation_governance_hub.config import get_settings
from innovation_governance_hub.database import SessionLocal
from innovation_governance_hub.domain.enums import InitiativeStatus, Stage
from innovation_governance_hub.domain.schemas import MeetingSummaryResult
from innovation_governance_hub.excel.exporters import executive_workbook
from innovation_governance_hub.excel.importers import (
    error_report,
    persist_preview,
    preview_expenses,
    preview_initiatives,
)
from innovation_governance_hub.exceptions import DomainError, GateBlockedError
from innovation_governance_hub.integrations.ai_provider_factory import create_ai_provider
from innovation_governance_hub.integrations.n8n_client import N8NClient
from innovation_governance_hub.persistence.models import (
    ActionItem,
    AIGovernanceDecision,
    AIUseCase,
    AnnualBudget,
    Expense,
    GateCriterionDefinition,
    Initiative,
    InitiativeDocument,
    InitiativeGateCheck,
    Meeting,
    NotificationLog,
)
from innovation_governance_hub.services.ai_governance_service import (
    AIUseCaseService,
    adoption,
    review_overdue,
)
from innovation_governance_hub.services.audit_service import AuditService
from innovation_governance_hub.services.automation_service import AutomationService
from innovation_governance_hub.services.budget_service import BudgetService
from innovation_governance_hub.services.document_service import DocumentService
from innovation_governance_hub.services.gate_service import GateService
from innovation_governance_hub.services.initiative_service import InitiativeService
from innovation_governance_hub.services.meeting_service import MeetingService
from innovation_governance_hub.ui.formatting import br_date, brl, percent


def overview() -> None:
    st.markdown(
        '<style>[data-testid="stMetricValue"]{font-size:1.75rem}</style>',
        unsafe_allow_html=True,
    )
    with SessionLocal() as s:
        initiatives = s.scalars(select(Initiative)).all()
        cases = s.scalars(select(AIUseCase)).all()
        year = date.today().year
        totals = BudgetService(s).totals(year)
        alerts = AutomationService(s).run(False)
        active = [
            i
            for i in initiatives
            if i.status not in (InitiativeStatus.COMPLETED, InitiativeStatus.ARCHIVED)
        ]
        values: list[tuple[str, str | int]] = [
            ("Iniciativas", len(initiatives)),
            ("Projetos ativos", len(active)),
            ("Atrasados", sum(bool(i.deadline and i.deadline < date.today()) for i in active)),
            ("Parados", sum(a.notification_type == "projeto_parado" for a in alerts)),
            ("Orçamento", brl(totals["planned"])),
            ("Gasto realizado", brl(totals["actual"])),
            ("Saldo", brl(totals["balance"])),
            ("Casos de IA", len(cases)),
            ("IA aprovada", sum(c.evaluation_status == "Aprovado" for c in cases)),
            ("Revisões vencidas", sum(review_overdue(c) for c in cases)),
        ]
        for start in range(0, len(values), 4):
            row = values[start : start + 4]
            for col, (label, value) in zip(st.columns(len(row)), row, strict=True):
                col.metric(label, value)
        tab1, tab2, tab3 = st.tabs(["Portfólio", "Financeiro", "Governança de IA"])
        with tab1:
            frame = pd.DataFrame(
                [
                    {"Estágio": i.current_stage, "Área": i.requesting_area, "Iniciativa": i.code}
                    for i in initiatives
                ],
                columns=["Estágio", "Área", "Iniciativa"],
            )
            st.plotly_chart(
                px.histogram(frame, x="Estágio", color="Área", title="Iniciativas por estágio"),
                use_container_width=True,
            )
            st.dataframe(
                [
                    {
                        "Código": i.code,
                        "Nome": i.name,
                        "Prazo": br_date(i.deadline),
                        "Status": i.status,
                    }
                    for i in active
                    if i.deadline and i.deadline < date.today()
                ],
                use_container_width=True,
            )
        with tab2:
            expenses = s.scalars(select(Expense)).all()
            frame = pd.DataFrame(
                [
                    {
                        "Mês": x.competence_date.strftime("%m/%Y"),
                        "Categoria": x.category,
                        "Valor": float(x.amount),
                    }
                    for x in expenses
                ],
                columns=["Mês", "Categoria", "Valor"],
            )
            st.plotly_chart(
                px.bar(
                    frame, x="Mês", y="Valor", color="Categoria", title="Gastos por mês e categoria"
                ),
                use_container_width=True,
            )
        with tab3:
            frame = pd.DataFrame(
                [
                    {
                        "Status": x.evaluation_status,
                        "Risco": x.risk_level,
                        "Adoção": adoption(x),
                        "Caso": x.code,
                    }
                    for x in cases
                ],
                columns=["Status", "Risco", "Adoção", "Caso"],
            )
            st.plotly_chart(
                px.scatter(
                    frame,
                    x="Caso",
                    y="Adoção",
                    color="Risco",
                    symbol="Status",
                    title="Adoção de IA (%)",
                ),
                use_container_width=True,
            )


def pipeline() -> None:
    with SessionLocal.begin() as s:
        items = s.scalars(select(Initiative).order_by(Initiative.code)).all()
        with st.expander("Cadastrar iniciativa"):
            with st.form("new_initiative"):
                name = st.text_input("Nome")
                area = st.text_input("Área solicitante")
                owner = st.text_input("Responsável")
                problem = st.text_area("Problema")
                solution = st.text_area("Solução proposta")
                cost = st.number_input("Custo planejado", min_value=0.0)
                if st.form_submit_button("Cadastrar"):
                    code = f"INI-{(max([int(i.code.split('-')[1]) for i in items] or [0]) + 1):03d}"
                    s.add(
                        Initiative(
                            code=code,
                            name=name,
                            requesting_area=area,
                            owner=owner,
                            problem_description=problem,
                            proposed_solution=solution,
                            priority="Média",
                            expected_impact_level="Médio",
                            expected_impact_description="",
                            complexity="Média",
                            created_date=date.today(),
                            deadline=None,
                            status="Ativa",
                            current_stage="Ideia",
                            planned_cost=Decimal(str(cost)),
                            expected_benefit=Decimal("0"),
                            notes="",
                        )
                    )
                    st.success(f"{code} cadastrada.")
        filters = st.multiselect(
            "Estágio", [x.value for x in Stage], placeholder="Selecione os estágios"
        )
        shown = [i for i in items if not filters or i.current_stage in filters]
        st.dataframe(
            [
                {
                    "Código": i.code,
                    "Nome": i.name,
                    "Área": i.requesting_area,
                    "Estágio": i.current_stage,
                    "Status": i.status,
                    "Prazo": br_date(i.deadline),
                    "Planejado": brl(i.planned_cost),
                    "Realizado": brl(BudgetService(s).initiative_actual(i.id)),
                }
                for i in shown
            ],
            use_container_width=True,
        )


def initiative_details() -> None:
    with SessionLocal.begin() as s:
        items = s.scalars(select(Initiative).order_by(Initiative.code)).all()
        if not items:
            st.info("Cadastre uma iniciativa no Funil.")
            return
        selected = st.selectbox("Iniciativa", items, format_func=lambda x: f"{x.code} — {x.name}")
        tabs = st.tabs(
            ["Resumo", "Gate atual", "Documentos", "Linha do tempo", "Reuniões", "Custos"]
        )
        with tabs[0]:
            st.write(selected.problem_description)
            st.metric("Custo planejado", brl(selected.planned_cost))
            st.metric("Realizado", brl(BudgetService(s).initiative_actual(selected.id)))
            with st.form(f"edit-initiative-{selected.id}"):
                name = st.text_input("Nome", value=selected.name)
                problem = st.text_area("Descrição do problema", value=selected.problem_description)
                solution = st.text_area("Solução proposta", value=selected.proposed_solution)
                area = st.text_input("Área solicitante", value=selected.requesting_area)
                owner = st.text_input("Responsável", value=selected.owner)
                priority_options = ["Baixa", "Média", "Alta", "Crítica"]
                priority = st.selectbox(
                    "Prioridade",
                    priority_options,
                    index=priority_options.index(selected.priority),
                )
                impact_options = ["Baixo", "Médio", "Alto", "Muito alto"]
                impact = st.selectbox(
                    "Impacto",
                    impact_options,
                    index=impact_options.index(selected.expected_impact_level),
                )
                complexity_options = ["Baixa", "Média", "Alta"]
                complexity = st.selectbox(
                    "Complexidade",
                    complexity_options,
                    index=complexity_options.index(selected.complexity),
                )
                deadline = st.date_input("Prazo", value=selected.deadline, format="DD/MM/YYYY")
                planned = st.number_input(
                    "Custo planejado", min_value=0.0, value=float(selected.planned_cost)
                )
                if st.form_submit_button("Salvar alterações"):
                    try:
                        InitiativeService(s).update(
                            selected.id,
                            {
                                "name": name,
                                "problem_description": problem,
                                "proposed_solution": solution,
                                "requesting_area": area,
                                "owner": owner,
                                "priority": priority,
                                "expected_impact_level": impact,
                                "expected_impact_description": selected.expected_impact_description,
                                "complexity": complexity,
                                "deadline": deadline,
                                "status": selected.status,
                                "planned_cost": Decimal(str(planned)),
                            },
                        )
                        st.success("Iniciativa atualizada.")
                    except DomainError as exc:
                        st.error(str(exc))
            if selected.current_stage not in ("Concluída", "Arquivada"):
                archive_reason = st.text_input("Motivo para arquivar")
                confirm_archive = st.checkbox("Confirmar arquivamento")
                if st.button("Arquivar iniciativa", disabled=not confirm_archive):
                    try:
                        GateService(s).archive(selected.id, "Usuário local", archive_reason)
                        st.success("Iniciativa arquivada.")
                    except DomainError as exc:
                        st.error(str(exc))
        with tabs[1]:
            defs = s.scalars(
                select(GateCriterionDefinition)
                .where(GateCriterionDefinition.stage == selected.current_stage)
                .order_by(GateCriterionDefinition.display_order)
            ).all()
            checks = {
                c.criterion_definition_id: c
                for c in s.scalars(
                    select(InitiativeGateCheck).where(
                        InitiativeGateCheck.initiative_id == selected.id
                    )
                ).all()
            }
            for criterion in defs:
                if criterion.evaluation_type == "Automática":
                    st.write(
                        f"{'✅' if criterion.name not in GateService(s).evaluate(selected) else '❌'} {criterion.name} — automática"
                    )
                else:
                    done = st.checkbox(
                        criterion.name,
                        value=bool(checks.get(criterion.id) and checks[criterion.id].completed),
                        key=f"c{selected.id}-{criterion.id}",
                    )
                    existing_check = checks.get(criterion.id)
                    evidence = st.text_input(
                        "Evidência",
                        value=existing_check.evidence if existing_check else "",
                        key=f"e{selected.id}-{criterion.id}",
                    )
                    if st.button("Salvar critério", key=f"b{selected.id}-{criterion.id}"):
                        try:
                            GateService(s).set_manual_check(
                                selected.id, criterion.id, done, evidence, "Usuário local"
                            )
                            st.success("Critério salvo.")
                        except DomainError as exc:
                            st.error(str(exc))
            if st.button("Tentar avançar gate", type="primary"):
                try:
                    GateService(s).advance(selected.id, "Usuário local")
                    st.success("Gate avançado.")
                except GateBlockedError as exc:
                    st.error(str(exc))
        with tabs[2]:
            uploaded = st.file_uploader(
                "Documento", type=["pdf", "docx", "xlsx", "png", "jpg", "txt"]
            )
            kind = st.text_input("Tipo do documento", "Evidência")
            description = st.text_input("Descrição do documento")
            if uploaded and st.button("Salvar documento"):
                try:
                    DocumentService(s).save(
                        selected.id,
                        uploaded.name,
                        uploaded.getvalue(),
                        kind,
                        description,
                        "Usuário local",
                    )
                    st.success("Documento armazenado.")
                except DomainError as exc:
                    st.error(str(exc))
            docs = s.scalars(
                select(InitiativeDocument).where(InitiativeDocument.initiative_id == selected.id)
            ).all()
            for doc in docs:
                path = Path(doc.relative_path)
                left, middle, right = st.columns([4, 2, 2])
                left.write(f"**{doc.original_filename}** — {doc.document_type}")
                middle.download_button(
                    "Baixar",
                    path.read_bytes() if path.exists() else b"",
                    file_name=doc.original_filename,
                    key=f"download-{doc.id}",
                )
                confirmed = right.checkbox("Confirmar exclusão", key=f"confirm-doc-{doc.id}")
                if right.button("Excluir", key=f"delete-doc-{doc.id}", disabled=not confirmed):
                    try:
                        DocumentService(s).delete(doc.id)
                        st.success("Documento excluído.")
                    except DomainError as exc:
                        st.error(str(exc))
        with tabs[3]:
            events = AuditService(s).timeline("Iniciativa", selected.id)
            event_types = sorted({event.event_type for event in events})
            event_type_labels = {
                "initiative.created": "Iniciativa criada",
                "initiative.updated": "Iniciativa alterada",
                "expense.created": "Despesa registrada",
                "meeting.created": "Reunião registrada",
                "document.uploaded": "Documento enviado",
                "gate.blocked": "Gate bloqueado",
                "gate.advanced": "Gate avançado",
                "initiative.archived": "Iniciativa arquivada",
            }
            chosen = st.multiselect(
                "Tipos de evento",
                event_types,
                default=event_types,
                format_func=lambda value: event_type_labels.get(value, value),
            )
            newest = st.toggle("Mais recentes primeiro", value=True)
            filtered = [event for event in events if event.event_type in chosen]
            filtered.sort(key=lambda event: (event.occurred_at, event.id), reverse=newest)
            if not filtered:
                st.info("Nenhum evento registrado para os filtros selecionados.")
            for event in filtered:
                st.markdown(
                    f"**{event.summary}**  \n{event.occurred_at.strftime('%d/%m/%Y %H:%M')} · {event.actor}"
                )
        with tabs[4]:
            st.dataframe(
                [
                    {
                        "Título": x.title,
                        "Data": br_date(x.meeting_date),
                        "Resumo": x.executive_summary,
                    }
                    for x in s.scalars(
                        select(Meeting).where(Meeting.initiative_id == selected.id)
                    ).all()
                ]
            )
        with tabs[5]:
            st.dataframe(
                [
                    {
                        "Data": br_date(x.competence_date),
                        "Descrição": x.description,
                        "Status": x.financial_status,
                        "Valor": brl(x.amount),
                    }
                    for x in s.scalars(
                        select(Expense).where(Expense.initiative_id == selected.id)
                    ).all()
                ]
            )


def ai_governance() -> None:
    with SessionLocal.begin() as s:
        cases = s.scalars(select(AIUseCase).order_by(AIUseCase.code)).all()
        st.dataframe(
            [
                {
                    "Código": x.code,
                    "Nome": x.name,
                    "Risco": x.risk_level,
                    "Status": x.evaluation_status,
                    "Dados pessoais": x.uses_personal_data,
                    "Adoção": percent(adoption(x)),
                    "Revisão vencida": review_overdue(x),
                }
                for x in cases
            ],
            use_container_width=True,
        )
        with st.expander("Cadastrar caso de IA"):
            with st.form("new-ai-case"):
                code = st.text_input("Código do caso")
                name = st.text_input("Nome do caso")
                area = st.text_input("Área responsável")
                owner = st.text_input("Responsável do caso")
                objective = st.text_area("Objetivo")
                tool = st.text_input("Ferramenta de IA")
                provider = st.text_input("Modelo ou provedor")
                data_description = st.text_area("Descrição dos dados")
                risk = st.selectbox("Nível de risco", ["Baixo", "Médio", "Alto", "Crítico"])
                mitigation = st.text_area("Mitigação")
                estimated = st.number_input("Usuários estimados", min_value=0)
                active = st.number_input("Usuários ativos", min_value=0)
                if st.form_submit_button("Cadastrar caso"):
                    try:
                        saved = AIUseCaseService(s).save(
                            {
                                "code": code,
                                "name": name,
                                "responsible_area": area,
                                "objective": objective,
                                "ai_tool": tool,
                                "model_or_provider": provider,
                                "data_description": data_description,
                                "uses_personal_data": False,
                                "risk_level": risk,
                                "risk_mitigation": mitigation,
                                "expected_impact": "",
                                "evaluation_status": "Rascunho",
                                "owner": owner,
                                "next_review_date": None,
                                "policy_accepted": False,
                                "governance_approved": False,
                                "estimated_users": estimated,
                                "active_users": active,
                                "notes": "",
                            }
                        )
                        st.success(f"{saved.code} cadastrado.")
                    except (DomainError, ValueError) as exc:
                        st.error(str(exc))
        if cases:
            case = st.selectbox("Editar caso", cases, format_func=lambda x: f"{x.code} — {x.name}")
            target = st.selectbox(
                "Status desejado",
                [
                    "Rascunho",
                    "Em avaliação",
                    "Aprovado",
                    "Aprovado com restrições",
                    "Rejeitado",
                    "Suspenso",
                    "Em revisão",
                ],
                index=0,
            )
            justification = st.text_area("Justificativa da decisão")
            restrictions = st.text_area("Restrições aplicáveis")
            next_review = st.date_input(
                "Próxima revisão",
                value=case.next_review_date or date.today(),
                format="DD/MM/YYYY",
            )
            if st.button("Atualizar avaliação"):
                try:
                    values = {
                        column.name: getattr(case, column.name)
                        for column in AIUseCase.__table__.columns
                        if column.name not in {"id", "created_at", "updated_at"}
                    }
                    values.update(
                        evaluation_status=target,
                        next_review_date=next_review,
                        actor="Usuário local",
                        justification=justification,
                        restrictions=restrictions,
                    )
                    AIUseCaseService(s).save(values, case.id)
                    st.success("Avaliação atualizada.")
                except DomainError as exc:
                    st.error(str(exc))
            decisions = s.scalars(
                select(AIGovernanceDecision)
                .where(AIGovernanceDecision.ai_use_case_id == case.id)
                .order_by(AIGovernanceDecision.decided_at.desc())
            ).all()
            st.subheader("Histórico de decisões")
            if decisions:
                st.dataframe(
                    [
                        {
                            "Data": item.decided_at.strftime("%d/%m/%Y %H:%M"),
                            "De": item.previous_status or "Criação",
                            "Para": item.new_status,
                            "Responsável": item.responsible,
                            "Justificativa": item.justification,
                            "Restrições": item.restrictions or "—",
                        }
                        for item in decisions
                    ],
                    use_container_width=True,
                )
            else:
                st.info("Nenhuma decisão de governança registrada.")


def budget() -> None:
    with SessionLocal.begin() as s:
        year = st.number_input("Ano", 2020, 2100, date.today().year)
        totals = BudgetService(s).projection(year)
        primary_metrics = [
            ("Planejado", totals["planned"]),
            ("Realizado", totals["actual"]),
            ("Previsto", totals["forecast"]),
            ("Comprometido", totals["committed"]),
        ]
        for start in range(0, len(primary_metrics), 2):
            for col, item in zip(st.columns(2), primary_metrics[start : start + 2], strict=True):
                col.metric(item[0], brl(item[1]))
        forecast_cols = st.columns(2)
        forecast_cols[0].metric(
            "Variação", brl(totals["variance"]), percent(totals["variance_percent"])
        )
        forecast_cols[1].metric("Saldo após compromissos", brl(totals["balance_after_commitments"]))
        forecast_cols = st.columns(2)
        forecast_cols[0].metric("Projeção até dezembro", brl(totals["year_end_projection"]))
        forecast_cols[1].metric(
            "Média dos últimos 3 meses", brl(totals["recent_three_month_average"])
        )
        st.caption(
            "Projeção simples demonstrativa: realizado + previsto cadastrado + média recente nos meses futuros."
        )
        planned = st.number_input("Orçamento anual", min_value=0.0, value=float(totals["planned"]))
        if st.button("Salvar orçamento"):
            row = s.scalar(select(AnnualBudget).where(AnnualBudget.year == year))
            if row:
                row.planned_amount = Decimal(str(planned))
            else:
                s.add(AnnualBudget(year=year, planned_amount=Decimal(str(planned)), notes=""))
            st.success("Orçamento salvo.")
        st.warning(f"Consumo: {percent(totals['consumed_percent'])}") if totals[
            "consumed_percent"
        ] >= 80 else st.info(f"Consumo: {percent(totals['consumed_percent'])}")
        expenses = s.scalars(
            select(Expense).where(
                Expense.competence_date.between(date(year, 1, 1), date(year, 12, 31))
            )
        ).all()
        expense_choices: list[Expense | None] = [None, *expenses]
        expense = st.selectbox(
            "Cadastrar ou editar despesa",
            expense_choices,
            format_func=lambda value: (
                "Nova despesa"
                if value is None
                else f"{br_date(value.competence_date)} — {value.description} — {brl(value.amount)}"
            ),
        )
        initiatives = s.scalars(select(Initiative).order_by(Initiative.code)).all()
        initiative_choices: list[Initiative | None] = [None, *initiatives]
        current_initiative = (
            next((item for item in initiatives if item.id == expense.initiative_id), None)
            if expense
            else None
        )
        with st.form(f"expense-{expense.id if expense else 'new'}"):
            competence = st.date_input(
                "Data de competência",
                value=expense.competence_date if expense else date.today(),
                format="DD/MM/YYYY",
            )
            linked = st.selectbox(
                "Iniciativa (opcional)",
                initiative_choices,
                index=initiative_choices.index(current_initiative),
                format_func=lambda value: (
                    "Sem iniciativa" if value is None else f"{value.code} — {value.name}"
                ),
            )
            category = st.selectbox(
                "Categoria",
                [
                    "Ferramentas e software",
                    "Fornecedores",
                    "Consultoria",
                    "Infraestrutura",
                    "Treinamento",
                    "Outros",
                ],
                index=(
                    [
                        "Ferramentas e software",
                        "Fornecedores",
                        "Consultoria",
                        "Infraestrutura",
                        "Treinamento",
                        "Outros",
                    ].index(expense.category)
                    if expense
                    else 0
                ),
            )
            description = st.text_input("Descrição", value=expense.description if expense else "")
            supplier = st.text_input("Fornecedor", value=expense.supplier if expense else "")
            tool = st.text_input("Ferramenta", value=expense.tool_name if expense else "")
            cost_type = st.selectbox(
                "Tipo de custo",
                ["Pontual", "Recorrente"],
                index=["Pontual", "Recorrente"].index(expense.cost_type) if expense else 0,
            )
            financial_status = st.selectbox(
                "Status financeiro",
                ["Realizado", "Previsto"],
                index=["Realizado", "Previsto"].index(expense.financial_status) if expense else 0,
            )
            amount = st.number_input(
                "Valor", min_value=0.01, value=float(expense.amount) if expense else 0.01
            )
            if st.form_submit_button("Salvar despesa", type="primary"):
                try:
                    BudgetService(s).save_expense(
                        {
                            "initiative_id": linked.id if linked else None,
                            "competence_date": competence,
                            "category": category,
                            "description": description,
                            "supplier": supplier,
                            "tool_name": tool,
                            "cost_type": cost_type,
                            "financial_status": financial_status,
                            "amount": Decimal(str(amount)),
                        },
                        expense.id if expense else None,
                    )
                    st.success("Despesa salva.")
                except DomainError as exc:
                    st.error(str(exc))
        if expense:
            confirm_expense = st.checkbox(
                "Confirmar exclusão da despesa", key=f"confirm-expense-{expense.id}"
            )
            if st.button("Excluir despesa", disabled=not confirm_expense):
                BudgetService(s).delete_expense(expense.id)
                st.success("Despesa excluída.")
        st.dataframe(
            [
                {
                    "Código": i.code,
                    "Nome": i.name,
                    "Planejado": brl(i.planned_cost),
                    "Realizado": brl(BudgetService(s).initiative_actual(i.id)),
                }
                for i in BudgetService(s).over_budget()
            ],
            use_container_width=True,
        )


def meetings() -> None:
    with SessionLocal.begin() as s:
        items = s.scalars(select(Initiative).order_by(Initiative.code)).all()
        if not items:
            st.info("Cadastre uma iniciativa.")
            return
        selected = st.selectbox("Iniciativa", items, format_func=lambda x: f"{x.code} — {x.name}")
        title = st.text_input("Título")
        participants = st.text_input("Participantes")
        minutes = st.text_area("Ata", height=180)
        if st.button("Gerar resumo para revisão"):
            if not minutes.strip():
                st.error("Informe a ata antes de gerar o resumo.")
            else:
                try:
                    result = create_ai_provider().summarize(minutes)
                    st.session_state["summary"] = result.model_dump()
                except DomainError as exc:
                    st.error(str(exc))
        if "summary" in st.session_state:
            generated = MeetingSummaryResult.model_validate(st.session_state["summary"])
            st.info(f"{generated.mode} — {generated.provider_name}")
            reviewed_summary = st.text_area(
                "Resumo executivo revisado",
                value=generated.executive_summary,
                key="reviewed_summary",
            )
            decisions_text = st.text_area(
                "Decisões — uma por linha",
                value="\n".join(generated.decisions),
                key="reviewed_decisions",
            )
            actions_text = st.text_area(
                "Pendências — descrição | responsável | DD/MM/AAAA (uma por linha)",
                value="\n".join(f"{action} | A definir |" for action in generated.action_items),
                key="reviewed_actions",
            )
            if st.button("Salvar reunião e conteúdo revisado", type="primary"):
                try:
                    actions: list[dict[str, object]] = []
                    for line in [
                        value.strip() for value in actions_text.splitlines() if value.strip()
                    ]:
                        parts = [part.strip() for part in line.split("|")]
                        if len(parts) < 2:
                            raise DomainError(
                                "Use o formato descrição | responsável | DD/MM/AAAA nas pendências."
                            )
                        deadline = (
                            pd.to_datetime(parts[2], dayfirst=True, errors="raise").date()
                            if len(parts) > 2 and parts[2]
                            else None
                        )
                        actions.append(
                            {"description": parts[0], "owner": parts[1], "deadline": deadline}
                        )
                    reviewed = generated.model_copy(update={"executive_summary": reviewed_summary})
                    MeetingService(s).create(
                        selected.id,
                        title,
                        date.today(),
                        participants,
                        minutes,
                        reviewed,
                        [line.strip() for line in decisions_text.splitlines() if line.strip()],
                        actions,
                    )
                    st.session_state.pop("summary", None)
                    st.success("Reunião, decisões e pendências salvas.")
                except (DomainError, ValueError) as exc:
                    st.error(str(exc))
        st.dataframe(
            [
                {"Título": x.title, "Data": br_date(x.meeting_date), "Modo": x.summary_mode}
                for x in s.scalars(
                    select(Meeting).where(Meeting.initiative_id == selected.id)
                ).all()
            ]
        )
        open_actions = s.scalars(
            select(ActionItem)
            .where(ActionItem.initiative_id == selected.id)
            .order_by(ActionItem.deadline)
        ).all()
        if open_actions:
            st.subheader("Pendências")
        for action in open_actions:
            col1, col2 = st.columns([4, 2])
            col1.write(
                f"{action.description} — {action.owner} — {br_date(action.deadline)} — {action.status}"
            )
            new_status = col2.selectbox(
                "Status",
                ["Aberta", "Em andamento", "Concluída", "Cancelada"],
                index=["Aberta", "Em andamento", "Concluída", "Cancelada"].index(action.status),
                key=f"action-status-{action.id}",
            )
            if new_status != action.status:
                action.status = new_status


def excel_io() -> None:
    for name in ["modelo_iniciativas.xlsx", "modelo_custos.xlsx"]:
        path = Path("templates") / name
        if path.exists():
            st.download_button(f"Baixar {name}", path.read_bytes(), file_name=name)
    with SessionLocal() as s:
        st.download_button(
            "Exportar relatório executivo",
            executive_workbook(s),
            "relatorio_executivo.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    import_kind = st.radio("Tipo de importação", ["Iniciativas", "Custos"], horizontal=True)
    uploaded = st.file_uploader("Enviar XLSX para validar", type=["xlsx"])
    if uploaded:
        try:
            content = uploaded.getvalue()
            with SessionLocal() as session:
                if import_kind == "Iniciativas":
                    codes = set(session.scalars(select(Initiative.code)).all())
                    preview = preview_initiatives(content, codes)
                else:
                    initiatives = {
                        item.code: item.id for item in session.scalars(select(Initiative)).all()
                    }
                    preview = preview_expenses(content, initiatives)
            if preview.valid:
                st.success(f"Validação concluída: {len(preview.rows)} linhas prontas.")
                preview_labels = {
                    "code": "Código",
                    "name": "Nome",
                    "problem_description": "Descrição do problema",
                    "proposed_solution": "Solução proposta",
                    "requesting_area": "Área solicitante",
                    "owner": "Responsável",
                    "planned_cost": "Custo planejado",
                    "amount": "Valor",
                    "competence_date": "Data de competência",
                }
                st.dataframe(
                    pd.DataFrame(preview.rows).head(50).rename(columns=preview_labels),
                    use_container_width=True,
                )
                if st.button("Confirmar importação", type="primary"):
                    with SessionLocal.begin() as session:
                        imported = persist_preview(session, preview)
                    st.success(f"Importação concluída em transação única: {imported} registros.")
            else:
                st.error(f"Foram encontrados {len(preview.issues)} erros; nada foi importado.")
                st.dataframe(
                    [
                        {"Linha": issue.row, "Coluna": issue.column, "Erro": issue.message}
                        for issue in preview.issues
                    ],
                    use_container_width=True,
                )
                st.download_button(
                    "Baixar relatório de erros",
                    error_report(preview),
                    "erros_importacao.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
        except (ValueError, OSError) as exc:
            st.error(f"Arquivo inválido: {exc}")


def automations() -> None:
    settings = get_settings()
    st.info(
        "n8n habilitado"
        if settings.n8n_enabled
        else "n8n desabilitado — verificações locais disponíveis"
    )
    st.caption(f"Webhook configurado: {'sim' if settings.n8n_webhook_url else 'não'}")
    with SessionLocal.begin() as s:
        if st.button("Executar verificações"):
            alerts = AutomationService(s).run()
            st.success(f"{len(alerts)} alertas detectados.")
        logs = s.scalars(select(NotificationLog).order_by(NotificationLog.detected_at.desc())).all()
        type_labels = {
            "pendencia_vencida": "Pendência vencida",
            "revisao_ia_vencida": "Revisão de IA vencida",
            "ia_risco_sem_aprovacao": "Risco de IA sem aprovação",
            "gate_pendente": "Gate pendente",
            "projeto_parado": "Projeto sem atividade",
            "projeto_atrasado": "Projeto atrasado",
            "orcamento_excedido": "Orçamento excedido",
            "orcamento_proximo": "Orçamento próximo do limite",
            "documentacao_pendente": "Documentação pendente",
        }
        st.dataframe(
            [
                {
                    "Tipo": type_labels.get(x.notification_type, x.notification_type),
                    "Severidade": x.severity,
                    "Título": x.title,
                    "Entrega": x.delivery_status,
                }
                for x in logs
            ],
            use_container_width=True,
        )
        failed = [log for log in logs if log.delivery_status == "Falha"]
        if failed:
            retry = st.selectbox(
                "Falha para reprocessar",
                failed,
                format_func=lambda value: f"{value.title} — {value.error_message}",
            )
            if st.button("Reprocessar falha"):
                result = N8NClient().send(
                    {
                        "event": "innovation_governance_alerts",
                        "generated_at": retry.detected_at.isoformat(),
                        "summary": {"total": 1, "reprocessing": True},
                        "alerts": [
                            {
                                "fingerprint": retry.fingerprint,
                                "type": retry.notification_type,
                                "severity": retry.severity,
                                "title": retry.title,
                                "message": retry.message,
                            }
                        ],
                    }
                )
                retry.delivery_status = "Enviada" if result.get("sent") else "Falha"
                retry.error_message = str(result.get("error", ""))
                st.success("Reprocessamento concluído.") if result.get("sent") else st.error(
                    f"Falha real: {retry.error_message or result.get('status')}"
                )
        if st.button(
            "Testar webhook",
            disabled=not settings.n8n_enabled,
            help="Habilite N8N_ENABLED e configure a URL.",
        ):
            st.write(N8NClient().send({"event": "test", "alerts": [], "summary": {}}))


def about() -> None:
    st.markdown(
        """O **Innovation Governance Hub** é um projeto educacional e de portfólio para demonstrar governança de inovação, IA, orçamento, atas, Excel e automações.\n\nArquitetura: Streamlit → serviços → SQLAlchemy → SQLite. A FastAPI expõe somente automações. IA e n8n são adaptadores opcionais.\n\n**Este projeto utiliza exclusivamente dados fictícios e foi desenvolvido para fins educacionais e de portfólio. Não representa processos, políticas, resultados ou informações internas de nenhuma empresa real.**\n\nLimitações do MVP: uso local individual, sem autenticação, SQLite e arquivos locais; nenhuma decisão humana é automatizada."""
    )
