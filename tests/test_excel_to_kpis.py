"""Fluxo completo: planilha → validação → banco → KPIs executivos.

Usa um banco vazio isolado e o mesmo serviço de importação da interface.
"""

from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

import pandas as pd
import pytest
from sqlalchemy import func, select

from innovation_governance_hub.excel.importers import ImportPreview
from innovation_governance_hub.excel.templates import (
    AI_CASE_COLUMNS,
    EXPENSE_COLUMNS,
    INDICATOR_COLUMNS,
    INITIATIVE_COLUMNS,
)
from innovation_governance_hub.persistence.models import (
    AIGovernanceDecision,
    AIUseCase,
    Expense,
    ImportBatch,
    Initiative,
    InitiativeIndicator,
)
from innovation_governance_hub.services.executive_committee_service import (
    ExecutiveCommitteeService,
)
from innovation_governance_hub.services.import_service import ImportService
from innovation_governance_hub.services.ui_query_services import (
    AIGovernanceQueryService,
    BudgetQueryService,
    OverviewQueryService,
)


def xlsx(columns: list[str], rows: list[dict[str, object]]) -> bytes:
    output = BytesIO()
    pd.DataFrame(rows, columns=columns).to_excel(output, index=False)
    return output.getvalue()


def initiative_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "Código": "INI-800",
        "Nome": "Iniciativa importada",
        "Descrição do problema": "Processo manual fictício",
        "Solução proposta": "Automação demonstrativa",
        "Área solicitante": "Operações",
        "Responsável": "Pessoa Import",
        "Prioridade": "Alta",
        "Impacto esperado": "Alto",
        "Descrição do impacto": "Fictício",
        "Complexidade": "Média",
        "Data de criação": date.today() - timedelta(days=30),
        "Prazo": date.today() + timedelta(days=60),
        "Status": "Ativa",
        "Estágio atual": "Descoberta",
        "Custo planejado": 50000,
        "Benefício esperado": 90000,
        "Observações": "Fictício",
    }
    row.update(overrides)
    return row


def ai_case_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "Código": "IA-800",
        "Nome": "Caso importado",
        "Área responsável": "Operações",
        "Objetivo": "Apoiar análise",
        "Ferramenta avaliada": "Assistente fictício",
        "Provedor ou modelo": "Provedor avaliado",
        "Descrição dos dados": "Dados sintéticos",
        "Usa dados pessoais": "Não",
        "Nível de risco": "Alto",
        "Mitigações": "Plano em elaboração",
        "Impacto esperado": "Ganho potencial",
        "Status da avaliação": "Em avaliação",
        "Responsável": "Responsável Import",
        "Próxima revisão": date.today() + timedelta(days=30),
        "Política aceita": "Não",
        "Aprovação da governança": "Não",
        "Usuários estimados": 200,
        "Usuários ativos": 150,
        "Observações": "Fictício",
    }
    row.update(overrides)
    return row


def indicator_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "Código da iniciativa": "INI-800",
        "Nome do indicador": "Tempo de ciclo",
        "Descrição": "Indicador importado",
        "Unidade": "Dias",
        "Baseline": 20,
        "Meta": 8,
        "Valor atual": 15,
        "Direção": "Reduzir",
        "Responsável": "Pessoa Import",
        "Data de medição": date.today(),
        "Observações": "Fictício",
    }
    row.update(overrides)
    return row


def expense_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "Data de competência": date.today().replace(day=10),
        "Código da iniciativa": "INI-800",
        "Categoria": "Consultoria",
        "Descrição": "Despesa importada",
        "Fornecedor": "Fornecedor fictício",
        "Ferramenta": "",
        "Tipo de custo": "Pontual",
        "Status financeiro": "Realizado",
        "Valor": 12000,
    }
    row.update(overrides)
    return row


