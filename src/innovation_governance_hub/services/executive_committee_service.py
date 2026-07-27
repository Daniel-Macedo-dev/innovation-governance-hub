from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from innovation_governance_hub.config import get_settings
from innovation_governance_hub.domain.clock import business_date
from innovation_governance_hub.persistence.models import (
    ActionItem,
    AIUseCase,
    AnnualBudget,
    AuditEvent,
    Initiative,
    InitiativeIndicator,
    NotificationLog,
)
from innovation_governance_hub.services.budget_service import BudgetService
from innovation_governance_hub.services.indicator_service import IndicatorService


@dataclass(frozen=True)
class ExecutiveMetric:
    label: str
    value: str


@dataclass(frozen=True)
class DecisionRequired:
    kind: str
    entity: str
    reason: str
    severity: str
    owner: str
    deadline: str
    recommendation: str


@dataclass(frozen=True)
class PortfolioHealthItem:
    initiative_id: int
    name: str
    status: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class CommitteeBrief:
    position_date: str
    active_initiatives: int
    decisions: tuple[DecisionRequired, ...]
    health: tuple[PortfolioHealthItem, ...]
    financial: tuple[ExecutiveMetric, ...]
    ai: tuple[ExecutiveMetric, ...]
    indicators: tuple[ExecutiveMetric, ...]
    next_actions: tuple[DecisionRequired, ...]
    changes: tuple[str, ...]
    narrative: str


