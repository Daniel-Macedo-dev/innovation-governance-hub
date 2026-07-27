from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from innovation_governance_hub.domain.clock import business_date
from innovation_governance_hub.persistence.models import (
    ActionItem,
    AIGovernanceDecision,
    AIUseCase,
    AuditEvent,
    Expense,
    Initiative,
    InitiativeAssessment,
    InitiativeDocument,
    InitiativeIndicator,
    Meeting,
    MeetingDecision,
    NotificationLog,
)
from innovation_governance_hub.services.ai_governance_service import adoption, review_overdue
from innovation_governance_hub.services.budget_service import BudgetService
from innovation_governance_hub.services.gate_service import GateService
from innovation_governance_hub.services.indicator_service import IndicatorService
from innovation_governance_hub.services.prioritization_service import PrioritizationService

INACTIVE_STATUSES = {"Concluída", "Arquivada"}
UNASSIGNED_AREA = "Área não informada"


def _row(model: object, *fields: str) -> dict[str, Any]:
    return {field: getattr(model, field) for field in fields}


def _is_active(item: Initiative) -> bool:
    return item.status not in INACTIVE_STATUSES


@dataclass(frozen=True)
class AreaDeliveryMetric:
    area: str
    active: int
    on_time: int
    overdue: int
    no_deadline: int

    @property
    def on_time_percentage(self) -> float:
        if self.active == 0:
            return 0.0
        return round(self.on_time / self.active * 100, 1)


def _area_delivery_metrics(
    initiatives: list[Initiative], reference: date
) -> list[AreaDeliveryMetric]:
    """Execução por área do portfólio ativo.

    Ativo = status diferente de Concluída/Arquivada. Uma iniciativa ativa está
    dentro do prazo quando o prazo é igual ou posterior à data de negócio; está
    atrasada quando o prazo é anterior; e conta como sem prazo quando não possui
    prazo — nesse caso o cumprimento não pode ser comprovado e reduz o percentual.
    """
    active_count: dict[str, int] = {}
    on_time: dict[str, int] = {}
    overdue: dict[str, int] = {}
    no_deadline: dict[str, int] = {}
    for item in initiatives:
        if not _is_active(item):
            continue
        area = item.requesting_area.strip() or UNASSIGNED_AREA
        active_count[area] = active_count.get(area, 0) + 1
        on_time.setdefault(area, 0)
        overdue.setdefault(area, 0)
        no_deadline.setdefault(area, 0)
        if item.deadline is None:
            no_deadline[area] += 1
        elif item.deadline >= reference:
            on_time[area] += 1
        else:
            overdue[area] += 1
    metrics = [
        AreaDeliveryMetric(
            area=area,
            active=active_count[area],
            on_time=on_time[area],
            overdue=overdue[area],
            no_deadline=no_deadline[area],
        )
        for area in active_count
    ]
    # Ordenação operacional: maior volume de ativos primeiro, desempate alfabético.
    return sorted(metrics, key=lambda metric: (-metric.active, metric.area))


@dataclass(frozen=True)
class PortfolioPriorityRow:
    initiative_id: int
    code: str
    name: str
    area: str
    theme: str
    stage: str
    priority: str
    owner: str
    health: str
    planned_cost: Decimal
    score: float
    value: float
    effort: float
    risk: int
    quadrant: str


class OverviewQueryService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def load(self) -> dict[str, Any]:
        today = business_date()
        initiatives = list(self.session.scalars(select(Initiative)).all())
        cases = list(self.session.scalars(select(AIUseCase)).all())
        totals = BudgetService(self.session).totals(today.year)
        active = [item for item in initiatives if _is_active(item)]
        area_delivery = _area_delivery_metrics(initiatives, today)
        return {
            "initiatives": [
                _row(
                    item,
                    "id",
                    "code",
                    "name",
                    "requesting_area",
                    "current_stage",
                    "status",
                    "deadline",
                )
                for item in initiatives
            ],
            "active": len(active),
            "overdue": sum(bool(item.deadline and item.deadline < today) for item in active),
            "area_delivery": area_delivery,
            "budget": totals,
            "ai_total": len(cases),
            "ai_approved": sum(item.evaluation_status == "Aprovado" for item in cases),
            "ai_overdue": sum(review_overdue(item) for item in cases),
        }


