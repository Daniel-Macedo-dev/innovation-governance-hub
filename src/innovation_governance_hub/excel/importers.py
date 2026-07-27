"""Leitura, validação e persistência de planilhas.

As planilhas usam chaves de negócio estáveis (códigos), nunca IDs internos.
A persistência reutiliza os mesmos serviços do cadastro manual, garantindo
validações, auditoria e histórico decisório idênticos nos dois caminhos.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import BytesIO

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from innovation_governance_hub.domain.enums import (
    AIStatus,
    FinancialStatus,
    InitiativeStatus,
    RiskLevel,
    Stage,
)
from innovation_governance_hub.persistence.models import Expense, ImportBatch
from innovation_governance_hub.services.ai_governance_service import AIUseCaseService
from innovation_governance_hub.services.audit_service import AuditService
from innovation_governance_hub.services.indicator_service import IndicatorService
from innovation_governance_hub.services.initiative_service import InitiativeService

from .templates import AI_CASE_COLUMNS, EXPENSE_COLUMNS, INDICATOR_COLUMNS, INITIATIVE_COLUMNS

PRIORITIES = {"Baixa", "Média", "Alta", "Crítica"}
IMPACTS = {"Baixo", "Médio", "Alto", "Muito alto"}
COMPLEXITIES = {"Baixa", "Média", "Alta"}
CATEGORIES = {
    "Ferramentas e software",
    "Fornecedores",
    "Consultoria",
    "Infraestrutura",
    "Treinamento",
    "Outros",
}
COST_TYPES = {"Pontual", "Recorrente"}
BOOLEANS = {"Sim": True, "Não": False, "Nao": False}
INDICATOR_UNITS = {"Percentual", "Real", "Dias", "Horas", "Quantidade", "Índice"}
INDICATOR_DIRECTIONS = {"Aumentar", "Reduzir", "Manter faixa"}
# Rejeição e suspensão exigem justificativa individual e são feitas pela interface.
IMPORTABLE_AI_STATUSES = {
    str(AIStatus.DRAFT),
    str(AIStatus.EVALUATING),
    str(AIStatus.REVIEW),
    str(AIStatus.APPROVED),
}

CREATE, UPDATE = "Criar", "Atualizar"


@dataclass(frozen=True)
class ImportIssue:
    row: int
    column: str
    message: str


@dataclass
class ImportPreview:
    kind: str
    rows: list[dict[str, object]]
    issues: list[ImportIssue]
    fingerprint: str = ""
    actions: list[str] = field(default_factory=list)
    targets: list[int | None] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.issues

    @property
    def create_count(self) -> int:
        return sum(action == CREATE for action in self.actions)

    @property
    def update_count(self) -> int:
        return sum(action == UPDATE for action in self.actions)


@dataclass(frozen=True)
class ImportOutcome:
    kind: str
    created: int
    updated: int


def _read(source: bytes) -> pd.DataFrame:
    return pd.read_excel(BytesIO(source), dtype=object).dropna(how="all")


def _missing_columns(frame: pd.DataFrame, expected: list[str]) -> list[ImportIssue]:
    return [
        ImportIssue(1, name, "Coluna obrigatória ausente.")
        for name in expected
        if name not in frame.columns
    ]


def _text(value: object) -> str:
    return "" if pd.isna(value) else str(value).strip()


def _date(
    value: object, row: int, column: str, issues: list[ImportIssue], required: bool = False
) -> date | None:
    if pd.isna(value) or value == "":
        if required:
            issues.append(ImportIssue(row, column, "Data obrigatória."))
        return None
    try:
        parsed = pd.to_datetime(value, dayfirst=True, errors="raise")
        return parsed.date()
    except (ValueError, TypeError, OverflowError):
        issues.append(ImportIssue(row, column, "Data inválida; use DD/MM/AAAA."))
        return None


def _money(
    value: object, row: int, column: str, issues: list[ImportIssue], positive: bool = False
) -> Decimal:
    raw = _text(value).replace("R$", "").replace(" ", "")
    if not raw:
        return Decimal("0")
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    try:
        amount = Decimal(raw)
    except InvalidOperation:
        issues.append(ImportIssue(row, column, "Valor monetário inválido."))
        return Decimal("0")
    if positive and amount <= 0:
        issues.append(ImportIssue(row, column, "O valor deve ser maior que zero."))
    return amount


def _optional_decimal(
    value: object, row: int, column: str, issues: list[ImportIssue]
) -> Decimal | None:
    raw = _text(value).replace("R$", "").replace(" ", "")
    if not raw:
        return None
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    try:
        return Decimal(raw)
    except InvalidOperation:
        issues.append(ImportIssue(row, column, "Valor numérico inválido."))
        return None


def _int(value: object, row: int, column: str, issues: list[ImportIssue]) -> int:
    raw = _text(value)
    if not raw:
        return 0
    try:
        parsed = int(float(raw))
    except ValueError:
        issues.append(ImportIssue(row, column, "Número inteiro inválido."))
        return 0
    if parsed < 0:
        issues.append(ImportIssue(row, column, "O número não pode ser negativo."))
        return 0
    return parsed


def _bool(value: object, row: int, column: str, issues: list[ImportIssue]) -> bool:
    text = _text(value)
    if not text:
        return False
    if text not in BOOLEANS:
        issues.append(ImportIssue(row, column, "Use Sim ou Não."))
        return False
    return BOOLEANS[text]


def _enum(
    value: object, allowed: set[str], row: int, column: str, issues: list[ImportIssue]
) -> str:
    text = _text(value)
    if text not in allowed:
        issues.append(
            ImportIssue(row, column, f"Valor inválido. Permitidos: {', '.join(sorted(allowed))}.")
        )
    return text


def _resolve_action(
    code: str,
    existing: dict[str, int],
    allow_updates: bool,
    row_number: int,
    column: str,
    issues: list[ImportIssue],
) -> tuple[str, int | None]:
    if code and code in existing:
        if allow_updates:
            return UPDATE, existing[code]
        issues.append(
            ImportIssue(
                row_number,
                column,
                "Código já cadastrado. Ative o modo de atualização para alterar o registro.",
            )
        )
    return CREATE, None


def preview_initiatives(
    source: bytes, existing: dict[str, int] | None = None, allow_updates: bool = False
) -> ImportPreview:
    frame = _read(source)
    issues = _missing_columns(frame, INITIATIVE_COLUMNS)
    fingerprint = sha256(source).hexdigest()
    if issues:
        return ImportPreview("initiatives", [], issues, fingerprint)
    known = dict(existing or {})
    seen_in_file: set[str] = set()
    rows: list[dict[str, object]] = []
    actions: list[str] = []
    targets: list[int | None] = []
    for offset, record in frame.iterrows():
        row_number = int(offset) + 2
        code = _text(record["Código"])
        if code and code in seen_in_file:
            issues.append(ImportIssue(row_number, "Código", "Código duplicado no arquivo."))
        if code:
            seen_in_file.add(code)
        action, target = _resolve_action(code, known, allow_updates, row_number, "Código", issues)
        name = _text(record["Nome"])
        problem = _text(record["Descrição do problema"])
        area = _text(record["Área solicitante"])
        owner = _text(record["Responsável"])
        for column, value in [
            ("Nome", name),
            ("Descrição do problema", problem),
            ("Área solicitante", area),
            ("Responsável", owner),
        ]:
            if not value:
                issues.append(ImportIssue(row_number, column, "Campo obrigatório."))
        rows.append(
            {
                "code": code,
                "name": name,
                "problem_description": problem,
                "proposed_solution": _text(record["Solução proposta"]),
                "requesting_area": area,
                "owner": owner,
                "priority": _enum(
                    record["Prioridade"], PRIORITIES, row_number, "Prioridade", issues
                ),
                "expected_impact_level": _enum(
                    record["Impacto esperado"], IMPACTS, row_number, "Impacto esperado", issues
                ),
                "expected_impact_description": _text(record["Descrição do impacto"]),
                "complexity": _enum(
                    record["Complexidade"], COMPLEXITIES, row_number, "Complexidade", issues
                ),
                "created_date": _date(
                    record["Data de criação"], row_number, "Data de criação", issues, True
                ),
                "deadline": _date(record["Prazo"], row_number, "Prazo", issues),
                "status": _enum(
                    record["Status"],
                    {x.value for x in InitiativeStatus},
                    row_number,
                    "Status",
                    issues,
                ),
                "current_stage": _enum(
                    record["Estágio atual"],
                    {x.value for x in Stage},
                    row_number,
                    "Estágio atual",
                    issues,
                ),
                "planned_cost": _money(
                    record["Custo planejado"], row_number, "Custo planejado", issues
                ),
                "expected_benefit": _money(
                    record["Benefício esperado"], row_number, "Benefício esperado", issues
                ),
                "notes": _text(record["Observações"]),
            }
        )
        actions.append(action)
        targets.append(target)
    return ImportPreview("initiatives", rows, issues, fingerprint, actions, targets)


def preview_expenses(source: bytes, initiatives: dict[str, int]) -> ImportPreview:
    frame = _read(source)
    issues = _missing_columns(frame, EXPENSE_COLUMNS)
    fingerprint = sha256(source).hexdigest()
    if issues:
        return ImportPreview("expenses", [], issues, fingerprint)
    rows: list[dict[str, object]] = []
    actions: list[str] = []
    for offset, record in frame.iterrows():
        row_number = int(offset) + 2
        code = _text(record["Código da iniciativa"])
        if code and code not in initiatives:
            issues.append(
                ImportIssue(row_number, "Código da iniciativa", "Iniciativa inexistente.")
            )
        description = _text(record["Descrição"])
        if not description:
            issues.append(ImportIssue(row_number, "Descrição", "Campo obrigatório."))
        rows.append(
            {
                "initiative_id": initiatives.get(code),
                "competence_date": _date(
                    record["Data de competência"], row_number, "Data de competência", issues, True
                ),
                "category": _enum(record["Categoria"], CATEGORIES, row_number, "Categoria", issues),
                "description": description,
                "supplier": _text(record["Fornecedor"]),
                "tool_name": _text(record["Ferramenta"]),
                "cost_type": _enum(
                    record["Tipo de custo"], COST_TYPES, row_number, "Tipo de custo", issues
                ),
                "financial_status": _enum(
                    record["Status financeiro"],
                    {x.value for x in FinancialStatus},
                    row_number,
                    "Status financeiro",
                    issues,
                ),
                "amount": _money(record["Valor"], row_number, "Valor", issues, True),
            }
        )
        actions.append(CREATE)
    return ImportPreview("expenses", rows, issues, fingerprint, actions, [None] * len(rows))


def preview_ai_cases(
    source: bytes, existing: dict[str, int] | None = None, allow_updates: bool = False
) -> ImportPreview:
    frame = _read(source)
    issues = _missing_columns(frame, AI_CASE_COLUMNS)
    fingerprint = sha256(source).hexdigest()
    if issues:
        return ImportPreview("ai_cases", [], issues, fingerprint)
    known = dict(existing or {})
    seen_in_file: set[str] = set()
    rows: list[dict[str, object]] = []
    actions: list[str] = []
    targets: list[int | None] = []
    for offset, record in frame.iterrows():
        row_number = int(offset) + 2
        code = _text(record["Código"])
        name = _text(record["Nome"])
        if not code:
            issues.append(ImportIssue(row_number, "Código", "Campo obrigatório."))
        if not name:
            issues.append(ImportIssue(row_number, "Nome", "Campo obrigatório."))
        if code and code in seen_in_file:
            issues.append(ImportIssue(row_number, "Código", "Código duplicado no arquivo."))
        if code:
            seen_in_file.add(code)
        action, target = _resolve_action(code, known, allow_updates, row_number, "Código", issues)
        estimated = _int(record["Usuários estimados"], row_number, "Usuários estimados", issues)
        active = _int(record["Usuários ativos"], row_number, "Usuários ativos", issues)
        if active > estimated:
            issues.append(
                ImportIssue(
                    row_number,
                    "Usuários ativos",
                    "Usuários ativos não podem superar os estimados.",
                )
            )
        status = _enum(
            record["Status da avaliação"],
            IMPORTABLE_AI_STATUSES,
            row_number,
            "Status da avaliação",
            issues,
        )
        risk = _enum(
            record["Nível de risco"],
            {x.value for x in RiskLevel},
            row_number,
            "Nível de risco",
            issues,
        )
        row = {
            "code": code,
            "name": name,
            "responsible_area": _text(record["Área responsável"]),
            "objective": _text(record["Objetivo"]),
            "ai_tool": _text(record["Ferramenta avaliada"]),
            "model_or_provider": _text(record["Provedor ou modelo"]),
            "data_description": _text(record["Descrição dos dados"]),
            "uses_personal_data": _bool(
                record["Usa dados pessoais"], row_number, "Usa dados pessoais", issues
            ),
            "risk_level": risk,
            "risk_mitigation": _text(record["Mitigações"]),
            "expected_impact": _text(record["Impacto esperado"]),
            "evaluation_status": status,
            "owner": _text(record["Responsável"]),
            "next_review_date": _date(
                record["Próxima revisão"], row_number, "Próxima revisão", issues
            ),
            "policy_accepted": _bool(
                record["Política aceita"], row_number, "Política aceita", issues
            ),
            "governance_approved": _bool(
                record["Aprovação da governança"], row_number, "Aprovação da governança", issues
            ),
            "estimated_users": estimated,
            "active_users": active,
            "notes": _text(record["Observações"]),
        }
        if status == AIStatus.APPROVED:
            approval_requirements = [
                (bool(str(row["owner"]).strip()), "Responsável"),
                (bool(row["policy_accepted"]), "Política aceita"),
                (bool(row["governance_approved"]), "Aprovação da governança"),
                (row["next_review_date"] is not None, "Próxima revisão"),
                (bool(str(row["data_description"]).strip()), "Descrição dos dados"),
            ]
            for satisfied, column in approval_requirements:
                if not satisfied:
                    issues.append(
                        ImportIssue(row_number, column, "Obrigatório para status Aprovado.")
                    )
            if risk in {str(RiskLevel.HIGH), str(RiskLevel.CRITICAL)} and not (
                str(row["risk_mitigation"]).strip() and str(row["notes"]).strip()
            ):
                issues.append(
                    ImportIssue(
                        row_number,
                        "Mitigações",
                        "Alto risco aprovado exige mitigação e justificativa em Observações.",
                    )
                )
        rows.append(row)
        actions.append(action)
        targets.append(target)
    return ImportPreview("ai_cases", rows, issues, fingerprint, actions, targets)


def preview_indicators(
    source: bytes,
    initiatives: dict[str, int],
    existing: dict[tuple[str, str], int] | None = None,
    allow_updates: bool = False,
) -> ImportPreview:
    frame = _read(source)
    issues = _missing_columns(frame, INDICATOR_COLUMNS)
    fingerprint = sha256(source).hexdigest()
    if issues:
        return ImportPreview("indicators", [], issues, fingerprint)
    known = dict(existing or {})
    seen_in_file: set[tuple[str, str]] = set()
    rows: list[dict[str, object]] = []
    actions: list[str] = []
    targets: list[int | None] = []
    for offset, record in frame.iterrows():
        row_number = int(offset) + 2
        code = _text(record["Código da iniciativa"])
        name = _text(record["Nome do indicador"])
        if not code or code not in initiatives:
            issues.append(
                ImportIssue(row_number, "Código da iniciativa", "Iniciativa inexistente.")
            )
        if not name:
            issues.append(ImportIssue(row_number, "Nome do indicador", "Campo obrigatório."))
        key = (code, name)
        if name and key in seen_in_file:
            issues.append(
                ImportIssue(row_number, "Nome do indicador", "Indicador duplicado no arquivo.")
            )
        seen_in_file.add(key)
        action: str = CREATE
        target: int | None = None
        if key in known:
            if allow_updates:
                action, target = UPDATE, known[key]
            else:
                issues.append(
                    ImportIssue(
                        row_number,
                        "Nome do indicador",
                        "Indicador já cadastrado nesta iniciativa. "
                        "Ative o modo de atualização para alterar a medição.",
                    )
                )
        rows.append(
            {
                "initiative_id": initiatives.get(code),
                "name": name,
                "description": _text(record["Descrição"]),
                "unit": _enum(record["Unidade"], INDICATOR_UNITS, row_number, "Unidade", issues),
                "baseline_value": _optional_decimal(
                    record["Baseline"], row_number, "Baseline", issues
                ),
                "target_value": _optional_decimal(record["Meta"], row_number, "Meta", issues),
                "current_value": _optional_decimal(
                    record["Valor atual"], row_number, "Valor atual", issues
                ),
                "direction": _enum(
                    record["Direção"], INDICATOR_DIRECTIONS, row_number, "Direção", issues
                ),
                "owner": _text(record["Responsável"]),
                "measurement_date": _date(
                    record["Data de medição"], row_number, "Data de medição", issues
                ),
                "notes": _text(record["Observações"]),
            }
        )
        actions.append(action)
        targets.append(target)
    return ImportPreview("indicators", rows, issues, fingerprint, actions, targets)


def _persist_initiatives(session: Session, preview: ImportPreview, actor: str) -> tuple[int, int]:
    service = InitiativeService(session)
    created = updated = 0
    for row, action, target in zip(preview.rows, preview.actions, preview.targets, strict=True):
        data = {key: value for key, value in row.items() if value is not None or key == "deadline"}
        data["actor"] = actor
        if action == UPDATE and target is not None:
            # Código, estágio e data de criação não mudam por planilha:
            # estágio avança apenas pelos gates.
            for locked in ("code", "current_stage", "created_date"):
                data.pop(locked, None)
            service.update(target, data)
            updated += 1
        else:
            if not data.get("code"):
                data.pop("code", None)
            service.create(data)
            created += 1
    return created, updated


def _persist_expenses(session: Session, preview: ImportPreview) -> tuple[int, int]:
    for row in preview.rows:
        session.add(Expense(**dict(row)))
    return len(preview.rows), 0


def _persist_ai_cases(session: Session, preview: ImportPreview, actor: str) -> tuple[int, int]:
    service = AIUseCaseService(session)
    created = updated = 0
    for row, action, target in zip(preview.rows, preview.actions, preview.targets, strict=True):
        data = dict(row)
        data["actor"] = actor
        if action == UPDATE and target is not None:
            service.save(data, target)
            updated += 1
        else:
            service.save(data)
            created += 1
    return created, updated


def _persist_indicators(session: Session, preview: ImportPreview, actor: str) -> tuple[int, int]:
    service = IndicatorService(session)
    created = updated = 0
    for row, action, target in zip(preview.rows, preview.actions, preview.targets, strict=True):
        data = {key: value for key, value in row.items() if key != "initiative_id"}
        initiative_id = int(str(row["initiative_id"]))
        if action == UPDATE and target is not None:
            service.save(initiative_id, data, actor, target)
            updated += 1
        else:
            service.save(initiative_id, data, actor)
            created += 1
    return created, updated


def persist_preview(
    session: Session,
    preview: ImportPreview,
    actor: str = "Sistema",
    original_filename: str = "",
) -> ImportOutcome:
    if not preview.valid:
        raise ValueError("A importação possui erros e não pode ser persistida.")
    if preview.fingerprint and session.scalar(
        select(ImportBatch.id).where(ImportBatch.fingerprint == preview.fingerprint)
    ):
        raise ValueError("Este arquivo já foi importado.")
    with session.begin_nested():
        if preview.kind == "initiatives":
            created, updated = _persist_initiatives(session, preview, actor)
        elif preview.kind == "expenses":
            created, updated = _persist_expenses(session, preview)
        elif preview.kind == "ai_cases":
            created, updated = _persist_ai_cases(session, preview, actor)
        elif preview.kind == "indicators":
            created, updated = _persist_indicators(session, preview, actor)
        else:
            raise ValueError("Tipo de importação desconhecido.")
        session.flush()
        if preview.fingerprint:
            session.add(
                ImportBatch(
                    fingerprint=preview.fingerprint,
                    import_type=preview.kind,
                    row_count=len(preview.rows),
                    imported_by=actor,
                    original_filename=original_filename,
                    created_count=created,
                    updated_count=updated,
                )
            )
        AuditService(session).record(
            event_type="excel.imported",
            entity_type="Importacao",
            entity_id=None,
            entity_code=preview.fingerprint[:12],
            action="importação",
            actor=actor,
            summary=(
                f"Importação de {preview.kind}: {created} registros criados, {updated} atualizados."
            ),
            metadata={
                "kind": preview.kind,
                "row_count": len(preview.rows),
                "created": created,
                "updated": updated,
                "original_filename": original_filename,
            },
        )
    return ImportOutcome(preview.kind, created, updated)


def error_report(preview: ImportPreview) -> bytes:
    output = BytesIO()
    pd.DataFrame(
        [{"Linha": x.row, "Coluna": x.column, "Erro": x.message} for x in preview.issues]
    ).to_excel(output, index=False, sheet_name="Erros")
    return output.getvalue()