class ExecutiveCommitteeService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def brief(self, change_days: int = 15) -> CommitteeBrief:
        today = business_date()
        initiatives = list(self.session.scalars(select(Initiative)).all())
        active = [item for item in initiatives if item.status not in {"Concluída", "Arquivada"}]
        actions = list(
            self.session.scalars(
                select(ActionItem).where(ActionItem.status.in_(["Aberta", "Em andamento"]))
            ).all()
        )
        cases = list(self.session.scalars(select(AIUseCase)).all())
        alerts = list(
            self.session.scalars(
                select(NotificationLog).where(
                    NotificationLog.lifecycle_status.in_(["Novo", "Reconhecido"])
                )
            ).all()
        )
        decisions: list[DecisionRequired] = []
        for item in active:
            if item.status == "Bloqueada" or (item.deadline and item.deadline < today):
                decisions.append(
                    DecisionRequired(
                        "Iniciativa",
                        item.name,
                        "Bloqueio explícito" if item.status == "Bloqueada" else "Prazo vencido",
                        "Crítica",
                        item.owner,
                        item.deadline.isoformat() if item.deadline else "Sem prazo",
                        "Revisar impedimento e registrar decisão humana.",
                    )
                )
        for case in cases:
            if case.risk_level in {"Alto", "Crítico"} and (
                not case.governance_approved
                or (case.next_review_date and case.next_review_date < today)
            ):
                decisions.append(
                    DecisionRequired(
                        "Governança de IA",
                        case.name,
                        "Risco elevado ou revisão pendente",
                        "Crítica",
                        case.owner,
                        case.next_review_date.isoformat() if case.next_review_date else "Sem prazo",
                        "Submeter à revisão de governança; não aprovar automaticamente.",
                    )
                )
        for action in actions:
            if action.deadline and action.deadline < today:
                decisions.append(
                    DecisionRequired(
                        "Pendência",
                        action.description,
                        "Pendência vencida",
                        "Atenção",
                        action.owner,
                        action.deadline.isoformat(),
                        "Confirmar responsável e novo compromisso.",
                    )
                )
        for alert in alerts:
            if alert.severity == "Crítica":
                decisions.append(
                    DecisionRequired(
                        "Alerta",
                        alert.title,
                        alert.message,
                        alert.severity,
                        alert.acknowledged_by or "Não definido",
                        "Imediato",
                        "Reconhecer e encaminhar ao responsável.",
                    )
                )
        health = tuple(self._health(item, actions) for item in initiatives)
        budget = self.session.scalar(select(AnnualBudget).where(AnnualBudget.year == today.year))
        projection = BudgetService(self.session).projection(today.year, today)
        financial = (
            tuple(
                ExecutiveMetric(label, value)
                for label, value in (
                    ("Orçamento anual", self._money(Decimal(projection["planned"]))),
                    ("Realizado", self._money(Decimal(projection["actual"]))),
                    ("Comprometido", self._money(Decimal(projection["committed"]))),
                    (
                        "Saldo após compromissos",
                        self._money(Decimal(projection["balance_after_commitments"])),
                    ),
                    (
                        "Projeção até dezembro",
                        self._money(Decimal(projection["year_end_projection"])),
                    ),
                )
            )
            if budget
            else ()
        )
        high_risk = sum(case.risk_level in {"Alto", "Crítico"} for case in cases)
        overdue_reviews = sum(
            bool(case.next_review_date and case.next_review_date < today) for case in cases
        )
        ai = (
            ExecutiveMetric("Total de casos", str(len(cases))),
            ExecutiveMetric("Alto ou crítico risco", str(high_risk)),
            ExecutiveMetric("Revisões vencidas", str(overdue_reviews)),
            ExecutiveMetric(
                "Usam dados pessoais", str(sum(case.uses_personal_data for case in cases))
            ),
        )
        indicator_rows = list(self.session.scalars(select(InitiativeIndicator)).all())
        statuses = [IndicatorService.status(row).status for row in indicator_rows]
        indicators = (
            ExecutiveMetric(
                "Iniciativas com indicadores",
                str(len({row.initiative_id for row in indicator_rows})),
            ),
            ExecutiveMetric("No caminho", str(statuses.count("No caminho"))),
            ExecutiveMetric("Em atenção", str(statuses.count("Atenção"))),
            ExecutiveMetric("Fora do esperado", str(statuses.count("Fora do esperado"))),
            ExecutiveMetric(
                "Sem indicador",
                str(len(active) - len({row.initiative_id for row in indicator_rows})),
            ),
        )
        since = today - timedelta(days=change_days)
        changes = tuple(
            self.session.scalars(
                select(AuditEvent.summary)
                .where(func.date(AuditEvent.occurred_at) >= since)
                .order_by(AuditEvent.occurred_at.desc())
                .limit(20)
            ).all()
        )
        next_actions = tuple(
            DecisionRequired(
                "Pendência",
                action.description,
                "Vencida" if action.deadline and action.deadline < today else "Próximos 7 dias",
                "Crítica" if action.deadline and action.deadline < today else "Atenção",
                action.owner,
                action.deadline.isoformat() if action.deadline else "Sem prazo",
                "Acompanhar na reunião ou iniciativa relacionada.",
            )
            for action in actions
            if action.deadline and action.deadline <= today + timedelta(days=7)
        )
        narrative = self._narrative(
            len(active), len(decisions), high_risk, overdue_reviews, projection if budget else None
        )
        return CommitteeBrief(
            today.isoformat(),
            len(active),
            tuple(decisions),
            health,
            financial,
            ai,
            indicators,
            next_actions,
            changes,
            narrative,
        )

    def _health(self, item: Initiative, actions: list[ActionItem]) -> PortfolioHealthItem:
        today = business_date()
        if item.status in {"Concluída", "Arquivada"}:
            return PortfolioHealthItem(
                item.id, item.name, item.status, ("Status informado pelo responsável.",)
            )
        critical = []
        if item.status == "Bloqueada":
            critical.append("Bloqueio explícito")
        if item.deadline and item.deadline < today:
            critical.append("Prazo vencido")
        if any(
            action.initiative_id == item.id
            and action.deadline
            and action.deadline < today
            and action.status != "Concluída"
            for action in actions
        ):
            critical.append("Pendência vencida")
        if critical:
            return PortfolioHealthItem(item.id, item.name, "Crítica", tuple(critical))
        attention = []
        if item.deadline and item.deadline <= today + timedelta(days=14):
            attention.append("Prazo próximo")
        if item.last_activity_at.date() < today - timedelta(
            days=get_settings().stale_project_days - 3
        ):
            attention.append("Atividade próxima do limite")
        return PortfolioHealthItem(
            item.id,
            item.name,
            "Atenção" if attention else "Saudável",
            tuple(attention or ["Sem condição de risco identificada."]),
        )

    @staticmethod
    def _money(value: Decimal) -> str:
        return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    @staticmethod
    def _narrative(
        active: int,
        decisions: int,
        high_risk: int,
        overdue: int,
        projection: dict[str, Decimal | int] | None,
    ) -> str:
        text = f"O portfólio possui {active} iniciativa{'s' if active != 1 else ''} ativa{'s' if active != 1 else ''}. {decisions} {'exigem' if decisions != 1 else 'exige'} decisão nesta revisão. Existem {high_risk} caso{'s' if high_risk != 1 else ''} de IA de alto ou crítico risco e {overdue} revisão{'ões' if overdue != 1 else ''} vencida{'s' if overdue != 1 else ''}."
        if projection and Decimal(projection["planned"]):
            percent = (
                Decimal(projection["year_end_projection"]) / Decimal(projection["planned"]) * 100
            )
            text += f" A projeção anual indica consumo de {percent:.1f}% do orçamento."
        return text
