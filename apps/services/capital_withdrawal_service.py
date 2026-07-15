"""Capital withdrawal requests — configurable return deadline from system settings."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from apps import db
from apps.models.settings import SystemSetting
from apps.models.shareholder import CapitalWithdrawalRequest
from apps.services.audit_service import log_action

MONEY = Decimal('0.01')
BOOTSTRAP_DEADLINE_DAYS = 183  # ~6 calendar months — used only until Settings is configured
SETTING_KEY = 'capital_return_deadline_days'


def get_capital_return_deadline_days():
    raw = SystemSetting.get(SETTING_KEY)
    try:
        days = int(str(raw or BOOTSTRAP_DEADLINE_DAYS).strip())
    except (TypeError, ValueError):
        days = BOOTSTRAP_DEADLINE_DAYS
    if days < 1 or days > 3650:
        return BOOTSTRAP_DEADLINE_DAYS
    return days


def get_capital_return_deadline_months_label():
    days = get_capital_return_deadline_days()
    months = round(days / 30.4375, 1)
    if abs(months - int(months)) < 0.05:
        months = int(months)
    return {
        'days': days,
        'months': months,
        'label': f'up to {months} months ({days} days)',
        'short_label': f'{months} months',
    }


def save_capital_return_deadline_days(days):
    try:
        value = int(days)
    except (TypeError, ValueError) as exc:
        raise ValueError('Capital return deadline must be a whole number of days.') from exc
    if value < 1 or value > 3650:
        raise ValueError('Capital return deadline must be between 1 and 3650 days.')
    SystemSetting.set(SETTING_KEY, str(value))


def ensure_default_withdrawal_settings():
    if not SystemSetting.get(SETTING_KEY):
        SystemSetting.set(SETTING_KEY, str(BOOTSTRAP_DEADLINE_DAYS))


def money(value):
    return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)


def _deadline_from(requested_at=None):
    base = requested_at or datetime.utcnow()
    return base + timedelta(days=get_capital_return_deadline_days())


def create_withdrawal_request(shareholder, amount, reason, user=None):
    if not shareholder or not shareholder.is_active:
        raise ValueError('Only active shareholders can request capital withdrawal.')
    amount = money(amount)
    if amount <= 0:
        raise ValueError('Withdrawal amount must be greater than zero.')
    reason = (reason or '').strip()
    if len(reason) < 3:
        raise ValueError('Please provide a reason for the withdrawal request.')

    now = datetime.utcnow()
    # Provisional deadline until approval; reset from approval date using configured days.
    request = CapitalWithdrawalRequest(
        shareholder_id=shareholder.id,
        amount=amount,
        reason=reason,
        status=CapitalWithdrawalRequest.STATUS_PENDING,
        requested_at=now,
        deadline_at=_deadline_from(now),
        created_by_id=user.id if user else None,
    )
    db.session.add(request)
    db.session.commit()
    log_action(
        'create',
        'capital_withdrawal',
        request.id,
        f'{shareholder.name}: {amount} — pending',
        user=user,
    )
    try:
        from apps.services.notification_service import notify_management_withdrawal_requested

        notify_management_withdrawal_requested(request, actor=user)
    except Exception:
        pass
    return request


def approve_withdrawal(request_id, user, review_notes=None):
    request = CapitalWithdrawalRequest.query.get_or_404(request_id)
    if request.status != CapitalWithdrawalRequest.STATUS_PENDING:
        raise ValueError('Only pending requests can be approved.')
    now = datetime.utcnow()
    request.status = CapitalWithdrawalRequest.STATUS_APPROVED
    request.reviewed_by_id = user.id
    request.reviewed_at = now
    request.review_notes = (review_notes or '').strip() or None
    request.deadline_at = _deadline_from(now)
    db.session.commit()
    meta = get_capital_return_deadline_months_label()
    log_action(
        'approve',
        'capital_withdrawal',
        request.id,
        f'Approved capital return for {request.shareholder.name} (deadline {request.deadline_at.date()}, {meta["label"]})',
        user=user,
    )
    try:
        from apps.services.notification_service import notify_shareholder_withdrawal_status

        notify_shareholder_withdrawal_status(request, 'Approved')
    except Exception:
        pass
    return request


def reject_withdrawal(request_id, user, review_notes=None):
    request = CapitalWithdrawalRequest.query.get_or_404(request_id)
    if request.status != CapitalWithdrawalRequest.STATUS_PENDING:
        raise ValueError('Only pending requests can be rejected.')
    notes = (review_notes or '').strip()
    if not notes:
        raise ValueError('Review notes are required when rejecting a request.')
    request.status = CapitalWithdrawalRequest.STATUS_REJECTED
    request.reviewed_by_id = user.id
    request.reviewed_at = datetime.utcnow()
    request.review_notes = notes
    db.session.commit()
    log_action(
        'reject',
        'capital_withdrawal',
        request.id,
        f'Rejected capital return for {request.shareholder.name}: {notes}',
        user=user,
    )
    try:
        from apps.services.notification_service import notify_shareholder_withdrawal_status

        notify_shareholder_withdrawal_status(request, 'Rejected')
    except Exception:
        pass
    return request


def complete_withdrawal(request_id, user, capital_return_date=None, review_notes=None):
    request = CapitalWithdrawalRequest.query.get_or_404(request_id)
    if request.status != CapitalWithdrawalRequest.STATUS_APPROVED:
        raise ValueError('Only approved requests can be marked completed.')
    request.status = CapitalWithdrawalRequest.STATUS_COMPLETED
    request.capital_return_date = capital_return_date or datetime.utcnow().date()
    request.reviewed_by_id = user.id
    request.reviewed_at = datetime.utcnow()
    if review_notes:
        request.review_notes = (review_notes or '').strip() or request.review_notes
    db.session.commit()
    log_action(
        'complete',
        'capital_withdrawal',
        request.id,
        f'Capital returned on {request.capital_return_date} to {request.shareholder.name}',
        user=user,
    )
    try:
        from apps.services.notification_service import notify_shareholder_withdrawal_status

        notify_shareholder_withdrawal_status(request, 'Completed')
    except Exception:
        pass
    return request


def cancel_withdrawal(request_id, user, reason=None):
    request = CapitalWithdrawalRequest.query.get_or_404(request_id)
    if request.status not in (
        CapitalWithdrawalRequest.STATUS_PENDING,
        CapitalWithdrawalRequest.STATUS_APPROVED,
    ):
        raise ValueError('Only open requests can be cancelled.')
    request.status = CapitalWithdrawalRequest.STATUS_CANCELLED
    request.reviewed_by_id = user.id
    request.reviewed_at = datetime.utcnow()
    if reason:
        request.review_notes = (reason or '').strip()
    db.session.commit()
    log_action(
        'cancel',
        'capital_withdrawal',
        request.id,
        f'Cancelled capital withdrawal for {request.shareholder.name}',
        user=user,
    )
    return request


def list_withdrawal_requests(status=None, shareholder_id=None):
    query = CapitalWithdrawalRequest.query
    if status:
        query = query.filter_by(status=status)
    if shareholder_id:
        query = query.filter_by(shareholder_id=shareholder_id)
    return query.order_by(CapitalWithdrawalRequest.requested_at.desc()).all()


def outstanding_withdrawal_requests():
    return (
        CapitalWithdrawalRequest.query.filter(
            CapitalWithdrawalRequest.status.in_(
                [
                    CapitalWithdrawalRequest.STATUS_PENDING,
                    CapitalWithdrawalRequest.STATUS_APPROVED,
                ]
            )
        )
        .order_by(CapitalWithdrawalRequest.deadline_at.asc())
        .all()
    )


def parse_amount(raw):
    try:
        return money(raw)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError('Invalid withdrawal amount.') from exc