def test_full_spreadsheet_flow_updates_kpis(session):
    imports = ImportService(session)
    before = imports.impact_snapshot()
    assert before["iniciativas_ativas"] == 0

    overdue = initiative_row(
        **{
            "Código": "INI-801",
            "Nome": "Iniciativa atrasada",
            "Prazo": date.today() - timedelta(days=5),
        }
    )
    preview = imports.preview("initiatives", xlsx(INITIATIVE_COLUMNS, [initiative_row(), overdue]))
    assert preview.valid, preview.issues
    outcome = imports.persist(preview, "Teste", "iniciativas.xlsx")
    assert (outcome.created, outcome.updated) == (2, 0)

    expense_preview = imports.preview("expenses", xlsx(EXPENSE_COLUMNS, [expense_row()]))
    assert expense_preview.valid, expense_preview.issues
    imports.persist(expense_preview, "Teste", "custos.xlsx")

    ai_preview = imports.preview("ai_cases", xlsx(AI_CASE_COLUMNS, [ai_case_row()]))
    assert ai_preview.valid, ai_preview.issues
    imports.persist(ai_preview, "Teste", "casos_ia.xlsx")

    indicator_preview = imports.preview("indicators", xlsx(INDICATOR_COLUMNS, [indicator_row()]))
    assert indicator_preview.valid, indicator_preview.issues
    imports.persist(indicator_preview, "Teste", "indicadores.xlsx")
    session.flush()

    after = imports.impact_snapshot()
    assert after["iniciativas_ativas"] == before["iniciativas_ativas"] + 2
    assert after["custo_realizado_ano"] == before["custo_realizado_ano"] + Decimal("12000")
    assert after["casos_ia"] == before["casos_ia"] + 1
    assert after["ia_risco_sem_aprovacao"] == before["ia_risco_sem_aprovacao"] + 1
    assert after["indicadores"] == before["indicadores"] + 1

    overview = OverviewQueryService(session).load()
    assert overview["active"] == 2
    assert overview["overdue"] == 1
    assert overview["budget"]["actual"] == Decimal("12000")

    budget = BudgetQueryService(session).load(date.today().year)
    assert budget["projection"]["actual"] == Decimal("12000")
    assert any(item["category"] == "Consultoria" for item in budget["categories"])

    ai_rows = AIGovernanceQueryService(session).list()
    assert len(ai_rows) == 1
    assert ai_rows[0]["adoption"] == 75.0
    assert ai_rows[0]["governance_approved"] is False

    brief = ExecutiveCommitteeService(session).brief()
    assert brief.active_initiatives == 2
    assert any(item.kind == "Governança de IA" for item in brief.decisions)
    assert any(
        item.kind == "Iniciativa" and "Prazo vencido" in item.reason for item in brief.decisions
    )
    indicator_metric = {metric.label: metric.value for metric in brief.indicators}
    assert indicator_metric["Iniciativas com indicadores"] == "1"

    history = imports.history()
    assert len(history) == 4
    assert {item["original_filename"] for item in history} == {
        "iniciativas.xlsx",
        "custos.xlsx",
        "casos_ia.xlsx",
        "indicadores.xlsx",
    }


def test_update_mode_changes_fields_but_preserves_key_and_stage(session):
    imports = ImportService(session)
    first = imports.preview("initiatives", xlsx(INITIATIVE_COLUMNS, [initiative_row()]))
    imports.persist(first, "Teste", "v1.xlsx")
    changed = initiative_row(
        **{
            "Nome": "Iniciativa importada v2",
            "Custo planejado": 75000,
            "Estágio atual": "Piloto",
            "Observações": "Atualizada",
        }
    )
    blocked = imports.preview("initiatives", xlsx(INITIATIVE_COLUMNS, [changed]))
    assert not blocked.valid
    assert any("Ative o modo de atualização" in issue.message for issue in blocked.issues)

    update_preview = imports.preview(
        "initiatives", xlsx(INITIATIVE_COLUMNS, [changed]), allow_updates=True
    )
    assert update_preview.valid
    assert update_preview.update_count == 1
    outcome = imports.persist(update_preview, "Teste", "v2.xlsx")
    assert (outcome.created, outcome.updated) == (0, 1)
    item = session.scalar(select(Initiative).where(Initiative.code == "INI-800"))
    assert item is not None
    assert item.name == "Iniciativa importada v2"
    assert item.planned_cost == Decimal("75000")
    assert item.current_stage == "Descoberta", "estágio só avança pelos gates"


def test_ai_case_import_records_decision_history_and_update(session):
    imports = ImportService(session)
    preview = imports.preview("ai_cases", xlsx(AI_CASE_COLUMNS, [ai_case_row()]))
    imports.persist(preview, "Teste", "ia_v1.xlsx")
    assert session.scalar(select(func.count()).select_from(AIGovernanceDecision)) == 1
    update = ai_case_row(**{"Usuários ativos": 180, "Mitigações": "Plano aprovado pela área"})
    update_preview = imports.preview(
        "ai_cases", xlsx(AI_CASE_COLUMNS, [update]), allow_updates=True
    )
    assert update_preview.valid, update_preview.issues
    outcome = imports.persist(update_preview, "Teste", "ia_v2.xlsx")
    assert outcome.updated == 1
    case = session.scalar(select(AIUseCase).where(AIUseCase.code == "IA-800"))
    assert case is not None and case.active_users == 180


