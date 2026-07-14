from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from apps import db
from apps.models.period import ManualAdjustment, MonthlyPeriod, ShareholderCalculation
from apps.services.shareholder_service import (
    get_active_arrangements,
    get_active_shareholders,
    get_ownership_percent,
    validate_ownership_totals,
)

MONEY = Decimal('0.01')
OWNERSHIP_TOLERANCE = Decimal('0.01')
RECONCILIATION_TOLERANCE = Decimal('0.01')


def money(value):
    return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)


def _assert_ownership_valid(as_of_date):
    ownership_total, shareholders = validate_ownership_totals(as_of_date)
    if not shareholders:
        raise ValueError('No active shareholders found for this period.')
    if abs(ownership_total - Decimal('100')) > OWNERSHIP_TOLERANCE:
        raise ValueError(
            f'Ownership must total 100% (currently {ownership_total:.4f}%). '
            'Update shareholder ownership records before calculating.'
        )
    return shareholders


def _build_calculation_rows(total, as_of_date, adjustments=None):
    is_profit = total >= 0
    shareholders = _assert_ownership_valid(as_of_date)

    rows = {}
    for shareholder in shareholders:
        ownership = get_ownership_percent(shareholder, as_of_date)
        base = money(total * ownership / Decimal('100'))
        rows[shareholder.id] = {
            'shareholder_id': shareholder.id,
            'shareholder_name': shareholder.name,
            'ownership_percent': ownership,
            'base_share': base,
            'arrangement_deduction': Decimal('0'),
            'arrangement_received': Decimal('0'),
            'manual_adjustment': Decimal('0'),
        }

    arrangements = get_active_arrangements(as_of_date, is_profit)
    for arrangement in arrangements:
        if not arrangement.applies_to_all_others:
            continue
        bonus_rate = Decimal(arrangement.bonus_percent) / Decimal('100')
        recipient_id = arrangement.recipient_shareholder_id

        for shareholder in shareholders:
            if shareholder.id == recipient_id:
                continue
            if shareholder.id not in rows:
                continue
            deduction = money(rows[shareholder.id]['base_share'] * bonus_rate)
            rows[shareholder.id]['arrangement_deduction'] -= deduction
            if recipient_id in rows:
                rows[recipient_id]['arrangement_received'] += deduction

    if adjustments:
        for adjustment in adjustments:
            if adjustment.shareholder_id in rows:
                rows[adjustment.shareholder_id]['manual_adjustment'] += money(adjustment.amount)

    result = []
    for data in rows.values():
        final_amount = money(
            data['base_share']
            + data['arrangement_deduction']
            + data['arrangement_received']
            + data['manual_adjustment']
        )
        result.append({**data, 'final_amount': final_amount})
    return sorted(result, key=lambda row: row['shareholder_name'])


def _validate_reconciliation(total, rows):
    distributed = money(sum((row['final_amount'] for row in rows), Decimal('0')))
    variance = money(total - distributed)
    if abs(variance) > RECONCILIATION_TOLERANCE:
        raise ValueError(
            f'Distribution total {distributed} does not reconcile with company P/L {total} '
            f'(variance {variance}).'
        )
    return distributed, variance


def preview_period_distribution(total_profit_loss, as_of_date):
    total = money(total_profit_loss)
    rows = _build_calculation_rows(total, as_of_date)
    distributed, variance = _validate_reconciliation(total, rows)
    return {
        'company_total': float(total),
        'distributed_total': float(distributed),
        'variance': float(variance),
        'is_profit': total >= 0,
        'shareholders': [
            {
                'name': row['shareholder_name'],
                'ownership_percent': float(row['ownership_percent']),
                'base_share': float(row['base_share']),
                'arrangement_deduction': float(row['arrangement_deduction']),
                'arrangement_received': float(row['arrangement_received']),
                'manual_adjustment': float(row['manual_adjustment']),
                'final_amount': float(row['final_amount']),
            }
            for row in rows
        ],
    }


def calculate_period(period: MonthlyPeriod):
    if period.is_locked:
        raise ValueError('Approved periods cannot be recalculated.')

    as_of_date = period.as_of_date
    total = money(period.total_profit_loss)
    adjustments = ManualAdjustment.query.filter_by(period_id=period.id).all()
    rows = _build_calculation_rows(total, as_of_date, adjustments=adjustments)
    _validate_reconciliation(total, rows)

    ShareholderCalculation.query.filter_by(period_id=period.id).delete()

    for data in rows:
        calc = ShareholderCalculation(
            period_id=period.id,
            shareholder_id=data['shareholder_id'],
            ownership_percent=data['ownership_percent'],
            base_share=data['base_share'],
            arrangement_deduction=data['arrangement_deduction'],
            arrangement_received=data['arrangement_received'],
            manual_adjustment=data['manual_adjustment'],
            final_amount=data['final_amount'],
        )
        db.session.add(calc)

    period.calculated_at = datetime.utcnow()
    db.session.commit()
    return period.calculations.all()


def approve_period(period: MonthlyPeriod, user):
    if period.status != MonthlyPeriod.STATUS_REVIEW:
        raise ValueError('Submit the period for review before approval.')
    if not period.calculations.count():
        raise ValueError('Calculate the period before approval.')

    period.status = MonthlyPeriod.STATUS_APPROVED
    period.approved_at = datetime.utcnow()
    period.approved_by_id = user.id
    db.session.commit()

    # Certificates are always generated on approval (independent of email settings).
    from apps.services.certificate_service import issue_period_certificates

    issue_period_certificates(period)
    return period


def submit_for_review(period: MonthlyPeriod):
    if period.status != MonthlyPeriod.STATUS_DRAFT:
        raise ValueError('Only draft periods can be submitted for review.')
    if not period.calculations.count():
        raise ValueError('Calculate the period before submitting for review.')

    period.status = MonthlyPeriod.STATUS_REVIEW
    db.session.commit()
    return period


def reopen_for_correction(period: MonthlyPeriod, reason: str):
    if period.status != MonthlyPeriod.STATUS_APPROVED:
        raise ValueError('Only approved periods can be reopened for correction.')

    from apps.models.certificate import ShareholderCertificate

    period.status = MonthlyPeriod.STATUS_REVIEW
    period.approved_at = None
    period.approved_by_id = None
    period.reports_sent_at = None

    ShareholderCertificate.query.filter_by(period_id=period.id).update(
        {ShareholderCertificate.email_status: 'pending', ShareholderCertificate.emailed_at: None},
        synchronize_session=False,
    )
    db.session.commit()
    return period, reason.strip()


def get_ytd_totals(shareholder_id, year, through_month):
    from sqlalchemy import func

    totals = (
        db.session.query(func.coalesce(func.sum(ShareholderCalculation.final_amount), 0))
        .join(MonthlyPeriod)
        .filter(
            ShareholderCalculation.shareholder_id == shareholder_id,
            MonthlyPeriod.year == year,
            MonthlyPeriod.month <= through_month,
            MonthlyPeriod.status == MonthlyPeriod.STATUS_APPROVED,
        )
        .scalar()
    )
    return money(totals or 0)
