from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from innovation_governance_hub.domain.enums import AIStatus, RiskLevel
from innovation_governance_hub.exceptions import ValidationError
from innovation_governance_hub.persistence.models import AIGovernanceDecision, AIUseCase
from innovation_governance_hub.services.audit_service import AuditService


def adoption(use_case: AIUseCase) -> float:
    if use_case.estimated_users <= 0:
        return 0.0
    return min(100.0, max(0.0, use_case.active_users / use_case.estimated_users * 100))


def validate_approval(use_case: AIUseCase, target: str) -> None:
    if target not in (AIStatus.APPROVED, AIStatus.RESTRICTED):
        return
    missing = []
    for ok, label in [
        (bool(use_case.owner.strip()), "responsável"),
        (use_case.policy_accepted, "política aceita"),
        (use_case.governance_approved, "aprovação da governança"),
        (bool(use_case.next_review_date), "próxima revisão"),
        (bool(use_case.data_description.strip()), "descrição dos dados"),
    ]:
        if not ok:
            missing.append(label)
    if use_case.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL) and (
        not use_case.risk_mitigation.strip() or not use_case.notes.strip()
    ):
        missing.append("mitigação e justificativa para alto risco")
    if missing:
        raise ValidationError("Aprovação inconsistente: " + ", ".join(missing))


def review_overdue(use_case: AIUseCase) -> bool:
    return bool(use_case.next_review_date and use_case.next_review_date < date.today())


class AIUseCaseService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def save(self, data: dict[str, object], use_case_id: int | None = None) -> AIUseCase:
        code = str(data.get("code", "")).strip()
        name = str(data.get("name", "")).strip()
        if not code or not name:
            raise ValidationError("Código e nome são obrigatórios.")
        duplicate = self.session.scalar(select(AIUseCase).where(AIUseCase.code == code))
        if duplicate and duplicate.id != use_case_id:
            raise ValidationError("Código de caso de IA já utilizado.")
        estimated = int(str(data.get("estimated_users", 0) or 0))
        active = int(str(data.get("active_users", 0) or 0))
        if estimated < 0 or active < 0 or active > estimated:
            raise ValidationError("Usuários ativos devem estar entre zero e a estimativa.")
        use_case = self.session.get(AIUseCase, use_case_id) if use_case_id else AIUseCase()
        if not use_case:
            raise ValidationError("Caso de IA não encontrado.")
        is_new = use_case_id is None
        previous_status = use_case.evaluation_status if not is_new else ""
        actor = str(data.get("actor", data.get("owner", "Sistema")))
        justification = str(data.get("justification", data.get("notes", ""))).strip()
        restrictions = str(data.get("restrictions", "")).strip()
        target = str(data.get("evaluation_status", previous_status))
        if target == AIStatus.RESTRICTED and not restrictions:
            raise ValidationError("Aprovação com restrições exige a descrição das restrições.")
        if target in (AIStatus.REJECTED, AIStatus.SUSPENDED) and not justification:
            raise ValidationError("Rejeição ou suspensão exige justificativa.")
        ignored = {"actor", "justification", "restrictions"}
        for key, value in data.items():
            if key in ignored:
                continue
            setattr(use_case, key, value)
        validate_approval(use_case, use_case.evaluation_status)
        self.session.add(use_case)
        self.session.flush()
        event = "ai_case.created" if is_new else "ai_case.updated"
        AuditService(self.session).record(
            event_type=event,
            entity_type="CasoIA",
            entity_id=use_case.id,
            entity_code=use_case.code,
            action="criação" if is_new else "avaliação",
            actor=actor,
            summary=f"Caso de IA {use_case.code} {'criado' if is_new else 'avaliado'}.",
            changes={"evaluation_status": {"before": previous_status, "after": target}},
        )
        if previous_status != target:
            self.session.add(
                AIGovernanceDecision(
                    ai_use_case_id=use_case.id,
                    previous_status=previous_status,
                    new_status=target,
                    risk_level=use_case.risk_level,
                    governance_approved=use_case.governance_approved,
                    policy_accepted=use_case.policy_accepted,
                    responsible=actor,
                    justification=justification,
                    restrictions=restrictions,
                    next_review_date=use_case.next_review_date,
                )
            )
        return use_case

    def suspend(self, use_case_id: int, actor: str, justification: str) -> AIUseCase:
        use_case = self.session.get(AIUseCase, use_case_id)
        if not use_case:
            raise ValidationError("Caso de IA não encontrado.")
        return self.save(
            {
                **{
                    column.name: getattr(use_case, column.name)
                    for column in AIUseCase.__table__.columns
                    if column.name not in {"id", "created_at", "updated_at"}
                },
                "evaluation_status": AIStatus.SUSPENDED,
                "governance_approved": False,
                "actor": actor,
                "justification": justification,
            },
            use_case.id,
        )

    def delete(self, use_case_id: int) -> None:
        raise ValidationError("Casos de IA preservam histórico; use a suspensão.")
