from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from innovation_governance_hub.exceptions import ValidationError
from innovation_governance_hub.persistence.models import Initiative, InitiativeIndicator
from innovation_governance_hub.services.audit_service import AuditService


@dataclass(frozen=True)
class InitiativeIndicatorResult:
    indicator_id: int
    status: str
    progress_percent: float | None


class IndicatorService:
    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def status(indicator: InitiativeIndicator) -> InitiativeIndicatorResult:
        if (
            indicator.current_value is None
            or indicator.baseline_value is None
            or indicator.target_value is None
        ):
            return InitiativeIndicatorResult(indicator.id, "Sem medição", None)
        baseline, target, current = map(
            Decimal, (indicator.baseline_value, indicator.target_value, indicator.current_value)
        )
        if target == baseline:
            progress = Decimal(100) if current == target else Decimal(0)
        elif indicator.direction == "Reduzir":
            progress = (baseline - current) / (baseline - target) * 100
        else:
            progress = (current - baseline) / (target - baseline) * 100
        status = (
            "No caminho" if progress >= 80 else "Atenção" if progress >= 50 else "Fora do esperado"
        )
        return InitiativeIndicatorResult(indicator.id, status, round(float(progress), 1))

    def save(
        self,
        initiative_id: int,
        data: dict[str, object],
        actor: str,
        indicator_id: int | None = None,
    ) -> InitiativeIndicatorResult:
        if not self.session.get(Initiative, initiative_id):
            raise ValidationError("Iniciativa não encontrada.")
        indicator = (
            self.session.get(InitiativeIndicator, indicator_id)
            if indicator_id
            else InitiativeIndicator(initiative_id=initiative_id)
        )
        if indicator is None:
            raise ValidationError("Indicador não encontrado.")
        for field, value in data.items():
            setattr(indicator, field, value)
        if not indicator.name.strip() or indicator.direction not in {
            "Aumentar",
            "Reduzir",
            "Manter faixa",
        }:
            raise ValidationError("Nome e direção válida são obrigatórios.")
        self.session.add(indicator)
        self.session.flush()
        result = self.status(indicator)
        AuditService(self.session).record(
            event_type="indicator.saved",
            entity_type="Iniciativa",
            entity_id=initiative_id,
            action="indicador",
            actor=actor,
            summary=f"Indicador '{indicator.name}' atualizado: {result.status}.",
            metadata={"indicator_id": indicator.id, "status": result.status},
        )
        return result
