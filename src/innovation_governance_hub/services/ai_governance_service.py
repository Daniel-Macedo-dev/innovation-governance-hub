from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from innovation_governance_hub.domain.enums import AIStatus, RiskLevel
from innovation_governance_hub.exceptions import ValidationError
from innovation_governance_hub.persistence.models import AIUseCase


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
        for key, value in data.items():
            setattr(use_case, key, value)
        validate_approval(use_case, use_case.evaluation_status)
        self.session.add(use_case)
        self.session.flush()
        return use_case

    def delete(self, use_case_id: int) -> None:
        use_case = self.session.get(AIUseCase, use_case_id)
        if not use_case:
            raise ValidationError("Caso de IA não encontrado.")
        self.session.delete(use_case)
