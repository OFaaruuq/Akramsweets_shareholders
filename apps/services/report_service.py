from decimal import Decimal

from apps.models.period import ManualAdjustment
from apps.services.calculation_service import get_ytd_totals, money
from apps.services.shareholder_service import get_active_arrangements


def _arrangement_breakdown(period, calculation):
    as_of_date = period.as_of_date
    total = money(period.total_profit_loss)
    is_profit = total >= 0
    arrangements = [a for a in get_active_arrangements(as_of_date, is_profit) if a.applies_to_all_others]
    lines = []

    if calculation.arrangement_received:
        for arrangement in arrangements:
            if arrangement.recipient_shareholder_id == calculation.shareholder_id:
                lines.append({
                    'name': arrangement.name,
                    'percent': arrangement.bonus_percent,
                    'role': 'received',
                    'amount': calculation.arrangement_received,
                    'description': f'{arrangement.bonus_percent}% received from other shareholders',
                })

    if calculation.arrangement_deduction:
        for arrangement in arrangements:
            if arrangement.recipient_shareholder_id != calculation.shareholder_id:
                lines.append({
                    'name': arrangement.name,
                    'percent': arrangement.bonus_percent,
                    'role': 'deduction',
                    'amount': calculation.arrangement_deduction,
                    'description': f'{arrangement.bonus_percent}% redirected to {arrangement.recipient.name}',
                })
                break

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

    from apps.services.brand_service import get_brand_settings

    brand = get_brand_settings()

    return {
        'period_label': period.period_label,
        'generated_at': period.approved_at or period.calculated_at,
        'company_total': period.total_profit_loss,
        'company_name': brand['company_name'],
        'brand_primary_color': brand['primary_color'],
        'brand_secondary_color': brand['secondary_color'],
        'brand_accent_color': brand['accent_color'],
        'brand_logo_path': brand['logo_filesystem_path'],
        'shareholder_name': shareholder.name,
        'shareholder_email': shareholder.email,
        'shareholder_phone': shareholder.phone,
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
