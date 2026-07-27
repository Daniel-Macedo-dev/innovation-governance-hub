from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from innovation_governance_hub.exceptions import ValidationError
from innovation_governance_hub.persistence.models import NotificationLog
from innovation_governance_hub.services.audit_service import AuditService

OPEN_STATUSES = {"Novo", "Reconhecido"}


class NotificationService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def acknowledge(self, notification_id: int, actor: str) -> NotificationLog:
        item = self._get(notification_id)
        if item.lifecycle_status not in OPEN_STATUSES:
            raise ValidationError("Somente alertas abertos podem ser reconhecidos.")
        item.lifecycle_status = "Reconhecido"
        item.acknowledged_at, item.acknowledged_by = datetime.now(), actor
        self._audit(item, actor, "reconhecimento")
        return item

    def close(
        self, notification_id: int, actor: str, note: str, ignored: bool = False
    ) -> NotificationLog:
        if not note.strip():
            raise ValidationError("Informe uma justificativa ou nota de resolução.")
        item = self._get(notification_id)
        item.lifecycle_status = "Ignorado" if ignored else "Resolvido"
        item.resolved_at, item.resolved_by, item.resolution_note = (
            datetime.now(),
            actor,
            note.strip(),
        )
        self._audit(item, actor, "ignorado" if ignored else "resolução")
        return item

    def register(self, **data: object) -> tuple[NotificationLog, bool]:
        fingerprint = str(data["fingerprint"])
        open_item = self.session.scalar(
            select(NotificationLog)
            .where(
                NotificationLog.fingerprint == fingerprint,
                NotificationLog.lifecycle_status.in_(OPEN_STATUSES),
            )
            .order_by(NotificationLog.id.desc())
        )
        if open_item:
            return open_item, False
        previous = self.session.scalar(
            select(NotificationLog)
            .where(NotificationLog.fingerprint == fingerprint)
            .order_by(NotificationLog.id.desc())
        )
        item = NotificationLog(**data, detected_at=datetime.now(), lifecycle_status="Novo")
        self.session.add(item)
        self.session.flush()
        self._audit(item, "Sistema", "reabertura" if previous else "detecção")
        return item, True

    def _get(self, notification_id: int) -> NotificationLog:
        item = self.session.get(NotificationLog, notification_id)
        if not item:
            raise ValidationError("Alerta não encontrado.")
        return item

    def _audit(self, item: NotificationLog, actor: str, action: str) -> None:
        AuditService(self.session).record(
            event_type=f"notification.{action}",
            entity_type="Alerta",
            entity_id=item.id,
            action=action,
            actor=actor,
            summary=f"Alerta '{item.title}': {action}.",
            metadata={"fingerprint": item.fingerprint, "status": item.lifecycle_status},
        )
