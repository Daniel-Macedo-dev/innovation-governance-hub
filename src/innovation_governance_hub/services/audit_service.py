import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from innovation_governance_hub.persistence.models import AuditEvent

SENSITIVE_KEYS = {"api_key", "password", "secret", "token", "authorization"}


def _safe(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return _safe(asdict(value))
    if isinstance(value, dict):
        return {
            str(key): _safe(item)
            for key, item in value.items()
            if not any(secret in str(key).lower() for secret in SENSITIVE_KEYS)
        }
    if isinstance(value, (list, tuple, set)):
        return [_safe(item) for item in value]
    return value


class AuditService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record(
        self,
        *,
        event_type: str,
        entity_type: str,
        entity_id: int | None,
        entity_code: str = "",
        action: str,
        actor: str,
        summary: str,
        changes: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_code=entity_code,
            action=action,
            actor=actor.strip() or "Sistema",
            summary=summary.strip(),
            changes_json=json.dumps(_safe(changes or {}), ensure_ascii=False, sort_keys=True),
            metadata_json=json.dumps(_safe(metadata or {}), ensure_ascii=False, sort_keys=True),
        )
        self.session.add(event)
        self.session.flush()
        return event

    def timeline(
        self, entity_type: str, entity_id: int, newest_first: bool = True
    ) -> list[AuditEvent]:
        order = AuditEvent.occurred_at.desc() if newest_first else AuditEvent.occurred_at.asc()
        return list(
            self.session.scalars(
                select(AuditEvent)
                .where(AuditEvent.entity_type == entity_type, AuditEvent.entity_id == entity_id)
                .order_by(order, AuditEvent.id.desc() if newest_first else AuditEvent.id.asc())
            ).all()
        )
