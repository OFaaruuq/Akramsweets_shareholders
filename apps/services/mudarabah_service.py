"""Mudarabah (profit-sharing) pool settings — shareholders vs managing partner."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from apps.models.settings import SystemSetting

DEFAULT_SHAREHOLDER_PERCENT = Decimal('50')
MONEY = Decimal('0.01')


def _parse(raw, default):
    if raw is None or str(raw).strip() == '':
        return default
    try:
        return Decimal(str(raw).strip())
    except (InvalidOperation, ValueError, TypeError):
        return default


def get_mudarabah_shareholder_percent():
    """Percent of Net Profit that goes to the shareholders' pool (default 50)."""
    value = _parse(SystemSetting.get('mudarabah_shareholder_percent'), DEFAULT_SHAREHOLDER_PERCENT)
    if value < 0 or value > 100:
        return DEFAULT_SHAREHOLDER_PERCENT
    return value.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)


def get_mudarabah_partner_percent():
    return (Decimal('100') - get_mudarabah_shareholder_percent()).quantize(
        Decimal('0.0001'), rounding=ROUND_HALF_UP
    )


def save_mudarabah_settings(shareholder_percent):
    value = _parse(shareholder_percent, DEFAULT_SHAREHOLDER_PERCENT)
    if value < 0 or value > 100:
        raise ValueError('Mudarabah shareholder percent must be between 0 and 100.')
    SystemSetting.set(
        'mudarabah_shareholder_percent',
        str(value.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)),
    )


def ensure_default_mudarabah_settings():
    if not SystemSetting.get('mudarabah_shareholder_percent'):
        SystemSetting.set('mudarabah_shareholder_percent', str(DEFAULT_SHAREHOLDER_PERCENT))


def split_net_profit(net_profit, shareholder_percent=None):
    """
    Split company Net Profit into shareholders' pool and managing partner share.

    Returns (shareholders_pool, managing_partner_share, shareholder_percent_used).
    """
    net = Decimal(net_profit or 0)
    percent = (
        get_mudarabah_shareholder_percent()
        if shareholder_percent is None
        else Decimal(shareholder_percent)
    )
    pool = (net * percent / Decimal('100')).quantize(MONEY, rounding=ROUND_HALF_UP)
    partner = (net - pool).quantize(MONEY, rounding=ROUND_HALF_UP)
    return pool, partner, percent


def get_mudarabah_settings():
    shareholder_percent = get_mudarabah_shareholder_percent()
    return {
        'shareholder_percent': shareholder_percent,
        'partner_percent': Decimal('100') - shareholder_percent,
        'label': (
            f'{shareholder_percent:g}% shareholders / '
            f'{(Decimal("100") - shareholder_percent):g}% Akram Sweets (managing partner)'
        ),
    }