class PipelineQueryService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(self) -> list[dict[str, Any]]:
        items = self.session.scalars(select(Initiative).order_by(Initiative.code)).all()
        budget = BudgetService(self.session)
        return [
            {
                **_row(
                    item,
                    "id",
                    "code",
                    "name",
                    "requesting_area",
                    "owner",
                    "current_stage",
                    "status",
                    "priority",
                    "strategic_theme",
                    "deadline",
                    "planned_cost",
                ),
                "actual_cost": budget.initiative_actual(item.id),
            }
            for item in items
        ]


class InitiativeDetailsQueryService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def load(self, initiative_id: int) -> dict[str, Any] | None:
        item = self.session.get(Initiative, initiative_id)
        if not item:
            return None
        assessment = self.session.scalar(
            select(InitiativeAssessment).where(InitiativeAssessment.initiative_id == initiative_id)
        )
        indicators = list(
            self.session.scalars(
                select(InitiativeIndicator).where(
                    InitiativeIndicator.initiative_id == initiative_id
                )
            ).all()
        )
        actions = list(
            self.session.scalars(
                select(ActionItem)
                .where(ActionItem.initiative_id == initiative_id)
                .order_by(ActionItem.deadline)
            ).all()
        )
        events = list(
            self.session.scalars(
                select(AuditEvent)
                .where(
                    AuditEvent.entity_type == "Iniciativa", AuditEvent.entity_id == initiative_id
                )
                .order_by(AuditEvent.occurred_at.desc())
            ).all()
        )
        documents = list(
            self.session.scalars(
                select(InitiativeDocument)
                .where(InitiativeDocument.initiative_id == initiative_id)
                .order_by(InitiativeDocument.uploaded_at.desc())
            ).all()
        )
        return {
            "initiative": {
                **_row(
                    item,
                    "id",
                    "code",
                    "name",
                    "problem_description",
                    "proposed_solution",
                    "requesting_area",
                    "owner",
                    "priority",
                    "expected_impact_level",
                    "expected_impact_description",
                    "complexity",
                    "strategic_theme",
                    "current_stage",
                    "status",
                    "deadline",
                    "planned_cost",
                    "expected_benefit",
                    "notes",
                ),
                "actual_cost": BudgetService(self.session).initiative_actual(initiative_id),
            },
            "assessment": _row(
                assessment,
                "strategic_alignment",
                "expected_value",
                "urgency",
                "confidence",
                "complexity",
                "execution_risk",
                "rationale",
                "assessed_by",
            )
            if assessment
            else None,
            "indicators": [
                {
                    **_row(
                        value,
                        "id",
                        "name",
                        "description",
                        "unit",
                        "baseline_value",
                        "target_value",
                        "current_value",
                        "direction",
                        "owner",
                        "measurement_date",
                        "notes",
                    ),
                    **asdict(IndicatorService.status(value)),
                }
                for value in indicators
            ],
            "actions": [
                _row(
                    value,
                    "id",
                    "meeting_id",
                    "description",
                    "owner",
                    "deadline",
                    "status",
                    "completed_at",
                )
                for value in actions
            ],
            "events": [
                _row(value, "summary", "actor", "occurred_at", "event_type") for value in events
            ],
            "criteria": GateService(self.session).criteria_status(item),
            "documents": [
                _row(
                    value,
                    "id",
                    "document_type",
                    "original_filename",
                    "description",
                    "uploaded_at",
                    "uploaded_by",
                )
                for value in documents
            ],
        }


