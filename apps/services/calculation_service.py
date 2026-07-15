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
    """Build per-shareholder rows from the shareholders' profit pool (not full Net Profit)."""
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
        bonus_rate = Decimal(arrangement.bonus_percent) / Decimal('100')
        recipient_id = arrangement.recipient_shareholder_id
        if recipient_id not in rows:
            continue
        source_ids = arrangement.contributing_shareholder_ids(rows.keys())
        if not source_ids:
            continue

        for shareholder_id in source_ids:
            if shareholder_id not in rows:
                continue
            deduction = money(rows[shareholder_id]['base_share'] * bonus_rate)
            rows[shareholder_id]['arrangement_deduction'] -= deduction
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
    """Reconcile distributed shareholder amounts to the shareholders' pool."""
    distributed = money(sum((row['final_amount'] for row in rows), Decimal('0')))
    variance = money(total - distributed)
    if abs(variance) > RECONCILIATION_TOLERANCE:
        raise ValueError(
            f'Distribution total {distributed} does not reconcile with shareholders\' pool {total} '
            f'(variance {variance}).'
        )
    return distributed, variance


def preview_period_distribution(total_profit_loss, as_of_date):
    from apps.models.shareholder import Shareholder
    from apps.services.mudarabah_service import split_net_profit
    from apps.services.share_value_service import capital_for_ownership, shares_for_ownership

    company_net = money(total_profit_loss)
    pool, partner_share, shareholder_percent = split_net_profit(company_net)
    rows = _build_calculation_rows(pool, as_of_date)
    distributed, variance = _validate_reconciliation(pool, rows)

    partner_percent = money(Decimal('100') - Decimal(shareholder_percent))
    shareholders_out = []
    for row in rows:
        sh = Shareholder.query.get(row['shareholder_id'])
        ownership = row['ownership_percent']
        registered_shares = float(sh.share_count or 0) if sh else 0.0
        registered_investment = float(sh.investment_amount or 0) if sh else 0.0
        derived_shares = shares_for_ownership(ownership)
        derived_capital = capital_for_ownership(ownership)
        arrangement_net = money(row['arrangement_deduction'] + row['arrangement_received'])
        shareholders_out.append({
            'id': row['shareholder_id'],
            'name': row['shareholder_name'],
            'ownership_percent': float(ownership),
            'investment': registered_investment or (
                float(derived_capital) if derived_capital is not None else 0.0
            ),
            'shares': registered_shares or (
                float(derived_shares) if derived_shares is not None else 0.0
            ),
            'base_share': float(row['base_share']),
            'original_profit': float(row['base_share']),
            'arrangement_deduction': float(row['arrangement_deduction']),
            'arrangement_received': float(row['arrangement_received']),
            'arrangement_adjustment': float(arrangement_net),
            'manual_adjustment': float(row['manual_adjustment']),
            'final_amount': float(row['final_amount']),
            'profit': float(row['final_amount']),
        })

    return {
        'company_total': float(company_net),
        'shareholders_pool': float(pool),
        'managing_partner_share': float(partner_share),
        'mudarabah_shareholder_percent': float(shareholder_percent),
        'mudarabah_partner_percent': float(partner_percent),
        'distributed_total': float(distributed),
        'remaining_balance': float(variance),
        'variance': float(variance),
        'is_profit': company_net >= 0,
        'formula': {
            'net_profit': float(company_net),
            'shareholder_percent': float(shareholder_percent),
            'partner_percent': float(partner_percent),
            'shareholders_pool': float(pool),
            'akram_share': float(partner_share),
            'total_distributed': float(distributed),
            'remaining_balance': float(variance),
        },
        'shareholders': shareholders_out,
    }


def calculate_period(period: MonthlyPeriod):
    if period.is_locked:
        raise ValueError('Approved periods cannot be recalculated.')
    if period.payment_completed:
        raise ValueError('Payment-completed periods cannot be recalculated.')

    from apps.services.audit_service import log_action
    from apps.services.mudarabah_service import split_net_profit

    as_of_date = period.as_of_date
    company_net = money(period.total_profit_loss)
    pool, partner_share, shareholder_percent = split_net_profit(company_net)
    period.shareholders_pool = pool
    period.managing_partner_share = partner_share
    period.mudarabah_shareholder_percent = shareholder_percent

    adjustments = ManualAdjustment.query.filter_by(period_id=period.id).all()
    rows = _build_calculation_rows(pool, as_of_date, adjustments=adjustments)
    _validate_reconciliation(pool, rows)

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

    log_action(
        'calculate',
        'monthly_period',
        period.id,
        (
            f'{period.period_label}: Net {company_net} → pool {pool} '
            f'({shareholder_percent}%) / partner {partner_share}; '
            f'{len(rows)} shareholder rows'
        ),
    )
    return period.calculations.all()


