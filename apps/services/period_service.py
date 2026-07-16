from calendar import month_name
from datetime import datetime
from decimal import Decimal

from apps.models.period import MonthlyPeriod
from apps.services.dashboard_service import get_dashboard_manual_kpis
from apps.services.decimal_utils import OWNERSHIP_TOLERANCE, money_value
from apps.services.shareholder_service import (
    get_active_arrangements,
    get_active_shareholders,
    get_ownership_percent,
    validate_ownership_totals,
)

MONTH_CHOICES = [(i, month_name[i]) for i in range(1, 13)]


def resolve_period_totals(
    *,
    net_profit,
    income=None,
    gross_profit=None,
    total_gross_profit=None,
    total_income=None,
    total_operating_expenses=None,
):
    """
    Resolve monthly period amounts.

    Shareholder distribution always uses the entered Net Profit (from Odoo).
    Optional P&L lines are stored for reference only; missing values default to 0.
    """
    net_profit = money_value(net_profit)
    income = money_value(income)
    gross_profit = money_value(gross_profit)
    total_gross_profit = money_value(total_gross_profit)
    total_income = money_value(total_income)
    total_operating_expenses = money_value(total_operating_expenses)

    cost_of_goods = income - gross_profit
    other_income = total_income - income

    return net_profit, {
        'income': income,
        'gross_profit': gross_profit,
        'total_gross_profit': total_gross_profit,
        'total_income': total_income,
        'total_expenses': total_operating_expenses,
        'total_profit_loss': net_profit,
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
    blocking_errors = []
    as_of_date = period_as_of_date(year, month)

    ownership_total, shareholders = validate_ownership_totals(as_of_date)
    ownership_rows = []
    from apps.services.shareholder_service import effective_shares_and_capital

    for shareholder in shareholders:
        percent = get_ownership_percent(shareholder, as_of_date)
        capital_info = effective_shares_and_capital(shareholder, percent)
        ownership_rows.append({
            'id': shareholder.id,
            'name': shareholder.name,
            'is_owner': shareholder.is_owner,
            'ownership_percent': float(percent),
            'investment': capital_info['investment'],
            'shares': capital_info['shares'],
            'registered_investment': capital_info['registered_investment'],
            'registered_shares': capital_info['registered_shares'],
            'capital_source': capital_info['source'],
        })

    ownership_valid = bool(shareholders) and abs(ownership_total - Decimal('100')) <= OWNERSHIP_TOLERANCE
    if not shareholders:
        msg = 'No active shareholders found for this period.'
        warnings.append(msg)
        blocking_errors.append(msg)
    elif not ownership_valid:
        msg = (
            f'Ownership totals {ownership_total:.4f}% — must equal exactly 100.0000% '
            'before profit calculation or approval.'
        )
        warnings.append(msg)
        blocking_errors.append(msg)

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
            'explanation': (
                f'After normal pool × ownership %, {arrangement.bonus_percent}% of each source '
                f"shareholder's base profit is transferred to {arrangement.recipient.name}."
            ),
        })

    # Capital withdrawal warnings (profit continues until effective exit)
    withdrawal_warnings = []
    try:
        from apps.models.shareholder import CapitalWithdrawalRequest

        open_withdrawals = CapitalWithdrawalRequest.query.filter(
            CapitalWithdrawalRequest.status.in_([
                CapitalWithdrawalRequest.STATUS_PENDING,
                CapitalWithdrawalRequest.STATUS_APPROVED,
            ])
        ).all()
        for req in open_withdrawals:
            due = req.deadline_at.strftime('%d-%b-%Y') if req.deadline_at else 'TBD'
            withdrawal_warnings.append({
                'shareholder_id': req.shareholder_id,
                'shareholder_name': req.shareholder.name if req.shareholder else 'Shareholder',
                'status': req.status,
                'amount': float(req.amount or 0),
                'deadline': due,
                'message': (
                    f'{req.shareholder.name if req.shareholder else "Shareholder"} has a '
                    f'{req.status} withdrawal request. Capital return due: {due}. '
                    'Profit distribution continues until the withdrawal effective date.'
                ),
            })
            warnings.append(withdrawal_warnings[-1]['message'])
    except Exception:
        pass

    return {
        'as_of_date': as_of_date,
        'ownership_rows': ownership_rows,
        'ownership_total': float(ownership_total),
        'ownership_valid': ownership_valid,
        'can_calculate': ownership_valid,
        'blocking_errors': blocking_errors,
        'arrangements': arrangement_rows,
        'withdrawal_warnings': withdrawal_warnings,
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

    return context
