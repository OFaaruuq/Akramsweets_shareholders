import json
from datetime import datetime
from decimal import Decimal

from apps import db
from apps.models.arrangement import SpecialArrangement
from apps.models.period import MonthlyPeriod, ShareholderCalculation
from apps.models.settings import SystemSetting
from apps.models.shareholder import OwnershipRecord, Shareholder
from apps.models.user import User

DASHBOARD_KPI_KEYS = (
    'dashboard_total_revenues',
    'dashboard_total_expenses',
    'dashboard_cost_of_goods',
    'dashboard_other_income',
    'dashboard_operating_notes',
)


def _decimal_setting(key, default='0'):
    raw = SystemSetting.get(key, default)
    try:
        return Decimal(str(raw or default))
    except Exception:
        return Decimal(default)


def get_dashboard_manual_kpis():
    return {
        'total_revenues': _decimal_setting('dashboard_total_revenues'),
        'total_expenses': _decimal_setting('dashboard_total_expenses'),
        'cost_of_goods': _decimal_setting('dashboard_cost_of_goods'),
        'other_income': _decimal_setting('dashboard_other_income'),
        'operating_notes': SystemSetting.get('dashboard_operating_notes', '') or '',
    }


def save_dashboard_manual_kpis(form):
    SystemSetting.set('dashboard_total_revenues', str(form.total_revenues.data or 0))
    SystemSetting.set('dashboard_total_expenses', str(form.total_expenses.data or 0))
    SystemSetting.set('dashboard_cost_of_goods', str(form.cost_of_goods.data or 0))
    SystemSetting.set('dashboard_other_income', str(form.other_income.data or 0))
    SystemSetting.set('dashboard_operating_notes', (form.operating_notes.data or '').strip())


def _money(value):
    return float(value or 0)


def _period_change(current, previous):
    if previous in (None, 0, Decimal('0')):
        return None
    return float((current - previous) / abs(previous) * 100)


def _sparkline(values, length=12):
    data = [float(v) for v in values]
    if len(data) >= length:
        return data[-length:]
    if not data:
        return [0] * length
    return ([data[0]] * (length - len(data))) + data


def get_available_analytics_years():
    rows = (
        db.session.query(MonthlyPeriod.year)
        .distinct()
        .order_by(MonthlyPeriod.year.desc())
        .all()
    )
    return [row[0] for row in rows]


def _resolve_analytics_year(year):
    available = get_available_analytics_years()
    if not available:
        return datetime.utcnow().year
    if year and year in available:
        return year
    current = datetime.utcnow().year
    if current in available:
        return current
    return available[0]


def _build_shareholder_series(shareholder_trends):
    names = []
    seen = set()
    for trend in shareholder_trends:
        for shareholder in trend['shareholders']:
            if shareholder['name'] not in seen:
                names.append(shareholder['name'])
                seen.add(shareholder['name'])
    names.sort()

    series = []
    for name in names:
        data = []
        for trend in shareholder_trends:
            match = next((s for s in trend['shareholders'] if s['name'] == name), None)
            data.append(match['final_amount'] if match else 0)
        series.append({'name': name, 'data': data})

    return {
        'labels': [trend['label'] for trend in shareholder_trends],
        'series': series,
    }


def _build_analytics_summary(monthly_totals, manual_kpis):
    if not monthly_totals:
        return {
            'profit_months': 0,
            'loss_months': 0,
            'avg_monthly_profit': Decimal('0'),
            'total_distributed': Decimal('0'),
            'best_period': None,
            'worst_period': None,
            'operating_margin': None,
        }

    profit_months = sum(1 for period in monthly_totals if period.total_profit_loss >= 0)
    loss_months = len(monthly_totals) - profit_months
    avg_monthly_profit = sum(
        (period.total_profit_loss for period in monthly_totals),
        Decimal('0'),
    ) / len(monthly_totals)
    total_distributed = Decimal('0')
    for period in monthly_totals:
        total_distributed += sum(
            (calc.final_amount for calc in period.calculations),
            Decimal('0'),
        )

    best_period = max(monthly_totals, key=lambda period: period.total_profit_loss)
    worst_period = min(monthly_totals, key=lambda period: period.total_profit_loss)

    return {
        'profit_months': profit_months,
        'loss_months': loss_months,
        'avg_monthly_profit': avg_monthly_profit,
        'total_distributed': total_distributed,
        'best_period': best_period,
        'worst_period': worst_period,
        'operating_margin': (
            (manual_kpis['total_revenues'] - manual_kpis['total_expenses'] - manual_kpis['cost_of_goods'])
            / manual_kpis['total_revenues'] * 100
            if manual_kpis['total_revenues'] > 0
            else None
        ),
    }


