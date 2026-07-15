"""Approval workflow helpers — pending inbox, period reject/return, notifications."""

from __future__ import annotations

from datetime import datetime

from apps import db
from apps.models.period import MonthlyPeriod
from apps.models.shareholder import CapitalWithdrawalRequest
from apps.services.audit_service import log_action


def get_pending_approvals():
    """
    Unified queue for management: periods awaiting approval + open withdrawals.

    Returns dict with counts and ordered item list for the Approvals inbox.
    """
    periods = (
        MonthlyPeriod.query.filter_by(status=MonthlyPeriod.STATUS_REVIEW)
        .order_by(MonthlyPeriod.year.desc(), MonthlyPeriod.month.desc())
        .all()
    )
    withdrawals = (
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

    items = []
    for period in periods:
        items.append({
            'kind': 'period',
            'id': period.id,
            'title': f'Period {period.period_label}',
            'subtitle': f'Net Profit {period.total_profit_loss}',
            'status': period.status,
            'priority': 'high',
            'submitted_at': getattr(period, 'submitted_for_review_at', None) or period.updated_at,
            'submitted_by': (
                period.submitted_for_review_by.full_name
                if getattr(period, 'submitted_for_review_by', None)
                else (period.created_by.full_name if period.created_by else None)
            ),
            'url_endpoint': 'periods.detail_period',
            'url_kwargs': {'period_id': period.id},
        })
    for req in withdrawals:
        items.append({
            'kind': 'withdrawal',
            'id': req.id,
            'title': f'Capital withdrawal — {req.shareholder.name}',
            'subtitle': f'Amount {req.amount} · due {req.deadline_at.date() if req.deadline_at else "—"}',
            'status': req.status,
            'priority': 'high' if req.status == CapitalWithdrawalRequest.STATUS_PENDING else 'normal',
            'submitted_at': req.requested_at,
            'submitted_by': req.shareholder.name,
            'url_endpoint': 'shareholders.review_withdrawal',
            'url_kwargs': {'request_id': req.id},
        })

    items.sort(
        key=lambda row: (
            0 if row['priority'] == 'high' else 1,
            row['submitted_at'] or datetime.min,
        )
    )

    return {
        'periods': periods,
        'withdrawals': withdrawals,
        'approval_items': items,
        'period_count': len(periods),
        'withdrawal_count': len(withdrawals),
        'pending_count': len(periods) + sum(
            1 for w in withdrawals if w.status == CapitalWithdrawalRequest.STATUS_PENDING
        ),
        'total_open': len(periods) + len(withdrawals),
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
