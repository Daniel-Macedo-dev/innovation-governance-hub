from datetime import date, datetime

from sqlalchemy.orm import Session

from innovation_governance_hub.exceptions import ValidationError
from innovation_governance_hub.persistence.models import (
    ActionItem,
    Initiative,
    Meeting,
    MeetingDecision,
)
from innovation_governance_hub.services.audit_service import AuditService


class MeetingService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        initiative_id: int,
        title: str,
        meeting_date: date,
        participants: str,
        minutes_text: str,
        executive_summary: str,
        decisions: list[str],
        actions: list[dict[str, object]],
        actor: str = "Sistema",
    ) -> Meeting:
        if not self.session.get(Initiative, initiative_id):
            raise ValidationError("Iniciativa não encontrada.")
        if not title.strip() or not minutes_text.strip():
            raise ValidationError("Título e ata são obrigatórios.")
        meeting = Meeting(
            initiative_id=initiative_id,
            title=title.strip(),
            meeting_date=meeting_date,
            participants=participants.strip(),
            minutes_text=minutes_text.strip(),
            executive_summary=executive_summary.strip(),
        )
        self.session.add(meeting)
        self.session.flush()
        for description in decisions:
            if description.strip():
                self.session.add(
                    MeetingDecision(meeting_id=meeting.id, description=description.strip())
                )
        for action in actions:
            description = str(action.get("description", "")).strip()
            owner = str(action.get("owner", "")).strip()
            if not description or not owner:
                raise ValidationError("Pendências exigem descrição e responsável.")
            deadline = action.get("deadline")
            if deadline is not None and not isinstance(deadline, date):
                raise ValidationError("Prazo da pendência inválido.")
            self.session.add(
                ActionItem(
                    meeting_id=meeting.id,
                    initiative_id=initiative_id,
                    description=description,
                    owner=owner,
                    deadline=deadline,
                    status="Aberta",
                )
            )
        AuditService(self.session).record(
            event_type="meeting.created",
            entity_type="Iniciativa",
            entity_id=initiative_id,
            action="registro de reunião",
            actor=actor,
            summary=f"Reunião {meeting.title} registrada.",
            metadata={
                "meeting_id": meeting.id,
                "decision_count": len(decisions),
                "action_count": len(actions),
            },
        )
        return meeting

    def update_action(self, action_id: int, data: dict[str, object], actor: str) -> ActionItem:
        action = self.session.get(ActionItem, action_id)
        if not action:
            raise ValidationError("Pendência não encontrada.")
        changes: dict[str, object] = {}
        for field in ("description", "owner", "deadline", "status"):
            if field in data and getattr(action, field) != data[field]:
                changes[field] = {"before": getattr(action, field), "after": data[field]}
                setattr(action, field, data[field])
        if not action.description.strip() or not action.owner.strip():
            raise ValidationError("Descrição e responsável são obrigatórios.")
        if action.status == "Concluída":
            action.completed_at = action.completed_at or datetime.now()
        elif action.status in {"Aberta", "Em andamento"}:
            action.completed_at = None
        if changes:
            AuditService(self.session).record(
                event_type="action.updated",
                entity_type="Iniciativa",
                entity_id=action.initiative_id,
                action="pendência atualizada",
                actor=actor,
                summary=f"Pendência '{action.description}' atualizada.",
                changes=changes,
                metadata={"action_id": action.id, "meeting_id": action.meeting_id},
            )
        return action

    def create_action(
        self,
        meeting_id: int,
        initiative_id: int,
        description: str,
        owner: str,
        deadline: date | None,
        actor: str,
    ) -> ActionItem:
        if not self.session.get(Meeting, meeting_id):
            raise ValidationError("Reunião não encontrada.")
        if not self.session.get(Initiative, initiative_id):
            raise ValidationError("Iniciativa não encontrada.")
        if not description.strip() or not owner.strip():
            raise ValidationError("Pendências exigem descrição e responsável.")
        action = ActionItem(
            meeting_id=meeting_id,
            initiative_id=initiative_id,
            description=description.strip(),
            owner=owner.strip(),
            deadline=deadline,
            status="Aberta",
        )
        self.session.add(action)
        self.session.flush()
        AuditService(self.session).record(
            event_type="action.created",
            entity_type="Iniciativa",
            entity_id=initiative_id,
            action="pendência criada",
            actor=actor,
            summary=f"Pendência '{action.description}' criada.",
            metadata={"action_id": action.id, "meeting_id": meeting_id},
        )
        return action

    def cancel_action(self, action_id: int, actor: str, reason: str) -> ActionItem:
        if not reason.strip():
            raise ValidationError("Cancelamento exige justificativa.")
        action = self.update_action(action_id, {"status": "Cancelada"}, actor)
        AuditService(self.session).record(
            event_type="action.cancelled",
            entity_type="Iniciativa",
            entity_id=action.initiative_id,
            action="pendência cancelada",
            actor=actor,
            summary=f"Pendência '{action.description}' cancelada.",
            metadata={"action_id": action.id, "reason": reason.strip()},
        )
        return action

    def reopen_action(self, action_id: int, actor: str, reason: str) -> ActionItem:
        if not reason.strip():
            raise ValidationError("Reabertura exige motivo.")
        action = self.update_action(action_id, {"status": "Aberta"}, actor)
        AuditService(self.session).record(
            event_type="action.reopened",
            entity_type="Iniciativa",
            entity_id=action.initiative_id,
            action="pendência reaberta",
            actor=actor,
            summary=f"Pendência '{action.description}' reaberta.",
            metadata={"action_id": action.id, "reason": reason.strip()},
        )
        return action
