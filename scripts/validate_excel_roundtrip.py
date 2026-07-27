from datetime import date
from io import BytesIO
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from innovation_governance_hub.database import Base
from innovation_governance_hub.excel.exporters import executive_workbook
from innovation_governance_hub.excel.importers import (
    persist_preview,
    preview_expenses,
    preview_initiatives,
)
from innovation_governance_hub.excel.templates import (
    EXPENSE_COLUMNS,
    INITIATIVE_COLUMNS,
    create_template,
)
from innovation_governance_hub.persistence.models import Expense, Initiative


def workbook_bytes(columns: list[str], row: dict[str, object]) -> bytes:
    output = BytesIO()
    pd.DataFrame([row], columns=columns).to_excel(output, index=False)
    return output.getvalue()


def main() -> None:
    create_template(Path("templates/modelo_iniciativas.xlsx"), INITIATIVE_COLUMNS)
    create_template(Path("templates/modelo_custos.xlsx"), EXPENSE_COLUMNS)
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session, session.begin():
        initiative_row = dict(
            zip(
                INITIATIVE_COLUMNS,
                [
                    "INI-RT-001",
                    "Iniciativa roundtrip",
                    "Problema fictício",
                    "Solução fictícia",
                    "Operações",
                    "Pessoa Demo",
                    "Alta",
                    "Alto",
                    "Impacto fictício",
                    "Média",
                    date(2026, 7, 1),
                    date(2026, 12, 1),
                    "Ativa",
                    "Ideia",
                    10000,
                    20000,
                    "Validação isolada",
                ],
                strict=True,
            )
        )
        initiatives = preview_initiatives(workbook_bytes(INITIATIVE_COLUMNS, initiative_row))
        assert initiatives.valid
        persist_preview(session, initiatives)
        item = session.scalar(select(Initiative).where(Initiative.code == "INI-RT-001"))
        assert item is not None
        expense_row = dict(
            zip(
                EXPENSE_COLUMNS,
                [
                    date(2026, 7, 1),
                    item.code,
                    "Consultoria",
                    "Despesa roundtrip",
                    "Fornecedor fictício",
                    "",
                    "Pontual",
                    "Realizado",
                    500,
                ],
                strict=True,
            )
        )
        expenses = preview_expenses(
            workbook_bytes(EXPENSE_COLUMNS, expense_row), {item.code: item.id}
        )
        assert expenses.valid
        persist_preview(session, expenses)
        assert session.scalar(select(func.count()).select_from(Expense)) == 1
        data = executive_workbook(session)
    workbook = load_workbook(BytesIO(data))
    required = {
        "Resumo executivo",
        "Iniciativas",
        "Governança de IA",
        "Custos",
        "Pendências",
        "Definições das métricas",
    }
    if not required <= set(workbook.sheetnames):
        raise RuntimeError("Abas obrigatórias ausentes")
    Path("templates/relatorio_executivo_validacao.xlsx").write_bytes(data)
    print("Roundtrip Excel validado.")


if __name__ == "__main__":
    main()
