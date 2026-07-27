from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from innovation_governance_hub.domain.enums import FinancialStatus
from innovation_governance_hub.exceptions import ValidationError
from innovation_governance_hub.persistence.models import AnnualBudget, Expense, Initiative


class BudgetService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def totals(self, year: int) -> dict[str, Decimal]:
        budget = self.session.scalar(select(AnnualBudget).where(AnnualBudget.year == year))
        actual = self.session.scalar(
            select(func.coalesce(func.sum(Expense.amount), 0)).where(
                func.extract("year", Expense.competence_date) == year,
                Expense.financial_status == FinancialStatus.ACTUAL,
            )
        )
        forecast = self.session.scalar(
            select(func.coalesce(func.sum(Expense.amount), 0)).where(
                func.extract("year", Expense.competence_date) == year,
                Expense.financial_status == FinancialStatus.FORECAST,
            )
        )
        planned = budget.planned_amount if budget else Decimal("0")
        actual_dec, forecast_dec = Decimal(actual or 0), Decimal(forecast or 0)
        return {
            "planned": planned,
            "actual": actual_dec,
            "forecast": forecast_dec,
            "balance": planned - actual_dec,
            "consumed_percent": (actual_dec / planned * 100) if planned else Decimal("0"),
        }

    def initiative_actual(self, initiative_id: int) -> Decimal:
        value = self.session.scalar(
            select(func.coalesce(func.sum(Expense.amount), 0)).where(
                Expense.initiative_id == initiative_id,
                Expense.financial_status == FinancialStatus.ACTUAL,
            )
        )
        return Decimal(value or 0)

    def over_budget(self) -> list[Initiative]:
        return [
            i
            for i in self.session.scalars(select(Initiative)).all()
            if self.initiative_actual(i.id) > i.planned_cost
        ]

    def save_expense(self, data: dict[str, object], expense_id: int | None = None) -> Expense:
        amount = Decimal(str(data.get("amount", 0)))
        if amount <= 0:
            raise ValidationError("O valor da despesa deve ser maior que zero.")
        initiative_id = data.get("initiative_id")
        if initiative_id is not None and not self.session.get(Initiative, int(str(initiative_id))):
            raise ValidationError("Iniciativa vinculada não encontrada.")
        expense = self.session.get(Expense, expense_id) if expense_id else Expense()
        if not expense:
            raise ValidationError("Despesa não encontrada.")
        for key, value in data.items():
            setattr(expense, key, value)
        expense.amount = amount
        self.session.add(expense)
        self.session.flush()
        return expense

    def delete_expense(self, expense_id: int) -> None:
        expense = self.session.get(Expense, expense_id)
        if not expense:
            raise ValidationError("Despesa não encontrada.")
        self.session.delete(expense)
