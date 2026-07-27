from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from innovation_governance_hub.database import Base


def now() -> datetime:
    return datetime.now()


class Initiative(Base):
    __tablename__ = "initiatives"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    problem_description: Mapped[str] = mapped_column(Text)
    proposed_solution: Mapped[str] = mapped_column(Text, default="")
    requesting_area: Mapped[str] = mapped_column(String(120))
    owner: Mapped[str] = mapped_column(String(120))
    priority: Mapped[str] = mapped_column(String(30))
    expected_impact_level: Mapped[str] = mapped_column(String(30))
    expected_impact_description: Mapped[str] = mapped_column(Text, default="")
    complexity: Mapped[str] = mapped_column(String(30))
    created_date: Mapped[date] = mapped_column(Date)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    current_stage: Mapped[str] = mapped_column(String(30), index=True)
    planned_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    expected_benefit: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    notes: Mapped[str] = mapped_column(Text, default="")
    last_activity_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)
    strategic_theme: Mapped[str] = mapped_column(String(120), default="")


class InitiativeAssessment(Base):
    __tablename__ = "initiative_assessments"
    id: Mapped[int] = mapped_column(primary_key=True)
    initiative_id: Mapped[int] = mapped_column(
        ForeignKey("initiatives.id", ondelete="CASCADE"), unique=True, index=True
    )
    strategic_alignment: Mapped[int] = mapped_column(Integer)
    expected_value: Mapped[int] = mapped_column(Integer)
    urgency: Mapped[int] = mapped_column(Integer)
    confidence: Mapped[int] = mapped_column(Integer)
    complexity: Mapped[int] = mapped_column(Integer)
    execution_risk: Mapped[int] = mapped_column(Integer)
    rationale: Mapped[str] = mapped_column(Text)
    assessed_by: Mapped[str] = mapped_column(String(120))
    assessed_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class InitiativeIndicator(Base):
    __tablename__ = "initiative_indicators"
    id: Mapped[int] = mapped_column(primary_key=True)
    initiative_id: Mapped[int] = mapped_column(
        ForeignKey("initiatives.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    unit: Mapped[str] = mapped_column(String(40))
    baseline_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    target_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    current_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    direction: Mapped[str] = mapped_column(String(30))
    owner: Mapped[str] = mapped_column(String(120))
    measurement_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class GateCriterionDefinition(Base):
    __tablename__ = "gate_criterion_definitions"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    stage: Mapped[str] = mapped_column(String(30), index=True)
    mandatory: Mapped[bool] = mapped_column(Boolean, default=True)
    evaluation_type: Mapped[str] = mapped_column(String(30))
    display_order: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class InitiativeGateCheck(Base):
    __tablename__ = "initiative_gate_checks"
    __table_args__ = (UniqueConstraint("initiative_id", "criterion_definition_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    initiative_id: Mapped[int] = mapped_column(ForeignKey("initiatives.id", ondelete="CASCADE"))
    criterion_definition_id: Mapped[int] = mapped_column(
        ForeignKey("gate_criterion_definitions.id")
    )
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    evidence: Mapped[str] = mapped_column(Text, default="")
    completed_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)
    criterion: Mapped[GateCriterionDefinition] = relationship()


class StageTransition(Base):
    __tablename__ = "stage_transitions"
    id: Mapped[int] = mapped_column(primary_key=True)
    initiative_id: Mapped[int] = mapped_column(
        ForeignKey("initiatives.id", ondelete="CASCADE"), index=True
    )
    from_stage: Mapped[str] = mapped_column(String(30))
    to_stage: Mapped[str] = mapped_column(String(30))
    attempted_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    successful: Mapped[bool] = mapped_column(Boolean)
    reason: Mapped[str] = mapped_column(Text, default="")
    missing_criteria_snapshot: Mapped[str] = mapped_column(Text, default="[]")
    performed_by: Mapped[str] = mapped_column(String(120))


class InitiativeDocument(Base):
    __tablename__ = "initiative_documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    initiative_id: Mapped[int] = mapped_column(
        ForeignKey("initiatives.id", ondelete="CASCADE"), index=True
    )
    document_type: Mapped[str] = mapped_column(String(80))
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(255), unique=True)
    relative_path: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text, default="")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    uploaded_by: Mapped[str] = mapped_column(String(120))


