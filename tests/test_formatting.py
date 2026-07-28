"""Formatação monetária: valor exato (`brl`) e compacto executivo (`compact_brl`)."""

from decimal import Decimal

import pytest

from innovation_governance_hub.ui.formatting import brl, compact_brl


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (950, "R$ 950,00"),
        (1_000, "R$ 1 mil"),
        (326_000, "R$ 326 mil"),
        (326_500, "R$ 326,5 mil"),
        (1_000_000, "R$ 1 milhão"),
        (1_200_000, "R$ 1,2 milhão"),
        (2_000_000, "R$ 2 milhões"),
        (12_500_000, "R$ 12,5 milhões"),
    ],
)
def test_compact_brl_matches_reference(value, expected):
    assert compact_brl(value) == expected


def test_compact_brl_accepts_decimal_int_and_float():
    assert compact_brl(Decimal("326500")) == "R$ 326,5 mil"
    assert compact_brl(326_500) == "R$ 326,5 mil"
    assert compact_brl(326_500.0) == "R$ 326,5 mil"


def test_compact_brl_zero_and_small_values_use_full_format():
    assert compact_brl(0) == "R$ 0,00"
    assert compact_brl(999) == "R$ 999,00"
    assert compact_brl(999.9) == "R$ 999,90"


def test_compact_brl_negative_balance():
    assert compact_brl(-1_200_000) == "R$ -1,2 milhão"
    assert compact_brl(-326_000) == "R$ -326 mil"


def test_compact_brl_no_useless_decimal_zero():
    assert compact_brl(1_000_000) == "R$ 1 milhão"
    assert compact_brl(2_000_000) == "R$ 2 milhões"
    assert "1,0" not in compact_brl(1_000_000)


def test_compact_brl_uses_comma_decimal_separator():
    assert compact_brl(326_500) == "R$ 326,5 mil"
    assert "," in compact_brl(1_200_000)
    assert "." not in compact_brl(1_200_000)


def test_compact_brl_rounding_boundaries():
    assert compact_brl(999_900) == "R$ 999,9 mil"
    assert compact_brl(999_999) == "R$ 1 milhão"  # promove para milhão
    assert compact_brl(1_949_999) == "R$ 1,9 milhão"
    assert compact_brl(1_999_999) == "R$ 2 milhões"  # singular/plural pelo valor exibido


def test_brl_still_returns_full_value():
    assert brl(1_200_000) == "R$ 1.200.000,00"
    assert brl(326_000) == "R$ 326.000,00"
    assert brl(950) == "R$ 950,00"
