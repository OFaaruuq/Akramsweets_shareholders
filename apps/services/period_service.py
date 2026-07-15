from calendar import month_name
from datetime import datetime
from decimal import Decimal

from apps.models.period import MonthlyPeriod
from apps.services.dashboard_service import get_dashboard_manual_kpis
from apps.services.shareholder_service import (
    get_active_arrangements,
    get_active_shareholders,
    get_ownership_percent,
    validate_ownership_totals,
)

MONTH_CHOICES = [(i, month_name[i]) for i in range(1, 13)]
OWNERSHIP_TOLERANCE = Decimal('0.01')


def money_value(value):
    return Decimal(value or 0)


def resolve_period_totals(
    *,
    income,
    gross_profit,
    total_gross_profit,
    total_income,
    total_operating_expenses,
    net_profit,
):
    """
    Persist the full manual P&L statement.

    Shareholder distribution always uses the entered Net Profit.
    Legacy columns are kept in sync for charts/reports that still read them.
    """
    income = money_value(income)
    gross_profit = money_value(gross_profit)
    total_gross_profit = money_value(total_gross_profit)
    total_income = money_value(total_income)
    total_operating_expenses = money_value(total_operating_expenses)
    net_profit = money_value(net_profit)

    # Implied COGS for compatibility displays (Income − Gross Profit)
    cost_of_goods = income - gross_profit
    # Other income portion implied by Total Income − Income
    other_income = total_income - income

    return net_profit, {
        'income': income,
        'gross_profit': gross_profit,
        'total_gross_profit': total_gross_profit,
        'total_income': total_income,
        'total_expenses': total_operating_expenses,
        'total_profit_loss': net_profit,
        # Legacy mirrors
        'total_revenues': income,
        'cost_of_goods': cost_of_goods,
        'other_income': other_income,
        'entry_mode': 'pnl',
    }


def period_as_of_date(year, month):
    from calendar import monthrange

    last_day = monthrange(year, month)[1]
    return datetime(year, month, last_day).date()


def get_suggested_period():
    latest = (
        MonthlyPeriod.query.order_by(MonthlyPeriod.year.desc(), MonthlyPeriod.month.desc()).first()
    )
    now = datetime.utcnow()
    if not latest:
        return {'year': now.year, 'month': now.month}

    year, month = latest.year, latest.month + 1
    if month > 12:
        month = 1
        year += 1
    return {'year': year, 'month': month}


def get_prior_period(year, month):
    if month == 1:
        return MonthlyPeriod.query.filter_by(year=year - 1, month=12).first()
    return MonthlyPeriod.query.filter_by(year=year, month=month - 1).first()


def get_period_readiness(year, month):
    warnings = []
    as_of_date = period_as_of_date(year, month)

    ownership_total, shareholders = validate_ownership_totals(as_of_date)
    ownership_rows = []
    for shareholder in shareholders:
        percent = get_ownership_percent(shareholder, as_of_date)
        ownership_rows.append({
            'id': shareholder.id,
            'name': shareholder.name,
            'is_owner': shareholder.is_owner,
            'ownership_percent': float(percent),
        })

    if not shareholders:
        warnings.append('No active shareholders found for this period.')
    elif abs(ownership_total - Decimal('100')) > OWNERSHIP_TOLERANCE:
        warnings.append(
            f'Ownership totals {ownership_total:.4f}% — must equal 100% before calculation.'
        )

    prior = get_prior_period(year, month)
    if prior is None:
        warnings.append('No prior monthly period exists. This will be the first entry.')
    elif prior.status != MonthlyPeriod.STATUS_APPROVED:
        warnings.append(
            f'Prior period {prior.period_label} is {prior.status} — approve it before closing this month.'
        )

    existing = MonthlyPeriod.query.filter_by(year=year, month=month).first()
    if existing:
        warnings.append(f'A period for {year}-{month:02d} already exists.')

    arrangements = get_active_arrangements(as_of_date, True)
    active_ids = {row['id'] for row in ownership_rows}
    arrangement_rows = []
    for arrangement in arrangements:
        sources = arrangement.source_label()
        warning = None
        if arrangement.recipient_shareholder_id not in active_ids:
            warning = (
                f'Recipient {arrangement.recipient.name} is inactive or has 0% ownership — '
                'this arrangement will be skipped.'
            )
        elif not arrangement.applies_to_all_others and not arrangement.source_ids():
            warning = 'No source shareholders selected — this arrangement will be skipped until sources are set.'
        arrangement_rows.append({
            'name': arrangement.name,
            'recipient': arrangement.recipient.name,
            'bonus_percent': float(arrangement.bonus_percent),
            'applies_to_all_others': arrangement.applies_to_all_others,
            'sources': sources,
            'apply_on_profit': arrangement.apply_on_profit,
            'apply_on_loss': arrangement.apply_on_loss,
            'warning': warning,
        })

    return {
        'as_of_date': as_of_date,
        'ownership_rows': ownership_rows,
        'ownership_total': float(ownership_total),
        'ownership_valid': abs(ownership_total - Decimal('100')) <= OWNERSHIP_TOLERANCE,
        'arrangements': arrangement_rows,
        'prior_period': prior,
        'existing_period': existing,
        'warnings': warnings,
    }


def get_period_create_context(year=None, month=None):
    suggested = get_suggested_period()
    year = year or suggested['year']
    month = month or suggested['month']
    readiness = get_period_readiness(year, month)
    kpis = get_dashboard_manual_kpis()

    return {
        'suggested_year': suggested['year'],
        'suggested_month': suggested['month'],
        'selected_year': year,
        'selected_month': month,
        'month_choices': MONTH_CHOICES,
        'dashboard_kpis': kpis,
        **readiness,
    }


def apply_period_form_defaults(form, period=None):
    context = get_period_create_context()
    if period:
        return context

    if form.year.data is None:
        form.year.data = context['suggested_year']
    if form.month.data is None:
        form.month.data = context['suggested_month']

    # Leave P&L lines blank — every line must be typed in manually.
    return context
