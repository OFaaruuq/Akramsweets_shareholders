"""Company share value configuration (1 share = X currency units)."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from apps.models.settings import SystemSetting

DEFAULT_SHARE_VALUE = Decimal('1000')
MONEY = Decimal('0.01')
SHARES = Decimal('0.0001')


def _parse_decimal(raw, default):
    if raw is None or str(raw).strip() == '':
        return default
    try:
        return Decimal(str(raw).strip())
    except (InvalidOperation, ValueError, TypeError):
        return default


def get_share_value():
    """Configured value of one share (e.g. 1000 means 1 share = 1000)."""
    value = _parse_decimal(SystemSetting.get('share_value'), DEFAULT_SHARE_VALUE)
    if value < 0:
        return DEFAULT_SHARE_VALUE
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def get_total_company_shares():
    """
    Optional total shares outstanding.

    When set (> 0), ownership % can be shown as an equivalent share count.
    """
    value = _parse_decimal(SystemSetting.get('total_company_shares'), Decimal('0'))
    if value < 0:
        return Decimal('0')
    return value.quantize(SHARES, rounding=ROUND_HALF_UP)


def save_share_settings(share_value, total_company_shares=None):
    value = _parse_decimal(share_value, DEFAULT_SHARE_VALUE)
    if value < 0:
        raise ValueError('Share value cannot be negative.')
    SystemSetting.set('share_value', str(value.quantize(MONEY, rounding=ROUND_HALF_UP)))

    if total_company_shares is None or str(total_company_shares).strip() == '':
        SystemSetting.set('total_company_shares', '')
    else:
        total = _parse_decimal(total_company_shares, Decimal('0'))
        if total < 0:
            raise ValueError('Total company shares cannot be negative.')
        SystemSetting.set('total_company_shares', str(total.quantize(SHARES, rounding=ROUND_HALF_UP)))


def shares_for_ownership(ownership_percent, total_shares=None):
    """Equivalent shares for an ownership % when total_company_shares is configured."""
    total = get_total_company_shares() if total_shares is None else Decimal(total_shares or 0)
    if total <= 0:
        return None
    percent = Decimal(ownership_percent or 0)
    return (total * percent / Decimal('100')).quantize(SHARES, rounding=ROUND_HALF_UP)


def capital_for_ownership(ownership_percent, share_value=None, total_shares=None):
    """
    Capital / investment value for an ownership %.

    Requires total_company_shares so share count can be derived:
    capital = (total_shares × ownership%) × share_value
    """
    units = shares_for_ownership(ownership_percent, total_shares=total_shares)
    if units is None:
        return None
    unit_value = get_share_value() if share_value is None else Decimal(share_value or 0)
    return (units * unit_value).quantize(MONEY, rounding=ROUND_HALF_UP)


def get_share_settings():
    share_value = get_share_value()
    total_shares = get_total_company_shares()
    currency = '$'
    try:
        from apps.services.certificate_settings_service import get_certificate_settings

        currency = get_certificate_settings().get('currency_symbol') or '$'
    except Exception:
        pass

    return {
        'share_value': share_value,
        'total_company_shares': total_shares,
        'has_total_shares': total_shares > 0,
        'label': f'1 share = {currency}{share_value:,.2f}',
        'currency_symbol': currency,
    }


def ensure_default_share_settings():
    if not SystemSetting.get('share_value'):
        SystemSetting.set('share_value', str(DEFAULT_SHARE_VALUE))
