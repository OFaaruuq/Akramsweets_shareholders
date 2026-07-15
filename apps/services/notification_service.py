"""In-app and transactional notification helpers for all modules."""

from __future__ import annotations

import logging

from apps.models.settings import SystemSetting
from apps.services.display_settings_service import money_label

logger = logging.getLogger(__name__)


def notification_flag(key, default=True):
    """Read a SystemSetting boolean used for notification preferences."""
    raw = SystemSetting.get(key)
    if raw is None or str(raw).strip() == '':
        return default
    return str(raw).strip().lower() in ('1', 'true', 'yes', 'on')


def send_sms_notification(phone, message):
    """
    SMS/WhatsApp delivery stub (BRD §12 future channel).

    No SMS provider is wired yet — messages are logged only.
    """
    if not phone:
        return {'sent': False, 'mode': 'skipped', 'reason': 'no phone number'}

    logger.info('SMS/WhatsApp stub (provider not configured) to %s: %s', phone, message[:120])
    return {
        'sent': False,
        'mode': 'stub',
        'recipient': phone,
        'reason': 'sms_provider_not_configured',
    }


def notify_shareholder(report_data, email_result, sms_enabled):
    """Record / fan-out notifications after a shareholder email attempt."""
    results = {'email': email_result}

    company = report_data.get('company_name') or 'Company'
    period_label = report_data.get('period_label') or 'period'
    if sms_enabled and report_data.get('shareholder_phone'):
        amount_text = money_label(
            report_data.get('final_amount') or 0,
            report_data.get('currency_symbol'),
        )
        sms_body = (
            f'{company} report {period_label}: '
            f'final amount {amount_text}. '
            f'Certificate & full details sent by email.'
        )
        results['sms'] = send_sms_notification(report_data.get('shareholder_phone'), sms_body)

    if email_result.get('sent'):
        logger.info(
            'Shareholder %s notified by email (%s)',
            report_data.get('shareholder_name'),
            email_result.get('recipient'),
        )
    elif email_result.get('mode') == 'log':
        logger.info(
            'Shareholder %s notification logged only — configure SMTP in Settings → System',
            report_data.get('shareholder_name'),
        )

    return results


def notify_management_period_submitted(period, submitted_by=None):
    """Email owners/admins when finance submits a period for review."""
    if not notification_flag('notify_management_on_review', True):
        return {'sent': False, 'mode': 'disabled'}

    from apps.models.user import User
    from apps.services.audit_service import log_action
    from apps.services.email_service import send_system_notice

    recipients = (
        User.query.filter(User.role.in_([User.ROLE_OWNER, User.ROLE_ADMIN]))
        .filter_by(is_active=True)
        .all()
    )
    actor = getattr(submitted_by, 'full_name', None) or 'Finance'
    subject = f'Period ready for approval — {period.period_label}'
    intro = (
        f'{actor} submitted {period.period_label} for management review. '
        f'Company total: {money_label(period.total_profit_loss)}.'
    )
    results = []
    for user in recipients:
        result = send_system_notice(
            user.email,
            subject,
            title='Period awaiting approval',
            paragraphs=[
                f'Hello {user.full_name},',
                intro,
                'Open Monthly Periods to review calculations, arrangements, and approve when ready.',
            ],
            cta_label='Open period',
            cta_endpoint='periods.detail_period',
            cta_kwargs={'period_id': period.id},
        )
        results.append({'user': user.email, **result})

    log_action(
        'notify',
        'management',
        period.id,
        f'Review alert emailed for {period.period_label} ({len(results)} recipient(s))',
        user=submitted_by,
    )
    return {'ok': True, 'results': results}


def notify_portal_credentials(user, shareholder, password, created=True):
    """Email shareholder portal login details after access is granted/updated."""
    if not notification_flag('email_portal_credentials', True):
        return {'sent': False, 'mode': 'disabled'}

    from apps.services.email_service import send_system_notice

    action = 'created' if created else 'updated'
    return send_system_notice(
        user.email,
        f'Your shareholder portal access was {action}',
        title=f'Portal access {action}',
        paragraphs=[
            f'Hello {user.full_name},',
            f'Portal access for {shareholder.name} has been {action}.',
            f'Sign-in email: {user.email}',
            f'Temporary password: {password}',
            'Please sign in and change your password after your first login.',
        ],
        cta_label='Open portal login',
        cta_endpoint='auth.login',
    )


def notify_staff_invite(user, password, created_by=None):
    """Email a new staff user their account details."""
    if not notification_flag('email_staff_invite', True):
        return {'sent': False, 'mode': 'disabled'}

    from apps.services.email_service import send_system_notice

    role_label = (user.role or 'staff').replace('_', ' ').title()
    return send_system_notice(
        user.email,
        'Your staff account is ready',
        title='Staff account created',
        paragraphs=[
            f'Hello {user.full_name},',
            f'A {role_label} account was created for you'
            + (f' by {created_by.full_name}.' if created_by else '.'),
            f'Sign-in email: {user.email}',
            f'Temporary password: {password}',
            'Sign in and change your password as soon as possible.',
        ],
        cta_label='Sign in',
        cta_endpoint='auth.login',
    )


def notify_password_changed(user):
    """Confirm a successful password change."""
    if not notification_flag('email_password_change', True):
        return {'sent': False, 'mode': 'disabled'}

    from apps.services.email_service import send_system_notice

    return send_system_notice(
        user.email,
        'Your password was changed',
        title='Password updated',
        paragraphs=[
            f'Hello {user.full_name},',
            'Your account password was changed successfully.',
            'If you did not make this change, contact management immediately.',
        ],
        cta_label='Open account',
        cta_endpoint='portal.profile' if user.is_shareholder() else 'pages.dashboard',
    )
