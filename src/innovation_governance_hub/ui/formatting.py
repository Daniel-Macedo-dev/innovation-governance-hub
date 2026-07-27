from datetime import date, datetime
from decimal import Decimal


def brl(value: Decimal | int | float) -> str:
    text = f"{Decimal(str(value)):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {text}"


def br_date(value: date | datetime | None) -> str:
    return value.strftime("%d/%m/%Y") if value else "—"


def percent(value: Decimal | float) -> str:
    return f"{Decimal(str(value)):.1f}%".replace(".", ",")
