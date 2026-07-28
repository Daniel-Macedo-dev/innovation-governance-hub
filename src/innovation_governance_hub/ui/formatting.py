from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

_MILLION = Decimal("1000000")
_THOUSAND = Decimal("1000")


def brl(value: Decimal | int | float) -> str:
    text = f"{Decimal(str(value)):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {text}"


def _round_tenth(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def _short_number(rounded: Decimal) -> str:
    """Número já arredondado, sem zeros inúteis e com vírgula decimal."""
    if rounded == rounded.to_integral_value():
        return str(int(rounded))
    return f"{rounded:.1f}".replace(".", ",")


def compact_brl(value: Decimal | int | float) -> str:
    """Valor monetário compacto para cards (mil/milhão/milhões) em pt-BR.

    Abaixo de mil usa o formato completo. A abreviação é apenas de apresentação;
    o valor armazenado não é alterado. Use `brl()` quando precisar do valor exato.
    """
    amount = Decimal(str(value))
    magnitude = abs(amount)
    if magnitude < _THOUSAND:
        return brl(amount)
    sign = "-" if amount < 0 else ""
    thousands = _round_tenth(magnitude / _THOUSAND)
    # Arredondamento pode promover milhares para o próximo milhão (999.950 -> 1 milhão).
    if magnitude >= _MILLION or thousands >= _THOUSAND:
        millions = _round_tenth(magnitude / _MILLION)
        unit = "milhão" if Decimal("1") <= millions < Decimal("2") else "milhões"
        return f"R$ {sign}{_short_number(millions)} {unit}"
    return f"R$ {sign}{_short_number(thousands)} mil"


def br_date(value: date | datetime | None) -> str:
    return value.strftime("%d/%m/%Y") if value else "—"


def percent(value: Decimal | float) -> str:
    return f"{Decimal(str(value)):.1f}%".replace(".", ",")
