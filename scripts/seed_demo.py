from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from innovation_governance_hub.database import SessionLocal, init_db
from innovation_governance_hub.domain.clock import business_date
from innovation_governance_hub.domain.enums import (
    AIStatus,
    FinancialStatus,
    InitiativeStatus,
    RiskLevel,
    Stage,
)
from innovation_governance_hub.domain.gate_definitions import GATE_DEFINITIONS
from innovation_governance_hub.persistence.models import (
    ActionItem,
    AIUseCase,
    AnnualBudget,
    Expense,
    GateCriterionDefinition,
    Initiative,
    InitiativeAssessment,
    InitiativeIndicator,
    Meeting,
    MeetingDecision,
    StageTransition,
)

NAMES = [
    "Previsão de demanda com IA",
    "Chatbot interno para RH",
    "Automação de conferência de documentos",
    "Otimização de rotas",
    "Leitura automática de notas fiscais",
    "Painel de eficiência operacional",
    "Manutenção preditiva",
    "Classificação automática de chamados",
    "Assistente de consulta a políticas",
    "Extração de informações de contratos",
    "Monitoramento de indicadores operacionais",
    "Automação de cadastro de fornecedores",
    "Gestão de conhecimento interno",
    "Análise de consumo energético",
    "Previsão de ocupação",
    "Auditoria automatizada de planilhas",
    "Roteirização de visitas técnicas",
    "Portal de ideias",
    "Monitoramento de SLA",
    "Consolidação automática de relatórios",
]
AREAS = ["Operações", "Pessoas", "Financeiro", "Logística", "Suprimentos", "Tecnologia"]


