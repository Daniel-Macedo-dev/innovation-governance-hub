"""Orquestra prévia, persistência, histórico e impacto das importações Excel.

Interface e API compartilham este serviço; não há parser duplicado.
"""

from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from innovation_governance_hub.domain.clock import business_date
from innovation_governance_hub.domain.enums import AIStatus, FinancialStatus, RiskLevel
from innovation_governance_hub.excel.importers import (
    ImportOutcome,
    ImportPreview,
    persist_preview,
    preview_ai_cases,
    preview_expenses,
    preview_indicators,
    preview_initiatives,
)
from innovation_governance_hub.persistence.models import (
    AIUseCase,
    Expense,
    ImportBatch,
    Initiative,
    InitiativeIndicator,
)

IMPORT_KIND_LABELS = {
    "initiatives": "Iniciativas",
    "expenses": "Despesas e custos",
    "ai_cases": "Casos de governança de IA",
    "indicators": "Indicadores de iniciativas",
}
UPDATABLE_KINDS = {"initiatives", "ai_cases", "indicators"}


class ImportService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _initiative_codes(self) -> dict[str, int]:
        return {
            code: identifier
            for code, identifier in self.session.execute(
                select(Initiative.code, Initiative.id)
            ).all()
        }

    def preview(self, kind: str, source: bytes, allow_updates: bool = False) -> ImportPreview:
        if kind == "initiatives":
            return preview_initiatives(source, self._initiative_codes(), allow_updates)
        if kind == "expenses":
            return preview_expenses(source, self._initiative_codes())
        if kind == "ai_cases":
            existing = {
                code: identifier
                for code, identifier in self.session.execute(
                    select(AIUseCase.code, AIUseCase.id)
                ).all()
            }
            return preview_ai_cases(source, existing, allow_updates)
        if kind == "indicators":
            initiatives = self._initiative_codes()
            by_id = {identifier: code for code, identifier in initiatives.items()}
            existing = {}
            for indicator in self.session.scalars(select(InitiativeIndicator)).all():
                code = by_id.get(indicator.initiative_id)
                if code:
                    existing[(code, indicator.name)] = indicator.id
            return preview_indicators(source, initiatives, existing, allow_updates)
        raise ValueError("Tipo de importação desconhecido.")

    def already_imported(self, fingerprint: str) -> bool:
        return bool(
            self.session.scalar(
                select(ImportBatch.id).where(ImportBatch.fingerprint == fingerprint)
            )
        )

    def persist(
        self, preview: ImportPreview, actor: str, original_filename: str = ""
    ) -> ImportOutcome:
        return persist_preview(self.session, preview, actor, original_filename)

    def history(self, limit: int = 20) -> list[dict[str, Any]]:
        batches = self.session.scalars(
            select(ImportBatch).order_by(ImportBatch.imported_at.desc()).limit(limit)
        ).all()
        return [
            {
                "imported_at": batch.imported_at,
                "kind": IMPORT_KIND_LABELS.get(batch.import_type, batch.import_type),
                "original_filename": batch.original_filename,
                "row_count": batch.row_count,
                "created_count": batch.created_count,
                "updated_count": batch.updated_count,
                "imported_by": batch.imported_by,
                "fingerprint": batch.fingerprint[:12],
            }
            for batch in batches
        ]

    def impact_snapshot(self) -> dict[str, Any]:
        """Métricas leves usadas para mostrar o efeito de uma importação nos KPIs."""
        year = business_date().year
        active = self.session.scalar(
            select(func.count())
            .select_from(Initiative)
            .where(Initiative.status.not_in(["Concluída", "Arquivada"]))
        )
        actual = self.session.scalar(
            select(func.coalesce(func.sum(Expense.amount), 0)).where(
                func.extract("year", Expense.competence_date) == year,
                Expense.financial_status == FinancialStatus.ACTUAL,
            )
        )
        pending_high_risk = self.session.scalar(
            select(func.count())
            .select_from(AIUseCase)
            .where(
                AIUseCase.risk_level.in_([RiskLevel.HIGH, RiskLevel.CRITICAL]),
                AIUseCase.evaluation_status.not_in([AIStatus.APPROVED, AIStatus.RESTRICTED]),
            )
        )
        return {
            "iniciativas_ativas": int(active or 0),
            "custo_realizado_ano": Decimal(actual or 0),
            "casos_ia": int(self.session.scalar(select(func.count()).select_from(AIUseCase)) or 0),
            "ia_risco_sem_aprovacao": int(pending_high_risk or 0),
            "indicadores": int(
                self.session.scalar(select(func.count()).select_from(InitiativeIndicator)) or 0
            ),
        }