def approve_period(period: MonthlyPeriod, user):
    if period.status != MonthlyPeriod.STATUS_REVIEW:
        raise ValueError('Submit the period for review before approval.')
    if not period.calculations.count():
        raise ValueError('Calculate the period before approval.')
    _assert_ownership_valid(period.as_of_date)

    period.status = MonthlyPeriod.STATUS_APPROVED
    period.approved_at = datetime.utcnow()
    period.approved_by_id = user.id
    period.rejection_reason = None
    period.rejected_at = None
    period.rejected_by_id = None
    if not period.payment_status:
        period.payment_status = MonthlyPeriod.PAYMENT_PENDING
    db.session.commit()

    from apps.services.audit_service import log_action
    from apps.services.certificate_service import issue_period_certificates

    issue_period_certificates(period)
    log_action('approve', 'monthly_period', period.id, f'{period.period_label} locked')
    return period


def submit_for_review(period: MonthlyPeriod, user=None):
    if period.status != MonthlyPeriod.STATUS_DRAFT:
        raise ValueError('Only draft periods can be submitted for review.')
    if not period.calculations.count():
        raise ValueError('Calculate the period before submitting for review.')
    _assert_ownership_valid(period.as_of_date)

    period.status = MonthlyPeriod.STATUS_REVIEW
    period.submitted_for_review_at = datetime.utcnow()
    period.submitted_for_review_by_id = user.id if user else None
    period.rejection_reason = None
    period.rejected_at = None
    period.rejected_by_id = None
    db.session.commit()

    from apps.services.audit_service import log_action

    log_action(
        'submit_review',
        'monthly_period',
        period.id,
        f'{period.period_label} submitted for management approval',
    )
    return period


def mark_payment_completed(period: MonthlyPeriod, user=None):
    if period.status != MonthlyPeriod.STATUS_APPROVED:
        raise ValueError('Only approved (locked) periods can be marked payment completed.')
    period.payment_status = MonthlyPeriod.PAYMENT_COMPLETED
    period.payment_completed_at = datetime.utcnow()
    period.payment_completed_by_id = user.id if user else None
    db.session.commit()

    from apps.services.audit_service import log_action

    log_action('payment_completed', 'monthly_period', period.id, period.period_label)
    return period


def reopen_for_correction(period: MonthlyPeriod, reason: str, user=None):
    """
    Unlock an approved period for correction.

    Returns the period to **draft** so finance must edit and re-submit for review.
    """
    if period.status != MonthlyPeriod.STATUS_APPROVED:
        raise ValueError('Only approved periods can be reopened for correction.')
    if period.payment_status == MonthlyPeriod.PAYMENT_COMPLETED:
        raise ValueError('Payment-completed periods cannot be reopened. Contact Super Admin.')

    notes = (reason or '').strip()
    if len(notes) < 10:
        raise ValueError('A detailed reason is required to reopen an approved period.')

    from apps.models.certificate import ShareholderCertificate
    from apps.services.audit_service import log_action

    period.status = MonthlyPeriod.STATUS_DRAFT
    period.approved_at = None
    period.approved_by_id = None
    period.reports_sent_at = None
    period.submitted_for_review_at = None
    period.submitted_for_review_by_id = None
    period.payment_status = MonthlyPeriod.PAYMENT_PENDING
    period.payment_completed_at = None
    period.payment_completed_by_id = None
    period.rejection_reason = f'Reopened for correction: {notes}'
    period.rejected_at = datetime.utcnow()
    period.rejected_by_id = user.id if user else None

    ShareholderCertificate.query.filter_by(period_id=period.id).update(
        {ShareholderCertificate.email_status: 'pending', ShareholderCertificate.emailed_at: None},
        synchronize_session=False,
    )
    db.session.commit()
    log_action('reopen', 'monthly_period', period.id, notes)
    return period, notes


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
