from decimal import Decimal

from apps.models.period import ManualAdjustment
from apps.services.calculation_service import get_ytd_totals, money
from apps.services.shareholder_service import (
    get_active_arrangements,
    get_ownership_percent,
    validate_ownership_totals,
)


def _arrangement_breakdown(period, calculation):
    """
    Rebuild per-arrangement lines from live rules + base shares.

    Aggregated arrangement_received / arrangement_deduction are totals across
    all rules — do not reuse them as each line's amount when multiple apply.
    """
    as_of_date = period.as_of_date
    # Arrangements apply to the shareholders' Mudarabah pool, not full Net Profit.
    pool = money(getattr(period, 'shareholders_pool', None) or period.total_profit_loss)
    company_net = money(period.total_profit_loss)
    is_profit = company_net >= 0
    _, shareholders = validate_ownership_totals(as_of_date)
    active_ids = [sh.id for sh in shareholders]
    bases = {
        sh.id: money(pool * get_ownership_percent(sh, as_of_date) / Decimal('100'))
        for sh in shareholders
    }

    lines = []
    shareholder_id = calculation.shareholder_id

    for arrangement in get_active_arrangements(as_of_date, is_profit):
        recipient_id = arrangement.recipient_shareholder_id
        if recipient_id not in bases:
            continue
        source_ids = arrangement.contributing_shareholder_ids(active_ids)
        if not source_ids:
            continue

        bonus_rate = Decimal(arrangement.bonus_percent) / Decimal('100')
        if shareholder_id == recipient_id:
            amount = money(sum((bases[sid] * bonus_rate for sid in source_ids), Decimal('0')))
            if amount == 0:
                continue
            lines.append({
                'name': arrangement.name,
                'percent': arrangement.bonus_percent,
                'role': 'received',
                'amount': amount,
                'description': (
                    f'{arrangement.bonus_percent}% of base share received from '
                    f'{arrangement.source_label()}'
                ),
            })
        elif shareholder_id in source_ids:
            amount = money(bases[shareholder_id] * bonus_rate)
            if amount == 0:
                continue
            lines.append({
                'name': arrangement.name,
                'percent': arrangement.bonus_percent,
                'role': 'deduction',
                'amount': -amount,
                'description': (
                    f'{arrangement.bonus_percent}% of base share redirected to '
                    f'{arrangement.recipient.name}'
                ),
            })

    return lines


def build_shareholder_report(period, calculation):
    shareholder = calculation.shareholder
    ytd = get_ytd_totals(shareholder.id, period.year, period.month)
    adjustments = (
        ManualAdjustment.query.filter_by(
            period_id=period.id,
            shareholder_id=shareholder.id,
        )
        .order_by(ManualAdjustment.created_at.asc())
        .all()
    )

    from apps.services.brand_service import ensure_default_logo, get_brand_settings
    from apps.services.certificate_settings_service import get_certificate_settings

    ensure_default_logo()
    brand = get_brand_settings()
    cert = get_certificate_settings()
    from apps.services.mudarabah_service import get_mudarabah_shareholder_percent

    stored_pct = getattr(period, 'mudarabah_shareholder_percent', None)
    mudarabah_pct = stored_pct if stored_pct is not None else get_mudarabah_shareholder_percent()

    return {
        'period_label': period.period_label,
        'generated_at': period.approved_at or period.calculated_at,
        'company_total': period.total_profit_loss,
        'shareholders_pool': getattr(period, 'shareholders_pool', None) or 0,
        'managing_partner_share': getattr(period, 'managing_partner_share', None) or 0,
        'mudarabah_shareholder_percent': mudarabah_pct,
        'managing_partner_name': brand['company_name'],
        'company_name': brand['company_name'],
        'brand_primary_color': brand['primary_color'],
        'brand_secondary_color': brand['secondary_color'],
        'brand_accent_color': brand['accent_color'],
        'brand_logo_path': brand['logo_filesystem_path'],
        'currency_symbol': cert.get('currency_symbol') or '$',
        'shareholder_name': shareholder.name,
        'shareholder_email': shareholder.email,
        'shareholder_phone': (
            (shareholder.phone or '').strip()
            or (
                (getattr(getattr(shareholder, 'user_account', None), 'phone', None) or '').strip()
            )
            or None
        ),
        'ownership_percent': calculation.ownership_percent,
        'base_share': calculation.base_share,
        'arrangement_deduction': calculation.arrangement_deduction,
        'arrangement_received': calculation.arrangement_received,
        'arrangements_applied': _arrangement_breakdown(period, calculation),
        'manual_adjustment': calculation.manual_adjustment,
        'adjustment_lines': [
            {
                'amount': row.amount,
                'reason': row.reason,
                'created_at': row.created_at,
            }
            for row in adjustments
        ],
        'final_amount': calculation.final_amount,
        'ytd_total': ytd,
        'odoo_reference': period.odoo_reference,
        'notes': period.notes,
    }
