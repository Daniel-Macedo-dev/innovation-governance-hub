from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

INITIATIVE_COLUMNS = [
    "Código",
    "Nome",
    "Descrição do problema",
    "Solução proposta",
    "Área solicitante",
    "Responsável",
    "Prioridade",
    "Impacto esperado",
    "Descrição do impacto",
    "Complexidade",
    "Data de criação",
    "Prazo",
    "Status",
    "Estágio atual",
    "Custo planejado",
    "Benefício esperado",
    "Observações",
]
EXPENSE_COLUMNS = [
    "Data de competência",
    "Código da iniciativa",
    "Categoria",
    "Descrição",
    "Fornecedor",
    "Ferramenta",
    "Tipo de custo",
    "Status financeiro",
    "Valor",
]


def create_template(path: Path, columns: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "Importação"
    ws.append(columns)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{ws.cell(1, len(columns)).coordinate}"
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F4E78")
    for idx, column in enumerate(columns, 1):
        ws.column_dimensions[ws.cell(1, idx).column_letter].width = max(14, len(column) + 2)
    wb.save(path)
    return path
