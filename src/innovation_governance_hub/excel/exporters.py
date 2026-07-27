from io import BytesIO

import pandas as pd
from openpyxl.styles import Font, PatternFill
from sqlalchemy import select
from sqlalchemy.orm import Session

from innovation_governance_hub.persistence.models import ActionItem, AIUseCase, Expense, Initiative
from innovation_governance_hub.services.budget_service import BudgetService


def executive_workbook(session: Session) -> bytes:
    output = BytesIO()
    initiatives = session.scalars(select(Initiative)).all()
    ai = session.scalars(select(AIUseCase)).all()
    expenses = session.scalars(select(Expense)).all()
    actions = session.scalars(select(ActionItem)).all()
    summary = pd.DataFrame(
        [
            {"Indicador": "Iniciativas", "Valor": len(initiatives)},
            {"Indicador": "Casos de IA", "Valor": len(ai)},
            {"Indicador": "Aviso", "Valor": "Dados totalmente fictícios"},
        ]
    )
    frames = {
        "Resumo executivo": summary,
        "Iniciativas": pd.DataFrame(
            [
                {
                    "Código": i.code,
                    "Nome": i.name,
                    "Status": i.status,
                    "Estágio": i.current_stage,
                    "Planejado": i.planned_cost,
                    "Realizado": BudgetService(session).initiative_actual(i.id),
                }
                for i in initiatives
            ]
        ),
        "Governança de IA": pd.DataFrame(
            [
                {
                    "Código": x.code,
                    "Nome": x.name,
                    "Risco": x.risk_level,
                    "Status": x.evaluation_status,
                }
                for x in ai
            ]
        ),
        "Custos": pd.DataFrame(
            [
                {
                    "Data": x.competence_date,
                    "Categoria": x.category,
                    "Descrição": x.description,
                    "Status": x.financial_status,
                    "Valor": x.amount,
                }
                for x in expenses
            ]
        ),
        "Pendências": pd.DataFrame(
            [
                {
                    "Descrição": x.description,
                    "Responsável": x.owner,
                    "Prazo": x.deadline,
                    "Status": x.status,
                }
                for x in actions
            ]
        ),
        "Definições das métricas": pd.DataFrame(
            [
                {"Métrica": "Projeto ativo", "Definição": "Não concluído nem arquivado"},
                {"Métrica": "Custo realizado", "Definição": "Soma de despesas Realizado"},
            ]
        ),
    }
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for name, frame in frames.items():
            frame.to_excel(writer, sheet_name=name, index=False)
        for ws in writer.book.worksheets:
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            for cell in ws[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor="1F4E78")
            for column in ws.columns:
                ws.column_dimensions[column[0].column_letter].width = min(
                    45, max(12, max(len(str(c.value or "")) for c in column) + 2)
                )
    return output.getvalue()
