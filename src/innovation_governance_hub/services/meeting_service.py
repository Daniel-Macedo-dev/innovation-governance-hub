from datetime import date

from sqlalchemy.orm import Session

from innovation_governance_hub.domain.schemas import MeetingSummaryResult
from innovation_governance_hub.exceptions import ValidationError
from innovation_governance_hub.persistence.models import (
    ActionItem,
    Initiative,
    Meeting,
    MeetingDecision,
)


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
        summary: MeetingSummaryResult,
        decisions: list[str],
        actions: list[dict[str, object]],
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
            executive_summary=summary.executive_summary.strip(),
            summary_provider=summary.provider_name,
            summary_mode=summary.mode,
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
        return meeting
