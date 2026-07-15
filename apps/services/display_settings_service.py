"""Shared display settings (currency, company) for templates and reports."""

from __future__ import annotations


def get_display_settings():
    from apps.services.brand_service import get_brand_settings
    from apps.services.certificate_settings_service import get_certificate_settings
    from apps.services.share_value_service import get_share_settings

    brand = get_brand_settings()
    cert = get_certificate_settings()
    currency = cert.get('currency_symbol') or '$'
    share = get_share_settings()
    return {
        'company_name': brand['company_name'],
        'currency_symbol': currency,
        'primary_color': brand['primary_color'],
        'secondary_color': brand['secondary_color'],
        'accent_color': brand['accent_color'],
        'logo_url': brand.get('logo_url'),
        'share_value': share['share_value'],
        'total_company_shares': share['total_company_shares'],
        'share_value_label': share['label'],
        'has_total_shares': share['has_total_shares'],
    }


def money_label(amount, currency_symbol=None):
    """Format a number with the configured currency symbol."""
    if currency_symbol is None:
        currency_symbol = get_display_settings()['currency_symbol']
    value = float(amount or 0)
    sign = '-' if value < 0 else ''
    return f'{sign}{currency_symbol}{abs(value):,.2f}'
