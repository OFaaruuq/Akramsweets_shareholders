"""Shared decimal/money helpers — single source for rounding and ownership tolerance."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

MONEY = Decimal('0.01')
SHARES = Decimal('0.0001')
OWNERSHIP_TOLERANCE = Decimal('0.01')


def money(value):
    """Round to currency cents (half-up)."""
    try:
        return Decimal(str(value if value is not None else 0)).quantize(MONEY, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        return Decimal('0.00')


def money_value(value):
    """Alias used by period forms — same as money()."""
    return money(value)


def parse_decimal(raw, default='0'):
    if raw is None or str(raw).strip() == '':
        return Decimal(default)
    try:
        return Decimal(str(raw).strip())
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(default)


def ownership_totals_match(total, expected=Decimal('100')):
    return abs(Decimal(total) - Decimal(expected)) <= OWNERSHIP_TOLERANCE
