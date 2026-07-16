"""Dangerous reset: wipe all shareholders and capital-register assets for a clean re-import."""

from __future__ import annotations

from decimal import Decimal

from apps import db
from apps.models.arrangement import SpecialArrangement, arrangement_source_shareholders
from apps.models.certificate import ShareholderCertificate
from apps.models.login_otp import LoginOTP
from apps.models.period import ManualAdjustment, ShareholderCalculation
from apps.models.shareholder import CapitalWithdrawalRequest, OwnershipRecord, Shareholder
from apps.models.user import User
from apps.services.share_value_service import DEFAULT_SHARE_VALUE, save_share_settings

CONFIRM_PHRASE = 'RESET SHAREHOLDERS'


def register_counts():
    """Snapshot used by the confirmation UI."""
    return {
        'shareholders': Shareholder.query.count(),
        'active_shareholders': Shareholder.query.filter_by(is_active=True).count(),
        'ownership_records': OwnershipRecord.query.count(),
        'calculations': ShareholderCalculation.query.count(),
        'certificates': ShareholderCertificate.query.count(),
        'withdrawals': CapitalWithdrawalRequest.query.count(),
        'arrangements': SpecialArrangement.query.count(),
        'portal_users': User.query.filter(User.shareholder_id.isnot(None)).count(),
        'confirm_phrase': CONFIRM_PHRASE,
    }


def purge_all_shareholders_and_assets(*, actor=None, reset_capital_settings=True):
    """
    Delete every shareholder and dependent capital/distribution rows.

    Keeps staff users and monthly period headers, but clears per-shareholder
    calculations, certificates, arrangements, withdrawals, and portal accounts.
    """
    counts_before = register_counts()

    # 1) Period line-items tied to shareholders
    cert_deleted = ShareholderCertificate.query.delete(synchronize_session=False)
    calc_deleted = ShareholderCalculation.query.delete(synchronize_session=False)
    adj_deleted = ManualAdjustment.query.delete(synchronize_session=False)

    # 2) Withdrawals
    wd_deleted = CapitalWithdrawalRequest.query.delete(synchronize_session=False)

    # 3) Arrangements (M2M sources first, then rows)
    db.session.execute(arrangement_source_shareholders.delete())
    arr_deleted = SpecialArrangement.query.delete(synchronize_session=False)

    # 4) Ownership
    own_deleted = OwnershipRecord.query.delete(synchronize_session=False)

    # 5) Portal users linked to shareholders
    portal_users = User.query.filter(User.shareholder_id.isnot(None)).all()
    portal_deleted = 0
    for user in portal_users:
        LoginOTP.query.filter_by(user_id=user.id).delete(synchronize_session=False)
        db.session.delete(user)
        portal_deleted += 1

    # Clear any leftover FK pointers (safety)
    User.query.filter(User.shareholder_id.isnot(None)).update(
        {User.shareholder_id: None},
        synchronize_session=False,
    )

    # 6) Shareholders
    sh_deleted = Shareholder.query.delete(synchronize_session=False)

    if reset_capital_settings:
        # Clean slate — re-import will rewrite totals and Murabaha assets
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
            f'Purged shareholder register: {sh_deleted} shareholders, '
            f'{calc_deleted} calculations, {cert_deleted} certificates, '
            f'{arr_deleted} arrangements, {portal_deleted} portal users'
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
            'portal_users': portal_deleted,
        },
        'company_owned_assets_reset': reset_capital_settings,
        'share_value_reset_to': str(DEFAULT_SHARE_VALUE) if reset_capital_settings else None,
    }