def _build_chart_payload(monthly_totals, distribution_rows, manual_kpis, workflow, is_shareholder_view=False):
    profit_values = [_money(p.total_profit_loss) for p in monthly_totals]
    revenue_values = [_money(p.total_revenues) for p in monthly_totals]
    expense_values = [_money(p.total_expenses) for p in monthly_totals]
    distributed_values = []
    for period in monthly_totals:
        total = sum((calc.final_amount for calc in period.calculations), Decimal('0'))
        distributed_values.append(_money(total))

    labels = [p.period_label for p in monthly_totals]
    if not labels:
        labels = ['N/A']
        profit_values = [0]
        revenue_values = [0]
        expense_values = [0]
        distributed_values = [0]

    pie_labels = []
    pie_series = []
    pie_rows = []
    for calc in distribution_rows:
        pie_labels.append(calc.shareholder.name)
        pie_series.append(_money(calc.final_amount))
        pie_rows.append({
            'name': calc.shareholder.name,
            'amount': _money(calc.final_amount),
            'percent': _money(calc.ownership_percent),
        })

    if not pie_series:
        pie_labels = ['No data']
        pie_series = [1]
        pie_rows = []

    return {
        'sparklines': {
            'revenues': _sparkline(revenue_values or [_money(manual_kpis['total_revenues'])]),
            'profit': _sparkline(profit_values),
            'shareholders': _sparkline([workflow['active_shareholders']] * max(1, len(labels))),
            'distributed': _sparkline(distributed_values),
            'pending': _sparkline([workflow['review_periods']] * max(1, len(labels))),
        },
        'profit_over_time': {
            'labels': labels,
            'profits': profit_values,
            'distributed': distributed_values,
        },
        'distribution_pie': {
            'labels': pie_labels,
            'series': pie_series,
            'rows': pie_rows,
        },
        'revenue_stats': {
            'labels': labels[-7:] if len(labels) > 7 else labels,
            'profits': profit_values[-7:] if len(profit_values) > 7 else profit_values,
            'revenues': revenue_values[-7:] if len(revenue_values) > 7 else revenue_values,
        },
        'analytics': {
            'is_shareholder_view': is_shareholder_view,
            'earning_reports': {
                'labels': labels,
                'profits': profit_values,
                'distributed': distributed_values,
                'expenses': expense_values,
                'revenues': revenue_values,
            },
            'growth_rate': {
                'labels': labels,
                'company': profit_values,
                'distributed': distributed_values,
            },
        },
    }