class AIGovernanceQueryService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(self) -> list[dict[str, Any]]:
        return [
            {
                **_row(
                    item,
                    "id",
                    "code",
                    "name",
                    "responsible_area",
                    "risk_level",
                    "evaluation_status",
                    "uses_personal_data",
                    "owner",
                    "next_review_date",
                    "governance_approved",
                    "risk_mitigation",
                ),
                "adoption": adoption(item),
                "review_overdue": review_overdue(item),
            }
            for item in self.session.scalars(select(AIUseCase).order_by(AIUseCase.code)).all()
        ]

    def detail(self, use_case_id: int) -> dict[str, Any] | None:
        item = self.session.get(AIUseCase, use_case_id)
        if not item:
            return None
        decisions = self.session.scalars(
            select(AIGovernanceDecision)
            .where(AIGovernanceDecision.ai_use_case_id == use_case_id)
            .order_by(AIGovernanceDecision.decided_at.desc())
        ).all()
        return {
            **_row(
                item,
                "id",
                "code",
                "name",
                "responsible_area",
                "objective",
                "ai_tool",
                "model_or_provider",
                "data_description",
                "uses_personal_data",
                "risk_level",
                "risk_mitigation",
                "expected_impact",
                "evaluation_status",
                "owner",
                "next_review_date",
                "policy_accepted",
                "governance_approved",
                "estimated_users",
                "active_users",
                "notes",
            ),
            "adoption": adoption(item),
            "review_overdue": review_overdue(item),
            "decisions": [
                _row(
                    decision,
                    "previous_status",
                    "new_status",
                    "risk_level",
                    "governance_approved",
                    "responsible",
                    "justification",
                    "restrictions",
                    "next_review_date",
                    "decided_at",
                )
                for decision in decisions
            ],
        }


class BudgetQueryService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def load(self, year: int) -> dict[str, Any]:
        service = BudgetService(self.session)
        expenses = self.session.scalars(
            select(Expense).order_by(Expense.competence_date.desc())
        ).all()
        initiatives = {item.id: item for item in self.session.scalars(select(Initiative)).all()}
        over_budget = [
            {
                "code": item.code,
                "name": item.name,
                "planned_cost": item.planned_cost,
                "actual_cost": service.initiative_actual(item.id),
            }
            for item in service.over_budget()
        ]
        return {
            "projection": service.projection(year, business_date()),
            "categories": service.category_totals(year),
            "over_budget": over_budget,
            "initiatives": [
                {"id": item.id, "code": item.code, "name": item.name}
                for item in sorted(initiatives.values(), key=lambda value: value.code)
            ],
            "expenses": [
                _row(
                    item,
                    "id",
                    "initiative_id",
                    "competence_date",
                    "category",
                    "description",
                    "tool_name",
                    "cost_type",
                    "financial_status",
                    "amount",
                )
                for item in expenses
            ],
        }


class MeetingQueryService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def load(self) -> dict[str, Any]:
        meetings = self.session.scalars(select(Meeting).order_by(Meeting.meeting_date.desc())).all()
        actions = self.session.scalars(select(ActionItem).order_by(ActionItem.deadline)).all()
        decisions = self.session.scalars(select(MeetingDecision)).all()
        return {
            "meetings": [
                _row(
                    item,
                    "id",
                    "initiative_id",
                    "title",
                    "meeting_date",
                    "participants",
                    "minutes_text",
                    "executive_summary",
                )
                for item in meetings
            ],
            "decisions": [_row(item, "meeting_id", "description") for item in decisions],
            "actions": [
                _row(
                    item,
                    "id",
                    "meeting_id",
                    "initiative_id",
                    "description",
                    "owner",
                    "deadline",
                    "status",
                    "completed_at",
                )
                for item in actions
            ],
        }


class AutomationQueryService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(self) -> list[dict[str, Any]]:
        rows = self.session.scalars(
            select(NotificationLog).order_by(NotificationLog.detected_at.desc())
        ).all()
        return [
            _row(
                item,
                "id",
                "notification_type",
                "severity",
                "entity_type",
                "entity_id",
                "title",
                "message",
                "detected_at",
                "lifecycle_status",
                "acknowledged_by",
                "resolution_note",
            )
            for item in rows
        ]


class PrioritizationQueryService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def portfolio(self, health_by_id: dict[int, str]) -> list[PortfolioPriorityRow]:
        initiatives = {item.id: item for item in self.session.scalars(select(Initiative)).all()}
        rows = []
        for assessment in self.session.scalars(select(InitiativeAssessment)).all():
            item = initiatives.get(assessment.initiative_id)
            if not item:
                continue
            result = PrioritizationService.calculate(assessment)
            rows.append(
                PortfolioPriorityRow(
                    item.id,
                    item.code,
                    item.name,
                    item.requesting_area,
                    item.strategic_theme or "Não definido",
                    item.current_stage,
                    item.priority,
                    item.owner,
                    health_by_id.get(item.id, "Saudável"),
                    item.planned_cost,
                    result.score,
                    result.value,
                    result.effort,
                    assessment.execution_risk,
                    result.quadrant,
                )
            )
        return sorted(rows, key=lambda value: value.score, reverse=True)
