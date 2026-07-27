from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from innovation_governance_hub.domain.clock import business_date
from innovation_governance_hub.domain.enums import FinancialStatus
from innovation_governance_hub.exceptions import ValidationError
from innovation_governance_hub.persistence.models import AnnualBudget, Expense, Initiative
from innovation_governance_hub.services.audit_service import AuditService


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
            "variance": planned - actual_dec,
            "variance_percent": ((planned - actual_dec) / planned * 100)
            if planned
            else Decimal("0"),
            "committed": actual_dec + forecast_dec,
            "balance_after_commitments": planned - actual_dec - forecast_dec,
        }

    def projection(self, year: int, as_of: date | None = None) -> dict[str, Decimal | int]:
        reference = as_of or business_date()
        totals = self.totals(year)
        actual_rows = list(
            self.session.execute(
                select(Expense.competence_date, Expense.amount).where(
                    func.extract("year", Expense.competence_date) == year,
                    Expense.financial_status == FinancialStatus.ACTUAL,
                    Expense.competence_date <= reference,
                )
            )
        )
        monthly = {month: Decimal("0") for month in range(1, 13)}
        for competence, amount in actual_rows:
            monthly[competence.month] += Decimal(amount)
        elapsed = min(
            12,
            max(
                0,
                reference.month if reference.year == year else (12 if reference.year > year else 0),
            ),
        )
        active_months = [monthly[month] for month in range(1, elapsed + 1)]
        average = sum(active_months, Decimal("0")) / elapsed if elapsed else Decimal("0")
        recent_months = active_months[-3:]
        recent_average = (
            sum(recent_months, Decimal("0")) / len(recent_months) if recent_months else Decimal("0")
        )
        future_months = max(0, 12 - elapsed)
        projected = (
            Decimal(totals["actual"]) + Decimal(totals["forecast"]) + recent_average * future_months
        )
        planned = Decimal(totals["planned"])
        return {
            **totals,
            "elapsed_months": elapsed,
            "future_months": future_months,
            "monthly_average": average,
            "recent_three_month_average": recent_average,
            "year_end_projection": projected,
            "projected_balance": planned - projected,
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

    def set_annual_budget(
        self, year: int, planned_amount: Decimal, notes: str, actor: str
    ) -> AnnualBudget:
        if planned_amount <= 0:
            raise ValidationError("O orçamento anual deve ser maior que zero.")
        budget = self.session.scalar(select(AnnualBudget).where(AnnualBudget.year == year))
        created = budget is None
        previous = budget.planned_amount if budget else None
        if budget is None:
            budget = AnnualBudget(year=year, planned_amount=planned_amount, notes=notes.strip())
            self.session.add(budget)
        else:
            budget.planned_amount = planned_amount
            budget.notes = notes.strip()
        self.session.flush()
        AuditService(self.session).record(
            event_type="budget.defined" if created else "budget.updated",
            entity_type="OrcamentoAnual",
            entity_id=budget.id,
            action="definição" if created else "edição",
            actor=actor,
            summary=f"Orçamento anual de {year} definido.",
            changes={"planned_amount": {"before": previous, "after": planned_amount}},
        )
        return budget

    def category_totals(self, year: int) -> list[dict[str, object]]:
        rows = self.session.execute(
            select(
                Expense.category,
                Expense.financial_status,
                func.coalesce(func.sum(Expense.amount), 0),
            )
            .where(func.extract("year", Expense.competence_date) == year)
            .group_by(Expense.category, Expense.financial_status)
        ).all()
        by_category: dict[str, dict[str, Decimal]] = {}
        for category, status, amount in rows:
            entry = by_category.setdefault(
                category, {"Realizado": Decimal("0"), "Previsto": Decimal("0")}
            )
            entry[str(status)] = Decimal(amount or 0)
        return [
            {
                "category": category,
                "actual": values["Realizado"],
                "forecast": values["Previsto"],
                "total": values["Realizado"] + values["Previsto"],
            }
            for category, values in sorted(
                by_category.items(), key=lambda pair: pair[1]["Realizado"], reverse=True
            )
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
            if key == "actor":
                continue
            setattr(expense, key, value)
        expense.amount = amount
        self.session.add(expense)
        self.session.flush()
        AuditService(self.session).record(
            event_type="expense.created" if expense_id is None else "expense.updated",
            entity_type="Despesa",
            entity_id=expense.id,
            action="criação" if expense_id is None else "edição",
            actor=str(data.get("actor", "Sistema")),
            summary=f"Despesa {expense.description} salva.",
            metadata={"amount": amount, "initiative_id": expense.initiative_id},
        )
        return expense

    def delete_expense(self, expense_id: int) -> None:
        expense = self.session.get(Expense, expense_id)
        if not expense:
            raise ValidationError("Despesa não encontrada.")
        self.session.delete(expense)
