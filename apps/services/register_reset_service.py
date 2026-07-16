"""Dangerous reset: wipe ALL shareholder-related data for a clean re-import."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import or_

from apps import db
from apps.models.arrangement import SpecialArrangement, arrangement_source_shareholders
from apps.models.audit import AuditLog
from apps.models.certificate import ShareholderCertificate
from apps.models.login_otp import LoginOTP
from apps.models.period import ManualAdjustment, MonthlyPeriod, ShareholderCalculation
from apps.models.shareholder import CapitalWithdrawalRequest, OwnershipRecord, Shareholder
from apps.models.todo import TodoDismissal
from apps.models.user import User
from apps.services.share_value_service import DEFAULT_SHARE_VALUE, save_share_settings

CONFIRM_PHRASE = 'RESET SHAREHOLDERS'


def register_counts():
    """Snapshot used by the confirmation UI."""
    portal_q = User.query.filter(
        or_(
            User.shareholder_id.isnot(None),
            User.role == User.ROLE_SHAREHOLDER,
        )
    )
    return {
        'shareholders': Shareholder.query.count(),
        'active_shareholders': Shareholder.query.filter_by(is_active=True).count(),
        'ownership_records': OwnershipRecord.query.count(),
        'calculations': ShareholderCalculation.query.count(),
        'certificates': ShareholderCertificate.query.count(),
        'withdrawals': CapitalWithdrawalRequest.query.count(),
        'arrangements': SpecialArrangement.query.count(),
        'periods': MonthlyPeriod.query.count(),
        'portal_users': portal_q.count(),
        'confirm_phrase': CONFIRM_PHRASE,
    }


def purge_all_shareholders_and_assets(*, actor=None, reset_capital_settings=True, wipe_periods=True):
    """
    Delete everything related to shareholders:

    - Shareholders, ownership, capital withdrawals
    - Special arrangements
    - Certificates, calculations, manual adjustments
    - Monthly periods (optional, default on — distribution history)
    - All portal / role=shareholder user accounts + OTPs
    - Shareholder-related audit / todo dismissals
    - Capital register settings (shares total, Murabaha assets → 0)

    Keeps staff users (owner/admin/finance) and system settings other than capital register.
    """
    counts_before = register_counts()

    # 1) Period line-items
    cert_deleted = ShareholderCertificate.query.delete(synchronize_session=False)
    calc_deleted = ShareholderCalculation.query.delete(synchronize_session=False)
    adj_deleted = ManualAdjustment.query.delete(synchronize_session=False)

    # 2) Withdrawals
    wd_deleted = CapitalWithdrawalRequest.query.delete(synchronize_session=False)

    # 3) Arrangements
    db.session.execute(arrangement_source_shareholders.delete())
    arr_deleted = SpecialArrangement.query.delete(synchronize_session=False)

    # 4) Ownership
    own_deleted = OwnershipRecord.query.delete(synchronize_session=False)

    # 5) Monthly periods (profit distribution history for old register)
    periods_deleted = 0
    if wipe_periods:
        periods_deleted = MonthlyPeriod.query.delete(synchronize_session=False)

    # 6) Portal / shareholder-role users
    portal_users = User.query.filter(
        or_(
            User.shareholder_id.isnot(None),
            User.role == User.ROLE_SHAREHOLDER,
        )
    ).all()
    portal_deleted = 0
    for user in portal_users:
        # Never delete the acting super-admin mid-request
        if actor is not None and getattr(actor, 'id', None) == user.id:
            user.shareholder_id = None
            if user.role == User.ROLE_SHAREHOLDER:
                user.role = User.ROLE_FINANCE
            continue
        LoginOTP.query.filter_by(user_id=user.id).delete(synchronize_session=False)
        db.session.delete(user)
        portal_deleted += 1

    User.query.filter(User.shareholder_id.isnot(None)).update(
        {User.shareholder_id: None},
        synchronize_session=False,
    )

    # 7) Shareholders
    sh_deleted = Shareholder.query.delete(synchronize_session=False)

    # 8) Audit / todos that reference shareholder entities
    audit_deleted = AuditLog.query.filter(
        AuditLog.entity_type.in_([
            'shareholder',
            'shareholder_capital',
            'ownership',
            'arrangement',
            'special_arrangement',
            'certificate',
            'capital_withdrawal',
            'withdrawal',
            'monthly_period',
            'period',
        ])
    ).delete(synchronize_session=False)

    todo_deleted = TodoDismissal.query.filter(
        or_(
            TodoDismissal.source_key.ilike('%shareholder%'),
            TodoDismissal.source_key.ilike('%withdrawal%'),
            TodoDismissal.source_key.ilike('%period%'),
            TodoDismissal.source_key.ilike('%arrangement%'),
            TodoDismissal.source_key.ilike('%certificate%'),
        )
    ).delete(synchronize_session=False)

    if reset_capital_settings:
        save_share_settings(
            share_value=DEFAULT_SHARE_VALUE,
            total_company_shares=None,
            company_owned_assets=Decimal('0'),
        )

    db.session.commit()

    from apps.services.audit_service import log_action

    log_action(
        'purge',
        'shareholder_capital',
        None,
        (
            f'FULL shareholder purge: {sh_deleted} shareholders, '
            f'{periods_deleted} periods, {calc_deleted} calculations, '
            f'{cert_deleted} certificates, {arr_deleted} arrangements, '
            f'{portal_deleted} portal users'
        ),
        user=actor,
    )

    return {
        'ok': True,
        'before': counts_before,
        'deleted': {
            'shareholders': sh_deleted,
            'ownership_records': own_deleted,
            'calculations': calc_deleted,
            'certificates': cert_deleted,
            'adjustments': adj_deleted,
            'withdrawals': wd_deleted,
            'arrangements': arr_deleted,
            'periods': periods_deleted,
            'portal_users': portal_deleted,
            'audit_logs': audit_deleted,
            'todo_dismissals': todo_deleted,
        },
        'company_owned_assets_reset': reset_capital_settings,
        'share_value_reset_to': str(DEFAULT_SHARE_VALUE) if reset_capital_settings else None,
    }
