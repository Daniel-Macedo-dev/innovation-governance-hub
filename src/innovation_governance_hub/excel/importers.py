from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import BytesIO

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from innovation_governance_hub.domain.enums import FinancialStatus, InitiativeStatus, Stage
from innovation_governance_hub.persistence.models import Expense, ImportBatch, Initiative
from innovation_governance_hub.services.audit_service import AuditService

from .templates import EXPENSE_COLUMNS, INITIATIVE_COLUMNS

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

    @property
    def valid(self) -> bool:
        return not self.issues


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


def _enum(
    value: object, allowed: set[str], row: int, column: str, issues: list[ImportIssue]
) -> str:
    text = _text(value)
    if text not in allowed:
        issues.append(
            ImportIssue(row, column, f"Valor inválido. Permitidos: {', '.join(sorted(allowed))}.")
        )
    return text


def preview_initiatives(source: bytes, existing_codes: set[str] | None = None) -> ImportPreview:
    frame = _read(source)
    issues = _missing_columns(frame, INITIATIVE_COLUMNS)
    if issues:
        return ImportPreview("initiatives", [], issues, sha256(source).hexdigest())
    rows: list[dict[str, object]] = []
    seen = set(existing_codes or set())
    for offset, record in frame.iterrows():
        row_number = int(offset) + 2
        code = _text(record["Código"])
        if code and code in seen:
            issues.append(ImportIssue(row_number, "Código", "Código duplicado."))
        if code:
            seen.add(code)
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
    return ImportPreview("initiatives", rows, issues, sha256(source).hexdigest())


def preview_expenses(source: bytes, initiatives: dict[str, int]) -> ImportPreview:
    frame = _read(source)
    issues = _missing_columns(frame, EXPENSE_COLUMNS)
    if issues:
        return ImportPreview("expenses", [], issues, sha256(source).hexdigest())
    rows: list[dict[str, object]] = []
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
    return ImportPreview("expenses", rows, issues, sha256(source).hexdigest())


def persist_preview(session: Session, preview: ImportPreview, actor: str = "Sistema") -> int:
    if not preview.valid:
        raise ValueError("A importação possui erros e não pode ser persistida.")
    if preview.fingerprint and session.scalar(
        select(ImportBatch.id).where(ImportBatch.fingerprint == preview.fingerprint)
    ):
        raise ValueError("Este arquivo já foi importado.")
    with session.begin_nested():
        if preview.kind == "initiatives":
            highest = max(
                (
                    int(code.split("-")[1])
                    for code in session.scalars(select(Initiative.code)).all()
                ),
                default=0,
            )
            for source_row in preview.rows:
                row = dict(source_row)
                if not row["code"]:
                    highest += 1
                    row["code"] = f"INI-{highest:03d}"
                row["last_activity_at"] = datetime.now()
                session.add(Initiative(**row))
        elif preview.kind == "expenses":
            for row in preview.rows:
                session.add(Expense(**dict(row)))
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
                )
            )
        AuditService(session).record(
            event_type="excel.imported",
            entity_type="Importacao",
            entity_id=None,
            entity_code=preview.fingerprint[:12],
            action="importação",
            actor=actor,
            summary=f"{len(preview.rows)} registros importados de {preview.kind}.",
            metadata={"kind": preview.kind, "row_count": len(preview.rows)},
        )
    return len(preview.rows)


def error_report(preview: ImportPreview) -> bytes:
    output = BytesIO()
    pd.DataFrame(
        [{"Linha": x.row, "Coluna": x.column, "Erro": x.message} for x in preview.issues]
    ).to_excel(output, index=False, sheet_name="Erros")
    return output.getvalue()