def get_dashboard_metrics(year=None):
    manual_kpis = get_dashboard_manual_kpis()
    selected_year = _resolve_analytics_year(year)
    available_years = get_available_analytics_years()
    active_shareholders = Shareholder.query.filter_by(is_active=True).count()
    draft_periods = MonthlyPeriod.query.filter_by(status=MonthlyPeriod.STATUS_DRAFT).count()
    review_periods = MonthlyPeriod.query.filter_by(status=MonthlyPeriod.STATUS_REVIEW).count()
    approved_periods = MonthlyPeriod.query.filter_by(status=MonthlyPeriod.STATUS_APPROVED).count()

    latest_period = (
        MonthlyPeriod.query.order_by(MonthlyPeriod.year.desc(), MonthlyPeriod.month.desc()).first()
    )
    previous_period = None
    if latest_period:
        previous_period = (
            MonthlyPeriod.query.filter(
                (MonthlyPeriod.year < latest_period.year)
                | (
                    (MonthlyPeriod.year == latest_period.year)
                    & (MonthlyPeriod.month < latest_period.month)
                )
            )
            .order_by(MonthlyPeriod.year.desc(), MonthlyPeriod.month.desc())
            .first()
        )

    latest_profit = latest_period.total_profit_loss if latest_period else Decimal('0')
    previous_profit = previous_period.total_profit_loss if previous_period else Decimal('0')
    latest_distributed = Decimal('0')
    if latest_period and latest_period.calculations.count():
        latest_distributed = sum(
            (calc.final_amount for calc in latest_period.calculations),
            Decimal('0'),
        )

    pending_approval = review_periods
    from apps.models.shareholder import CapitalWithdrawalRequest

    pending_withdrawals = CapitalWithdrawalRequest.query.filter_by(
        status=CapitalWithdrawalRequest.STATUS_PENDING
    ).count()
    approvals_inbox_count = review_periods + pending_withdrawals

    recent_periods = (
        MonthlyPeriod.query.order_by(MonthlyPeriod.year.desc(), MonthlyPeriod.month.desc()).limit(6).all()
    )

    monthly_totals_query = MonthlyPeriod.query.filter_by(status=MonthlyPeriod.STATUS_APPROVED)
    if selected_year:
        monthly_totals_query = monthly_totals_query.filter(MonthlyPeriod.year == selected_year)
    monthly_totals = (
        monthly_totals_query.order_by(MonthlyPeriod.year.asc(), MonthlyPeriod.month.asc()).all()
    )

    distribution_source = latest_period
    if distribution_source and distribution_source.status != MonthlyPeriod.STATUS_APPROVED:
        distribution_source = (
            MonthlyPeriod.query.filter_by(status=MonthlyPeriod.STATUS_APPROVED)
            .order_by(MonthlyPeriod.year.desc(), MonthlyPeriod.month.desc())
            .first()
        )

    distribution_rows = []
    if distribution_source:
        distribution_rows = (
            ShareholderCalculation.query.filter_by(period_id=distribution_source.id)
            .join(Shareholder)
            .order_by(Shareholder.name)
            .all()
        )

    ytd_company_profit = sum(
        (period.total_profit_loss for period in monthly_totals),
        Decimal('0'),
    )

    shareholder_trends = []
    analytics_table_rows = []
    for period in monthly_totals:
        calcs = (
            ShareholderCalculation.query.filter_by(period_id=period.id)
            .join(Shareholder)
            .order_by(Shareholder.name)
            .all()
        )
        shareholders = [
            {
                'id': calc.shareholder_id,
                'name': calc.shareholder.name,
                'final_amount': float(calc.final_amount),
                'ownership_percent': float(calc.ownership_percent),
            }
            for calc in calcs
        ]
        distributed_total = sum((calc.final_amount for calc in calcs), Decimal('0'))
        trend = {
            'period_id': period.id,
            'label': period.period_label,
            'company_total': float(period.total_profit_loss),
            'distributed_total': float(distributed_total),
            'is_profit': period.total_profit_loss >= 0,
            'reports_sent': period.reports_sent_at is not None,
            'shareholders': shareholders,
        }
        shareholder_trends.append(trend)
        analytics_table_rows.append(trend)

    net_operating_profit = (
        manual_kpis['total_revenues']
        - manual_kpis['total_expenses']
        - manual_kpis['cost_of_goods']
        + manual_kpis['other_income']
    )

    workflow = {
        'active_shareholders': active_shareholders,
        'draft_periods': draft_periods,
        'review_periods': review_periods,
        'approved_periods': approved_periods,
    }
    chart_data = _build_chart_payload(monthly_totals, distribution_rows, manual_kpis, workflow)
    chart_data['analytics']['shareholder_series'] = _build_shareholder_series(shareholder_trends)
    analytics_summary = _build_analytics_summary(monthly_totals, manual_kpis)

    return {
        'active_shareholders': active_shareholders,
        'draft_periods': draft_periods,
        'review_periods': review_periods,
        'approved_periods': approved_periods,
        'latest_period': latest_period,
        'latest_profit': latest_profit,
        'latest_distributed': latest_distributed,
        'pending_approval': pending_approval,
        'pending_withdrawals': pending_withdrawals,
        'approvals_inbox_count': approvals_inbox_count,
        'recent_periods': recent_periods,
        'monthly_totals': monthly_totals,
        'shareholder_trends': shareholder_trends,
        'analytics_table_rows': list(reversed(analytics_table_rows)),
        'distribution_rows': distribution_rows,
        'distribution_period': distribution_source,
        'total_users': User.query.count(),
        'active_arrangements': SpecialArrangement.query.filter_by(is_active=True).count(),
        'manual_kpis': manual_kpis,
        'net_operating_profit': net_operating_profit,
        'ytd_company_profit': ytd_company_profit,
        'profit_change_pct': _period_change(latest_profit, previous_profit),
        'selected_year': selected_year,
        'available_years': available_years,
        'analytics_summary': analytics_summary,
        'chart_data': chart_data,
        'chart_data_json': json.dumps(chart_data),
    }