class Meeting(Base):
    __tablename__ = "meetings"
    id: Mapped[int] = mapped_column(primary_key=True)
    initiative_id: Mapped[int] = mapped_column(
        ForeignKey("initiatives.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    meeting_date: Mapped[date] = mapped_column(Date)
    participants: Mapped[str] = mapped_column(Text)
    minutes_text: Mapped[str] = mapped_column(Text)
    executive_summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class MeetingDecision(Base):
    __tablename__ = "meeting_decisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    meeting_id: Mapped[int] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"), index=True
    )
    description: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class ActionItem(Base):
    __tablename__ = "action_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    meeting_id: Mapped[int] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"), index=True
    )
    initiative_id: Mapped[int] = mapped_column(
        ForeignKey("initiatives.id", ondelete="CASCADE"), index=True
    )
    description: Mapped[str] = mapped_column(Text)
    owner: Mapped[str] = mapped_column(String(120))
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="Aberta")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AIUseCase(Base):
    __tablename__ = "ai_use_cases"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    responsible_area: Mapped[str] = mapped_column(String(120))
    objective: Mapped[str] = mapped_column(Text)
    ai_tool: Mapped[str] = mapped_column(String(120))
    model_or_provider: Mapped[str] = mapped_column(String(120))
    data_description: Mapped[str] = mapped_column(Text, default="")
    uses_personal_data: Mapped[bool] = mapped_column(Boolean, default=False)
    risk_level: Mapped[str] = mapped_column(String(30), index=True)
    risk_mitigation: Mapped[str] = mapped_column(Text, default="")
    expected_impact: Mapped[str] = mapped_column(Text, default="")
    evaluation_status: Mapped[str] = mapped_column(String(40), index=True)
    owner: Mapped[str] = mapped_column(String(120), default="")
    next_review_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    policy_accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    governance_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    estimated_users: Mapped[int] = mapped_column(Integer, default=0)
    active_users: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class AIGovernanceDecision(Base):
    __tablename__ = "ai_governance_decisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    ai_use_case_id: Mapped[int] = mapped_column(
        ForeignKey("ai_use_cases.id", ondelete="CASCADE"), index=True
    )
    previous_status: Mapped[str] = mapped_column(String(40))
    new_status: Mapped[str] = mapped_column(String(40))
    risk_level: Mapped[str] = mapped_column(String(30))
    governance_approved: Mapped[bool] = mapped_column(Boolean)
    policy_accepted: Mapped[bool] = mapped_column(Boolean)
    responsible: Mapped[str] = mapped_column(String(120))
    justification: Mapped[str] = mapped_column(Text)
    restrictions: Mapped[str] = mapped_column(Text, default="")
    next_review_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)


class AnnualBudget(Base):
    __tablename__ = "annual_budgets"
    id: Mapped[int] = mapped_column(primary_key=True)
    year: Mapped[int] = mapped_column(Integer, unique=True)
    planned_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class Expense(Base):
    __tablename__ = "expenses"
    __table_args__ = (Index("ix_expense_competence_status", "competence_date", "financial_status"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    initiative_id: Mapped[int | None] = mapped_column(
        ForeignKey("initiatives.id"), nullable=True, index=True
    )
    competence_date: Mapped[date] = mapped_column(Date)
    category: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(250))
    supplier: Mapped[str] = mapped_column(String(120), default="")
    tool_name: Mapped[str] = mapped_column(String(120), default="")
    cost_type: Mapped[str] = mapped_column(String(30))
    financial_status: Mapped[str] = mapped_column(String(30))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class NotificationLog(Base):
    __tablename__ = "notification_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    notification_type: Mapped[str] = mapped_column(String(80))
    severity: Mapped[str] = mapped_column(String(30))
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    delivery_status: Mapped[str] = mapped_column(String(30), default="Detectada")
    delivery_channel: Mapped[str] = mapped_column(String(30), default="Local")
    external_reference: Mapped[str] = mapped_column(String(200), default="")
    error_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)
    lifecycle_status: Mapped[str] = mapped_column(String(30), default="Novo", index=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    acknowledged_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    resolution_note: Mapped[str] = mapped_column(Text, default="")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(50), index=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    entity_code: Mapped[str] = mapped_column(String(50), default="", index=True)
    action: Mapped[str] = mapped_column(String(50), index=True)
    actor: Mapped[str] = mapped_column(String(120))
    summary: Mapped[str] = mapped_column(String(500))
    changes_json: Mapped[str] = mapped_column(Text, default="{}")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)


class ImportBatch(Base):
    __tablename__ = "import_batches"
    id: Mapped[int] = mapped_column(primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    import_type: Mapped[str] = mapped_column(String(30), index=True)
    row_count: Mapped[int] = mapped_column(Integer)
    imported_by: Mapped[str] = mapped_column(String(120))
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=now)
