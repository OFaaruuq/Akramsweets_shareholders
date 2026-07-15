"""Approval workflow helpers — pending inbox, period reject/return, notifications."""

from __future__ import annotations

from datetime import datetime

from apps import db
from apps.models.period import MonthlyPeriod
from apps.models.shareholder import CapitalWithdrawalRequest
from apps.services.audit_service import log_action


def _waiting_days(since):
    if not since:
        return None
    return max(0, (datetime.utcnow() - since).days)


def get_pending_approvals():
    """
    Unified queue for staff:

    - needs_decision: periods in review + pending withdrawals (action required)
    - tracking: approved withdrawals still awaiting capital return
    """
    now = datetime.utcnow()

    periods = (
        MonthlyPeriod.query.filter_by(status=MonthlyPeriod.STATUS_REVIEW)
        .order_by(MonthlyPeriod.year.desc(), MonthlyPeriod.month.desc())
        .all()
    )
    pending_withdrawals = (
        CapitalWithdrawalRequest.query.filter_by(status=CapitalWithdrawalRequest.STATUS_PENDING)
        .order_by(CapitalWithdrawalRequest.requested_at.asc())
        .all()
    )
    approved_withdrawals = (
        CapitalWithdrawalRequest.query.filter_by(status=CapitalWithdrawalRequest.STATUS_APPROVED)
        .order_by(CapitalWithdrawalRequest.deadline_at.asc())
        .all()
    )

    needs_decision = []
    for period in periods:
        submitted_at = getattr(period, 'submitted_for_review_at', None) or period.updated_at
        needs_decision.append({
            'kind': 'period',
            'id': period.id,
            'title': f'Period {period.period_label}',
            'subtitle': (
                f'Net Profit {period.total_profit_loss} · '
                f"Pool {getattr(period, 'shareholders_pool', 0) or 0}"
            ),
            'amount': period.total_profit_loss,
            'pool': getattr(period, 'shareholders_pool', None),
            'status': period.status,
            'priority': 'high',
            'bucket': 'decision',
            'submitted_at': submitted_at,
            'waiting_days': _waiting_days(submitted_at),
            'submitted_by': (
                period.submitted_for_review_by.full_name
                if getattr(period, 'submitted_for_review_by', None)
                else (period.created_by.full_name if period.created_by else None)
            ),
            'deadline_at': None,
            'is_overdue': False,
            'url_endpoint': 'periods.detail_period',
            'url_kwargs': {'period_id': period.id},
            'action_label_mgmt': 'Review & approve',
            'action_label_staff': 'View period',
        })

    for req in pending_withdrawals:
        needs_decision.append({
            'kind': 'withdrawal',
            'id': req.id,
            'title': f'Capital withdrawal — {req.shareholder.name}',
            'subtitle': f'Requested return of capital',
            'amount': req.amount,
            'pool': None,
            'status': req.status,
            'priority': 'high',
            'bucket': 'decision',
            'submitted_at': req.requested_at,
            'waiting_days': _waiting_days(req.requested_at),
            'submitted_by': req.shareholder.name,
            'deadline_at': req.deadline_at,
            'is_overdue': False,
            'url_endpoint': 'shareholders.review_withdrawal',
            'url_kwargs': {'request_id': req.id},
            'action_label_mgmt': 'Approve / reject',
            'action_label_staff': 'View request',
        })

    needs_decision.sort(
        key=lambda row: (
            0 if row['kind'] == 'period' else 1,
            row['submitted_at'] or datetime.min,
        )
    )

    tracking = []
    overdue_count = 0
    for req in approved_withdrawals:
        is_overdue = bool(req.deadline_at and req.deadline_at < now)
        if is_overdue:
            overdue_count += 1
        tracking.append({
            'kind': 'withdrawal',
            'id': req.id,
            'title': f'Capital return due — {req.shareholder.name}',
            'subtitle': 'Approved — awaiting capital repayment',
            'amount': req.amount,
            'pool': None,
            'status': req.status,
            'priority': 'high' if is_overdue else 'normal',
            'bucket': 'tracking',
            'submitted_at': req.reviewed_at or req.requested_at,
            'waiting_days': _waiting_days(req.reviewed_at or req.requested_at),
            'submitted_by': req.shareholder.name,
            'deadline_at': req.deadline_at,
            'is_overdue': is_overdue,
            'url_endpoint': 'shareholders.review_withdrawal',
            'url_kwargs': {'request_id': req.id},
            'action_label_mgmt': 'Mark returned',
            'action_label_staff': 'View request',
        })

    tracking.sort(
        key=lambda row: (
            0 if row['is_overdue'] else 1,
            row['deadline_at'] or datetime.max,
        )
    )

    return {
        'periods': periods,
        'pending_withdrawals': pending_withdrawals,
        'approved_withdrawals': approved_withdrawals,
        'needs_decision': needs_decision,
        'tracking': tracking,
        # Back-compat for older templates / callers
        'approval_items': needs_decision + tracking,
        'withdrawals': pending_withdrawals + approved_withdrawals,
        'period_count': len(periods),
        'pending_withdrawal_count': len(pending_withdrawals),
        'tracking_count': len(approved_withdrawals),
        'overdue_count': overdue_count,
        # Legacy key was misleading (included approved). Keep for dashboard until updated.
        'withdrawal_count': len(pending_withdrawals),
        'pending_count': len(periods) + len(pending_withdrawals),
        'total_open': len(periods) + len(pending_withdrawals) + len(approved_withdrawals),
    }


def reject_period(period: MonthlyPeriod, user, reason: str):
    """Return a period in review back to draft with a required reason."""
    if period.status != MonthlyPeriod.STATUS_REVIEW:
        raise ValueError('Only periods awaiting review can be rejected.')
    notes = (reason or '').strip()
    if len(notes) < 5:
        raise ValueError('A rejection reason is required (at least 5 characters).')

    period.status = MonthlyPeriod.STATUS_DRAFT
    period.rejection_reason = notes
    period.rejected_at = datetime.utcnow()
    period.rejected_by_id = user.id
    period.submitted_for_review_at = None
    period.submitted_for_review_by_id = None
    db.session.commit()
    log_action(
        'reject',
        'monthly_period',
        period.id,
        f'{period.period_label}: {notes}',
        user=user,
    )
    return period
