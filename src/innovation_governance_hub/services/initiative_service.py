from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from innovation_governance_hub.domain.clock import business_date
from innovation_governance_hub.exceptions import ValidationError
from innovation_governance_hub.persistence.models import Initiative
from innovation_governance_hub.services.audit_service import AuditService


class InitiativeService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, data: dict[str, object]) -> Initiative:
        highest = max(
            (
                int(code.split("-")[1])
                for code in self.session.scalars(select(Initiative.code)).all()
            ),
            default=0,
        )
        values = self._validate(data)
        values.setdefault("code", f"INI-{highest + 1:03d}")
        values.setdefault("created_date", business_date())
        values.setdefault("status", "Ativa")
        values.setdefault("current_stage", "Ideia")
        values.setdefault("expected_benefit", Decimal("0"))
        values.setdefault("notes", "")
        values["last_activity_at"] = datetime.now()
        initiative = Initiative(**values)
        self.session.add(initiative)
        self.session.flush()
        AuditService(self.session).record(
            event_type="initiative.created",
            entity_type="Iniciativa",
            entity_id=initiative.id,
            entity_code=initiative.code,
            action="criação",
            actor=str(data.get("actor", "Sistema")),
            summary=f"Iniciativa {initiative.code} criada.",
        )
        return initiative

    def update(self, initiative_id: int, data: dict[str, object]) -> Initiative:
        initiative = self.session.get(Initiative, initiative_id)
        if not initiative:
            raise ValidationError("Iniciativa não encontrada.")
        values = self._validate(data)
        changes = {}
        for key, value in values.items():
            if key not in {"code", "current_stage"}:
                previous = getattr(initiative, key)
                if previous != value:
                    changes[key] = {"before": previous, "after": value}
                setattr(initiative, key, value)
        initiative.last_activity_at = datetime.now()
        if changes:
            AuditService(self.session).record(
                event_type="initiative.updated",
                entity_type="Iniciativa",
                entity_id=initiative.id,
                entity_code=initiative.code,
                action="edição",
                actor=str(data.get("actor", "Sistema")),
                summary=f"Iniciativa {initiative.code} atualizada.",
                changes=changes,
            )
        return initiative

    @staticmethod
    def _validate(data: dict[str, object]) -> dict[str, object]:
        required = ["name", "problem_description", "requesting_area", "owner"]
        if any(not str(data.get(field, "")).strip() for field in required):
            raise ValidationError("Nome, problema, área e responsável são obrigatórios.")
        planned = Decimal(str(data.get("planned_cost", 0)))
        if planned < 0:
            raise ValidationError("O custo planejado não pode ser negativo.")
        values = {key: value for key, value in data.items() if key != "actor"}
        values["planned_cost"] = planned
        return values
