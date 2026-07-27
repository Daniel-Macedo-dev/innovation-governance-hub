from datetime import date
from decimal import Decimal
from io import BytesIO

import pandas as pd
import pytest
from sqlalchemy import func, select

from innovation_governance_hub.excel.importers import (
    error_report,
    persist_preview,
    preview_expenses,
    preview_initiatives,
)
from innovation_governance_hub.excel.templates import EXPENSE_COLUMNS, INITIATIVE_COLUMNS
from innovation_governance_hub.persistence.models import Expense, Initiative


def xlsx(columns: list[str], row: dict[str, object]) -> bytes:
    output = BytesIO()
    pd.DataFrame([row], columns=columns).to_excel(output, index=False)
    return output.getvalue()


def valid_initiative() -> dict[str, object]:
    return {
        "Código": "INI-900",
        "Nome": "Importada",
        "Descrição do problema": "Problema válido",
        "Solução proposta": "Solução",
        "Área solicitante": "Operações",
        "Responsável": "Pessoa Demo",
        "Prioridade": "Alta",
        "Impacto esperado": "Alto",
        "Descrição do impacto": "Impacto fictício",
        "Complexidade": "Média",
        "Data de criação": date(2026, 7, 1),
        "Prazo": date(2026, 12, 1),
        "Status": "Ativa",
        "Estágio atual": "Ideia",
        "Custo planejado": "R$ 10.500,50",
        "Benefício esperado": 20000,
        "Observações": "Dados fictícios",
    }


def test_initiative_import_valid_and_persisted(session):
    preview = preview_initiatives(xlsx(INITIATIVE_COLUMNS, valid_initiative()))
    assert preview.valid
    assert preview.rows[0]["planned_cost"] == Decimal("10500.50")
    outcome = persist_preview(session, preview)
    assert (outcome.created, outcome.updated) == (1, 0)
    assert session.scalar(select(Initiative).where(Initiative.code == "INI-900")) is not None
    with pytest.raises(ValueError, match="já foi importado"):
        persist_preview(session, preview)


def test_initiative_import_reports_missing_column_and_existing_code():
    missing = preview_initiatives(xlsx(INITIATIVE_COLUMNS[:-1], valid_initiative()))
    assert not missing.valid
    duplicate = preview_initiatives(xlsx(INITIATIVE_COLUMNS, valid_initiative()), {"INI-900": 1})
    assert any("Ative o modo de atualização" in issue.message for issue in duplicate.issues)
    assert len(error_report(duplicate)) > 100


def test_initiative_update_mode_marks_row_and_requires_opt_in():
    updatable = preview_initiatives(
        xlsx(INITIATIVE_COLUMNS, valid_initiative()), {"INI-900": 7}, allow_updates=True
    )
    assert updatable.valid
    assert updatable.actions == ["Atualizar"]
    assert updatable.targets == [7]
    assert (updatable.create_count, updatable.update_count) == (0, 1)


def test_expense_import_valid_and_invalid_initiative(session):
    item = Initiative(
        code="INI-901",
        name="Base",
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
        planned_cost=Decimal("100"),
        expected_benefit=Decimal("200"),
        notes="",
    )
    session.add(item)
    session.flush()
    row = dict(
        zip(
            EXPENSE_COLUMNS,
            [
                date(2026, 7, 1),
                "INI-901",
                "Consultoria",
                "Serviço",
                "Fornecedor",
                "",
                "Pontual",
                "Realizado",
                50,
            ],
            strict=True,
        )
    )
    preview = preview_expenses(xlsx(EXPENSE_COLUMNS, row), {item.code: item.id})
    assert preview.valid
    persist_preview(session, preview)
    assert session.scalar(select(func.count()).select_from(Expense)) == 1
    row["Código da iniciativa"] = "INI-404"
    invalid = preview_expenses(xlsx(EXPENSE_COLUMNS, row), {item.code: item.id})
    assert not invalid.valid


def test_import_rejects_invalid_enum_date_and_money():
    row = valid_initiative()
    row.update({"Prioridade": "Urgentíssima", "Data de criação": "ontem", "Custo planejado": "abc"})
    preview = preview_initiatives(xlsx(INITIATIVE_COLUMNS, row))
    assert {issue.column for issue in preview.issues} >= {
        "Prioridade",
        "Data de criação",
        "Custo planejado",
    }