def seed() -> dict[str, int]:
    init_db()
    with SessionLocal.begin() as session:
        order = 1
        for stage, definitions in GATE_DEFINITIONS.items():
            for code, name, evaluation in definitions:
                if not session.scalar(
                    select(GateCriterionDefinition).where(GateCriterionDefinition.code == code)
                ):
                    session.add(
                        GateCriterionDefinition(
                            code=code,
                            name=name,
                            description=name,
                            stage=stage,
                            mandatory=True,
                            evaluation_type=evaluation,
                            display_order=order,
                            active=True,
                        )
                    )
                order += 1
        stages = [
            Stage.IDEA,
            Stage.SCREENING,
            Stage.DISCOVERY,
            Stage.VALIDATION,
            Stage.PILOT,
            Stage.SCALE,
            Stage.COMPLETED,
            Stage.ARCHIVED,
        ]
        for idx, name in enumerate(NAMES, 1):
            code = f"INI-{idx:03d}"
            if not session.scalar(select(Initiative).where(Initiative.code == code)):
                stage = stages[(idx - 1) % len(stages)]
                status = (
                    InitiativeStatus.COMPLETED
                    if stage == Stage.COMPLETED
                    else InitiativeStatus.ARCHIVED
                    if stage == Stage.ARCHIVED
                    else InitiativeStatus.BLOCKED
                    if idx in (3, 11)
                    else InitiativeStatus.ACTIVE
                )
                session.add(
                    Initiative(
                        code=code,
                        name=name,
                        problem_description="Processo manual com retrabalho e baixa visibilidade.",
                        proposed_solution="Experimentar solução digital com métricas de sucesso.",
                        requesting_area=AREAS[(idx - 1) % len(AREAS)],
                        owner=f"Pessoa Fictícia {idx}",
                        priority=["Baixa", "Média", "Alta", "Crítica"][idx % 4],
                        expected_impact_level=["Baixo", "Médio", "Alto", "Muito alto"][idx % 4],
                        expected_impact_description="Reduzir tempo operacional em cenário demonstrativo.",
                        complexity=["Baixa", "Média", "Alta"][idx % 3],
                        created_date=business_date() - timedelta(days=150 + idx),
                        deadline=business_date() - timedelta(days=idx)
                        if idx % 4 == 0
                        else business_date() + timedelta(days=30 + idx),
                        status=status,
                        current_stage=stage,
                        planned_cost=Decimal(15000 + idx * 4000),
                        expected_benefit=Decimal(30000 + idx * 7000),
                        notes="Dados totalmente fictícios.",
                        last_activity_at=datetime.now()
                        - timedelta(days=25 if idx % 5 == 0 else idx % 10),
                    )
                )
        session.flush()
        initiatives = session.scalars(select(Initiative).order_by(Initiative.id)).all()
        if not session.scalar(
            select(AnnualBudget).where(AnnualBudget.year == business_date().year)
        ):
            session.add(
                AnnualBudget(
                    year=business_date().year,
                    planned_amount=Decimal("1200000"),
                    notes="Orçamento fictício demonstrativo.",
                )
            )
        for month in range(1, 9):
            for idx in range(1, 6):
                description = f"Despesa demo {month}-{idx}"
                if not session.scalar(select(Expense).where(Expense.description == description)):
                    planned = initiatives[(month + idx) % len(initiatives)].planned_cost
                    amount = (
                        planned * Decimal("1.15")
                        if month == 1 and idx == 1
                        else Decimal(3500 + month * idx * 420)
                    )
                    session.add(
                        Expense(
                            initiative_id=initiatives[(month + idx) % len(initiatives)].id,
                            competence_date=date(business_date().year, month, 10),
                            category=[
                                "Ferramentas e software",
                                "Fornecedores",
                                "Consultoria",
                                "Infraestrutura",
                                "Treinamento",
                            ][idx - 1],
                            description=description,
                            supplier=f"Fornecedor Fictício {idx}",
                            tool_name=f"Ferramenta Demo {idx}",
                            cost_type="Recorrente" if idx % 2 else "Pontual",
                            financial_status=FinancialStatus.ACTUAL
                            if month <= business_date().month
                            else FinancialStatus.FORECAST,
                            amount=amount,
                        )
                    )
        for idx in range(1, 13):
            code = f"IA-{idx:03d}"
            if not session.scalar(select(AIUseCase).where(AIUseCase.code == code)):
                risk = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL][
                    idx % 4
                ]
                approved = idx % 3 == 0
                session.add(
                    AIUseCase(
                        code=code,
                        name=f"Caso de IA demonstrativo {idx}",
                        responsible_area=AREAS[idx % len(AREAS)],
                        objective="Apoiar análise humana sem substituir decisão final.",
                        ai_tool=f"Assistente Fictício {idx}",
                        model_or_provider="Provedor demonstrativo",
                        data_description="Dados sintéticos e documentos fictícios.",
                        uses_personal_data=idx % 4 == 0,
                        risk_level=risk,
                        risk_mitigation="Revisão humana, minimização e auditoria."
                        if risk in (RiskLevel.HIGH, RiskLevel.CRITICAL)
                        else "Revisão periódica.",
                        expected_impact="Ganho potencial não comprovado.",
                        evaluation_status=AIStatus.APPROVED if approved else AIStatus.EVALUATING,
                        owner=f"Responsável IA {idx}",
                        next_review_date=business_date() - timedelta(days=idx)
                        if idx % 4 == 0
                        else business_date() + timedelta(days=60),
                        policy_accepted=approved,
                        governance_approved=approved,
                        estimated_users=100 + idx * 10,
                        active_users=min(100 + idx * 10, idx * 14),
                        notes="Justificativa fictícia para demonstração.",
                    )
                )
        first = initiatives[0]
        assessment_profiles = (
            (5, 5, 5, 4, 1, 1),
            (5, 4, 4, 4, 4, 4),
            (2, 2, 3, 3, 2, 2),
            (2, 2, 2, 2, 5, 4),
            (4, 5, 3, 4, 2, 2),
            (4, 4, 4, 3, 4, 3),
            (3, 3, 4, 4, 2, 1),
            (2, 3, 2, 3, 4, 5),
        )
        for initiative, assessment_profile in zip(
            initiatives[:8], assessment_profiles, strict=True
        ):
            if not session.scalar(
                select(InitiativeAssessment).where(
                    InitiativeAssessment.initiative_id == initiative.id
                )
            ):
                session.add(
                    InitiativeAssessment(
                        initiative_id=initiative.id,
                        strategic_alignment=assessment_profile[0],
                        expected_value=assessment_profile[1],
                        urgency=assessment_profile[2],
                        confidence=assessment_profile[3],
                        complexity=assessment_profile[4],
                        execution_risk=assessment_profile[5],
                        rationale="Avaliação fictícia preparada para o comitê.",
                        assessed_by="Comitê demonstrativo",
                    )
                )
        indicator_profiles = (
            ("Redução do tempo de ciclo", "Dias", 20, 8, 9, "Reduzir", -1),
            ("Adoção do processo", "Percentual", 20, 80, 62, "Aumentar", -3),
            ("Erros operacionais", "Quantidade", 30, 5, 24, "Reduzir", -8),
            ("Benefício validado", "Real", 0, 100000, None, "Aumentar", None),
        )
        for initiative, indicator_profile in zip(initiatives[:4], indicator_profiles, strict=True):
            if not session.scalar(
                select(InitiativeIndicator).where(
                    InitiativeIndicator.initiative_id == initiative.id,
                    InitiativeIndicator.name == indicator_profile[0],
                )
            ):
                session.add(
                    InitiativeIndicator(
                        initiative_id=initiative.id,
                        name=indicator_profile[0],
                        description="Indicador fictício de resultado para demonstração.",
                        unit=indicator_profile[1],
                        baseline_value=Decimal(indicator_profile[2]),
                        target_value=Decimal(indicator_profile[3]),
                        current_value=Decimal(indicator_profile[4])
                        if indicator_profile[4] is not None
                        else None,
                        direction=indicator_profile[5],
                        owner=f"Responsável Indicador {initiative.id}",
                        measurement_date=(business_date() + timedelta(days=indicator_profile[6]))
                        if indicator_profile[6] is not None
                        else None,
                        notes="Dados totalmente fictícios.",
                    )
                )
        if not session.scalar(select(Meeting).where(Meeting.title == "Kick-off demonstrativo")):
            meeting = Meeting(
                initiative_id=first.id,
                title="Kick-off demonstrativo",
                meeting_date=business_date() - timedelta(days=20),
                participants="Ana Demo; Bruno Exemplo",
                minutes_text="Foi decidido validar o protótipo. Ana deve preparar métricas até 15/08/2026.",
                executive_summary="Validação do protótipo e definição de métricas.",
                summary_provider="Regras locais determinísticas",
                summary_mode="Modo demonstração local",
            )
            session.add(meeting)
            session.flush()
            session.add(
                MeetingDecision(
                    meeting_id=meeting.id, description="Validar o protótipo com dados sintéticos."
                )
            )
            session.add(
                ActionItem(
                    meeting_id=meeting.id,
                    initiative_id=first.id,
                    description="Preparar métricas do piloto.",
                    owner="Ana Demo",
                    deadline=business_date() - timedelta(days=2),
                    status="Aberta",
                )
            )
            session.add_all(
                [
                    ActionItem(
                        meeting_id=meeting.id,
                        initiative_id=first.id,
                        description="Revisar evidências do próximo gate.",
                        owner="Bruno Exemplo",
                        deadline=business_date() + timedelta(days=5),
                        status="Em andamento",
                    ),
                    ActionItem(
                        meeting_id=meeting.id,
                        initiative_id=first.id,
                        description="Consolidar aprendizados do experimento.",
                        owner="Ana Demo",
                        deadline=business_date() - timedelta(days=7),
                        status="Concluída",
                        completed_at=datetime.now() - timedelta(days=6),
                    ),
                ]
            )
        if not session.scalar(select(StageTransition.id)):
            session.add(
                StageTransition(
                    initiative_id=first.id,
                    from_stage=Stage.IDEA,
                    to_stage=Stage.SCREENING,
                    successful=False,
                    reason="Critérios obrigatórios pendentes",
                    missing_criteria_snapshot='["Impacto preliminar estimado"]',
                    performed_by="Usuário demonstrativo",
                )
            )
        session.flush()
        return {
            "iniciativas": len(session.scalars(select(Initiative)).all()),
            "casos_ia": len(session.scalars(select(AIUseCase)).all()),
            "despesas": len(session.scalars(select(Expense)).all()),
            "reunioes": len(session.scalars(select(Meeting)).all()),
        }


def main() -> None:
    print(seed())


if __name__ == "__main__":
    main()
