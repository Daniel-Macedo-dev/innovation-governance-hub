from datetime import date
from decimal import Decimal

import pytest

from innovation_governance_hub.config import Settings
from innovation_governance_hub.domain.schemas import MeetingSummaryResult
from innovation_governance_hub.exceptions import ValidationError
from innovation_governance_hub.persistence.models import ActionItem, Initiative, MeetingDecision
from innovation_governance_hub.services.document_service import DocumentService
from innovation_governance_hub.services.meeting_service import MeetingService


def initiative():
    return Initiative(
        code="INI-DOC",
        name="Documento",
        problem_description="Problema",
        proposed_solution="Solução",
        requesting_area="Área",
        owner="Pessoa",
        priority="Média",
        expected_impact_level="Médio",
        expected_impact_description="",
        complexity="Média",
        created_date=date.today(),
        deadline=None,
        status="Ativa",
        current_stage="Ideia",
        planned_cost=Decimal("10"),
        expected_benefit=Decimal("20"),
        notes="",
    )


def summary():
    return MeetingSummaryResult(
        executive_summary="Resumo",
        decisions=["Decisão"],
        action_items=["Ação"],
        provider_name="Local",
        mode="Modo demonstração local",
    )


def test_document_save_and_delete(session, tmp_path):
    item = initiative()
    session.add(item)
    session.flush()
    service = DocumentService(session, Settings(upload_dir=tmp_path / "uploads"))
    document = service.save(
        item.id,
        "evidência?.txt",
        "conteúdo".encode(),
        "Descoberta",
        "Teste",
        "Pessoa",
    )
    path = tmp_path / "uploads" / document.stored_filename
    assert path.exists()
    assert "?" not in document.original_filename
    service.delete(document.id)
    assert not path.exists()


def test_document_rejects_extension_and_size(session, tmp_path):
    item = initiative()
    session.add(item)
    session.flush()
    service = DocumentService(session, Settings(upload_dir=tmp_path))
    with pytest.raises(ValidationError):
        service.save(item.id, "malware.exe", b"x", "Outro", "", "Pessoa")


def test_meeting_persists_decisions_and_actions(session):
    item = initiative()
    session.add(item)
    session.flush()
    meeting = MeetingService(session).create(
        item.id,
        "Revisão",
        date.today(),
        "Ana",
        "Ata válida",
        summary(),
        ["Aprovar piloto"],
        [{"description": "Preparar indicador", "owner": "Ana", "deadline": date.today()}],
    )
    session.flush()
    assert meeting.id
    assert session.query(MeetingDecision).count() == 1
    assert session.query(ActionItem).count() == 1


def test_meeting_rejects_incomplete_action(session):
    item = initiative()
    session.add(item)
    session.flush()
    with pytest.raises(ValidationError):
        MeetingService(session).create(
            item.id,
            "Revisão",
            date.today(),
            "",
            "Ata",
            summary(),
            [],
            [{"description": "Ação", "owner": ""}],
        )