def get_shareholder_dashboard_metrics(shareholder_id, year=None):
    portal = get_shareholder_portal_metrics(shareholder_id)
    manual_kpis = get_dashboard_manual_kpis()
    selected_year = _resolve_analytics_year(year)
    available_years = get_available_analytics_years()

    filtered_rows = [
        row for row in portal['report_rows']
        if row['period'].year == selected_year
    ] if selected_year else portal['report_rows']

    payout_values = [_money(row['calculation'].final_amount) for row in reversed(filtered_rows)]
    labels = [row['period'].period_label for row in reversed(filtered_rows)]
    if not labels:
        labels = ['N/A']
        payout_values = [0]

    profit_months = sum(1 for row in filtered_rows if row['calculation'].final_amount >= 0)
    loss_months = len(filtered_rows) - profit_months
    ytd_for_year = sum((row['calculation'].final_amount for row in filtered_rows), Decimal('0'))
    avg_payout = ytd_for_year / len(filtered_rows) if filtered_rows else Decimal('0')
    best_row = max(filtered_rows, key=lambda row: row['calculation'].final_amount) if filtered_rows else None
    worst_row = min(filtered_rows, key=lambda row: row['calculation'].final_amount) if filtered_rows else None

    shareholder_trends = []
    for row in filtered_rows:
        calc = row['calculation']
        shareholder_trends.append({
            'period_id': row['period'].id,
            'label': row['period'].period_label,
            'company_total': float(calc.final_amount),
            'distributed_total': float(calc.final_amount),
            'is_profit': calc.final_amount >= 0,
            'reports_sent': row['period'].reports_sent_at is not None,
            'shareholders': [{
                'id': portal['shareholder'].id,
                'name': portal['shareholder'].name,
                'final_amount': float(calc.final_amount),
                'ownership_percent': float(calc.ownership_percent),
            }],
        })

    chart_data = _build_chart_payload([], [], manual_kpis, {'review_periods': 0, 'active_shareholders': 1}, is_shareholder_view=True)
    chart_data['sparklines'] = {
        'revenues': _sparkline(payout_values),
        'profit': _sparkline(payout_values),
        'shareholders': _sparkline([_money(portal['ownership_percent'])] * len(payout_values)),
        'distributed': _sparkline(payout_values),
        'pending': _sparkline([len(filtered_rows)] * len(payout_values)),
    }
    chart_data['profit_over_time'] = {'labels': labels, 'profits': payout_values, 'distributed': payout_values}
    chart_data['distribution_pie'] = {
        'labels': [portal['shareholder'].name],
        'series': [_money(portal['latest_calculation'].final_amount) if portal['latest_calculation'] else 1],
        'rows': [{
            'name': portal['shareholder'].name,
            'amount': _money(portal['latest_calculation'].final_amount) if portal['latest_calculation'] else 0,
            'percent': _money(portal['ownership_percent']),
        }],
    }
    chart_data['revenue_stats'] = {
        'labels': labels[-7:],
        'profits': payout_values[-7:] if payout_values else [0],
        'revenues': payout_values[-7:] if payout_values else [0],
    }
    chart_data['analytics'] = {
        'is_shareholder_view': True,
        'earning_reports': {
            'labels': labels,
            'profits': payout_values,
            'distributed': payout_values,
            'expenses': [0] * len(labels),
            'revenues': payout_values,
        },
        'growth_rate': {'labels': labels, 'company': payout_values, 'distributed': payout_values},
        'shareholder_series': _build_shareholder_series(shareholder_trends),
    }

    prior_payout = None
    if len(filtered_rows) > 1:
        prior_payout = filtered_rows[1]['calculation'].final_amount
    latest_payout = filtered_rows[0]['calculation'].final_amount if filtered_rows else Decimal('0')

    return {
        **portal,
        'report_rows': filtered_rows,
        'manual_kpis': manual_kpis,
        'latest_profit': latest_payout,
        'latest_distributed': latest_payout,
        'pending_approval': 0,
        'pending_withdrawals': 0,
        'approvals_inbox_count': 0,
        'active_shareholders': 1,
        'draft_periods': 0,
        'review_periods': 0,
        'approved_periods': len(filtered_rows),
        'distribution_rows': [],
        'distribution_period': filtered_rows[0]['period'] if filtered_rows else portal['latest_period'],
        'recent_periods': [row['period'] for row in filtered_rows[:6]],
        'ytd_company_profit': ytd_for_year,
        'ytd_total': ytd_for_year,
        'net_operating_profit': ytd_for_year,
        'profit_change_pct': _period_change(latest_payout, prior_payout),
        'selected_year': selected_year,
        'available_years': available_years,
        'shareholder_trends': shareholder_trends,
        'analytics_table_rows': list(reversed(shareholder_trends)),
        'analytics_summary': {
            'profit_months': profit_months,
            'loss_months': loss_months,
            'avg_monthly_profit': avg_payout,
            'total_distributed': ytd_for_year,
            'best_period': best_row['period'] if best_row else None,
            'worst_period': worst_row['period'] if worst_row else None,
            'operating_margin': None,
        },
        'chart_data': chart_data,
        'chart_data_json': json.dumps(chart_data),
    }


