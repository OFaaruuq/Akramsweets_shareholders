"""Mudarabah (profit-sharing) pool settings — shareholders vs managing partner.

All percentages and partner labels are read from SystemSetting / brand settings.
Nothing in the distribution math is hard-coded beyond a safe bootstrap default
used only when settings have never been configured.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from apps.models.settings import SystemSetting

# Bootstrap default only — overridden by Settings → Mudarabah once saved.
BOOTSTRAP_SHAREHOLDER_PERCENT = Decimal('50')
MONEY = Decimal('0.01')
SETTING_KEY = 'mudarabah_shareholder_percent'


def _parse(raw, default):
    if raw is None or str(raw).strip() == '':
        return default
    try:
        return Decimal(str(raw).strip())
    except (InvalidOperation, ValueError, TypeError):
        return default


def _partner_company_name():
    try:
        from apps.services.brand_service import get_brand_settings

        name = (get_brand_settings().get('company_name') or '').strip()
        if name:
            return name
    except Exception:
        pass
    try:
        from apps.services.display_settings_service import get_display_settings

        name = (get_display_settings().get('company_name') or '').strip()
        if name:
            return name
    except Exception:
        pass
    return 'Managing Partner'


def get_mudarabah_shareholder_percent():
    """Percent of Net Profit that goes to the shareholders' pool (from settings)."""
    value = _parse(SystemSetting.get(SETTING_KEY), BOOTSTRAP_SHAREHOLDER_PERCENT)
    if value < 0 or value > 100:
        return BOOTSTRAP_SHAREHOLDER_PERCENT
    return value.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)


def get_mudarabah_partner_percent():
    return (Decimal('100') - get_mudarabah_shareholder_percent()).quantize(
        Decimal('0.0001'), rounding=ROUND_HALF_UP
    )


def format_percent(value):
    """Human-readable percent without trailing zeros (e.g. 50, 33.3333)."""
    try:
        d = Decimal(str(value)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        d = BOOTSTRAP_SHAREHOLDER_PERCENT
    text = format(d.normalize(), 'f')
    if '.' in text:
        text = text.rstrip('0').rstrip('.')
    return text or '0'


def save_mudarabah_settings(shareholder_percent):
    value = _parse(shareholder_percent, BOOTSTRAP_SHAREHOLDER_PERCENT)
    if value < 0 or value > 100:
        raise ValueError('Mudarabah shareholder percent must be between 0 and 100.')
    SystemSetting.set(
        SETTING_KEY,
        str(value.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)),
    )


def ensure_default_mudarabah_settings():
    if not SystemSetting.get(SETTING_KEY):
        SystemSetting.set(SETTING_KEY, str(BOOTSTRAP_SHAREHOLDER_PERCENT))


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
    partner_percent = Decimal('100') - shareholder_percent
    partner_name = _partner_company_name()
    sh_label = format_percent(shareholder_percent)
    partner_label = format_percent(partner_percent)
    return {
        'shareholder_percent': float(shareholder_percent),
        'partner_percent': float(partner_percent),
        'shareholder_percent_label': sh_label,
        'partner_percent_label': partner_label,
        'partner_name': partner_name,
        'pool_caption': f"Shareholders' Pool ({sh_label}%)",
        'partner_caption': f'{partner_name} Share ({partner_label}%)',
        'label': (
            f'{sh_label}% shareholders / {partner_label}% {partner_name} (managing partner)'
        ),
    }


# Backwards-compatible alias used by older imports / docs references
DEFAULT_SHAREHOLDER_PERCENT = BOOTSTRAP_SHAREHOLDER_PERCENT