@pytest.mark.parametrize(
    ("columns", "rows", "expected_column"),
    [
        (INITIATIVE_COLUMNS[:-1], [initiative_row()], "Observações"),
        (
            INITIATIVE_COLUMNS,
            [initiative_row(), initiative_row()],
            "Código",
        ),
        (INITIATIVE_COLUMNS, [initiative_row(**{"Prioridade": "Urgente"})], "Prioridade"),
        (
            INITIATIVE_COLUMNS,
            [initiative_row(**{"Data de criação": "ontem"})],
            "Data de criação",
        ),
        (
            INITIATIVE_COLUMNS,
            [initiative_row(**{"Custo planejado": "abc"})],
            "Custo planejado",
        ),
    ],
)
def test_invalid_initiative_files_are_rejected(session, columns, rows, expected_column):
    preview = ImportService(session).preview("initiatives", xlsx(columns, rows))
    assert not preview.valid
    assert any(issue.column == expected_column for issue in preview.issues)


def test_invalid_ai_and_indicator_rows_are_rejected(session):
    imports = ImportService(session)
    bad_users = imports.preview(
        "ai_cases",
        xlsx(AI_CASE_COLUMNS, [ai_case_row(**{"Usuários ativos": 500})]),
    )
    assert any("não podem superar" in issue.message for issue in bad_users.issues)
    bad_risk = imports.preview(
        "ai_cases", xlsx(AI_CASE_COLUMNS, [ai_case_row(**{"Nível de risco": "Extremo"})])
    )
    assert any(issue.column == "Nível de risco" for issue in bad_risk.issues)
    rejected_status = imports.preview(
        "ai_cases",
        xlsx(AI_CASE_COLUMNS, [ai_case_row(**{"Status da avaliação": "Rejeitado"})]),
    )
    assert any(issue.column == "Status da avaliação" for issue in rejected_status.issues)
    orphan_indicator = imports.preview("indicators", xlsx(INDICATOR_COLUMNS, [indicator_row()]))
    assert any(issue.column == "Código da iniciativa" for issue in orphan_indicator.issues)


def test_invalid_file_persists_nothing_and_duplicates_are_blocked(session):
    imports = ImportService(session)
    mixed = xlsx(
        EXPENSE_COLUMNS,
        [expense_row(**{"Código da iniciativa": "INI-404"})],
    )
    preview = imports.preview("expenses", mixed)
    assert not preview.valid
    with pytest.raises(ValueError, match="erros"):
        imports.persist(preview, "Teste", "invalido.xlsx")
    assert session.scalar(select(func.count()).select_from(Expense)) == 0
    assert session.scalar(select(func.count()).select_from(ImportBatch)) == 0

    valid = imports.preview("initiatives", xlsx(INITIATIVE_COLUMNS, [initiative_row()]))
    imports.persist(valid, "Teste", "ok.xlsx")
    expense_file = xlsx(EXPENSE_COLUMNS, [expense_row()])
    imports.persist(imports.preview("expenses", expense_file), "Teste", "custos.xlsx")
    replay = imports.preview("expenses", expense_file)
    assert replay.valid
    assert imports.already_imported(replay.fingerprint)
    with pytest.raises(ValueError, match="já foi importado"):
        imports.persist(replay, "Teste", "custos.xlsx")


def test_persist_is_atomic_when_database_rejects_rows(session):
    """Se algo falhar dentro da transação, nada permanece salvo."""
    imports = ImportService(session)
    duplicated_codes = ImportPreview(
        kind="initiatives",
        rows=[
            {
                "code": "INI-900",
                "name": "Primeira",
                "problem_description": "Problema",
                "proposed_solution": "",
                "requesting_area": "Área",
                "owner": "Pessoa",
                "priority": "Média",
                "expected_impact_level": "Médio",
                "expected_impact_description": "",
                "complexity": "Média",
                "created_date": date.today(),
                "deadline": None,
                "status": "Ativa",
                "current_stage": "Ideia",
                "planned_cost": Decimal("10"),
                "expected_benefit": Decimal("0"),
                "notes": "",
            }
        ]
        * 2,
        issues=[],
        fingerprint="f" * 64,
        actions=["Criar", "Criar"],
        targets=[None, None],
    )
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        imports.persist(duplicated_codes, "Teste", "corrompido.xlsx")
    assert session.scalar(select(func.count()).select_from(Initiative)) == 0
    assert session.scalar(select(func.count()).select_from(ImportBatch)) == 0
    assert session.scalar(select(func.count()).select_from(InitiativeIndicator)) == 0