def get_shareholder_portal_metrics(shareholder_id):
    from datetime import datetime

    from apps.services.calculation_service import get_ytd_totals
    from apps.services.shareholder_service import get_ownership_percent

    shareholder = Shareholder.query.get_or_404(shareholder_id)
    today = datetime.utcnow().date()
    ownership_percent = get_ownership_percent(shareholder, today)

    approved_query = (
        MonthlyPeriod.query.filter_by(status=MonthlyPeriod.STATUS_APPROVED)
        .order_by(MonthlyPeriod.year.desc(), MonthlyPeriod.month.desc())
    )
    approved_periods = approved_query.all()

    report_rows = []
    for period in approved_periods:
        calc = ShareholderCalculation.query.filter_by(
            period_id=period.id,
            shareholder_id=shareholder_id,
        ).first()
        if calc:
            report_rows.append({'period': period, 'calculation': calc})

    latest_calc = report_rows[0]['calculation'] if report_rows else None
    latest_period = report_rows[0]['period'] if report_rows else None
    ytd_total = (
        get_ytd_totals(shareholder_id, latest_period.year, latest_period.month)
        if latest_period
        else Decimal('0')
    )

    ownership_history = shareholder.ownership_records.order_by(
        OwnershipRecord.effective_from.desc()
    ).all()

    monthly_payouts = list(reversed(report_rows[:12]))
    lifetime_total = sum((row['calculation'].final_amount for row in report_rows), Decimal('0'))

    return {
        'shareholder': shareholder,
        'ownership_percent': ownership_percent,
        'latest_calculation': latest_calc,
        'latest_period': latest_period,
        'ytd_total': ytd_total,
        'lifetime_total': lifetime_total,
        'report_rows': report_rows,
        'monthly_payouts': monthly_payouts,
        'ownership_history': ownership_history,
        'approved_report_count': len(report_rows),
    }
