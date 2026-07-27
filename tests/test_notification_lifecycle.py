import pytest
from sqlalchemy import func, select

from innovation_governance_hub.exceptions import ValidationError
from innovation_governance_hub.persistence.models import AuditEvent, NotificationLog
from innovation_governance_hub.services.notification_service import NotificationService


def alert():
    return {
        "fingerprint": "abc",
        "notification_type": "prazo",
        "severity": "Alta",
        "entity_type": "Iniciativa",
        "entity_id": 1,
        "title": "Prazo vencido",
        "message": "Requer atenção",
    }


def test_alert_lifecycle_deduplicates_open_and_reopens_closed(session):
    service = NotificationService(session)
    first, created = service.register(**alert())
    assert created and first.lifecycle_status == "Novo"
    duplicate, created = service.register(**alert())
    assert not created and duplicate.id == first.id
    service.acknowledge(first.id, "Daniel")
    assert first.lifecycle_status == "Reconhecido"
    with pytest.raises(ValidationError):
        service.close(first.id, "Daniel", "")
    service.close(first.id, "Daniel", "Condição tratada")
    reopened, created = service.register(**alert())
    assert created and reopened.id == first.id and reopened.lifecycle_status == "Novo"
    assert session.scalar(select(func.count()).select_from(NotificationLog)) == 1
    assert session.scalar(select(func.count()).select_from(AuditEvent)) == 4


def test_ignore_requires_reason(session):
    item, _ = NotificationService(session).register(**alert())
    NotificationService(session).close(item.id, "Daniel", "Falso positivo", ignored=True)
    assert item.lifecycle_status == "Ignorado"
