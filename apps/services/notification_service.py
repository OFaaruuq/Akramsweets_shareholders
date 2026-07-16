"""In-app and transactional notification helpers for all modules."""

from __future__ import annotations

import logging

from apps.models.settings import SystemSetting
from apps.services.display_settings_service import money_label
from apps.services.twilio_whatsapp_service import (
    resolve_user_whatsapp_phone,
    send_whatsapp_message,
)

logger = logging.getLogger(__name__)


def notification_flag(key, default=True):
    """Read a SystemSetting boolean used for notification preferences."""
    raw = SystemSetting.get(key)
    if raw is None or str(raw).strip() == '':
        return default
    return str(raw).strip().lower() in ('1', 'true', 'yes', 'on')


def whatsapp_notifications_enabled():
    """Master switch — stored as sms_notifications_enabled for backwards compatibility."""
    return notification_flag('sms_notifications_enabled', False)


def send_sms_notification(phone, message):
    """
    WhatsApp delivery via Twilio (legacy name kept for call sites / BRD §12).

    When Twilio is not configured, messages are logged only (stub mode).
    """
    return send_whatsapp_message(phone, message)


def _maybe_whatsapp(phone, message, *, enabled=None):
    if enabled is None:
        enabled = whatsapp_notifications_enabled()
    if not enabled:
        return {'sent': False, 'mode': 'disabled', 'channel': 'whatsapp'}
    if not phone:
        return {'sent': False, 'mode': 'skipped', 'channel': 'whatsapp', 'reason': 'no phone number'}
    return send_whatsapp_message(phone, message)


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
            f'{company}: {period_label} report ready. '
            f'Your final amount is {amount_text}. '
            f'Certificate & full details were sent by email. Sign in to the portal for more.'
        )
        results['whatsapp'] = _maybe_whatsapp(
            report_data.get('shareholder_phone'),
            sms_body,
            enabled=True,
        )
        results['sms'] = results['whatsapp']  # backwards-compatible key

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
    """Email + WhatsApp owners/admins when finance submits a period for review."""
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
    wa_body = (
        f'{period.period_label} is ready for approval. '
        f'{actor} submitted it. Company total: {money_label(period.total_profit_loss)}. '
        f'Open Monthly Periods to review.'
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
        entry = {'user': user.email, 'email': result}
        entry['whatsapp'] = _maybe_whatsapp(resolve_user_whatsapp_phone(user), wa_body)
        results.append(entry)

    log_action(
        'notify',
        'management',
        period.id,
        f'Review alert emailed for {period.period_label} ({len(results)} recipient(s))',
        user=submitted_by,
    )
    return {'ok': True, 'results': results}


def notify_finance_period_rejected(period, rejected_by=None):
    """Email + WhatsApp period creator / finance when management returns a period to draft."""
    if not notification_flag('notify_management_on_review', True):
        return {'sent': False, 'mode': 'disabled'}

    from apps.models.user import User
    from apps.services.email_service import send_system_notice

    recipients = []
    if period.submitted_for_review_by_id and period.submitted_for_review_by:
        recipients.append(period.submitted_for_review_by)
    elif period.created_by_id and period.created_by:
        recipients.append(period.created_by)
    else:
        recipients = (
            User.query.filter(User.role.in_([User.ROLE_FINANCE, User.ROLE_OWNER, User.ROLE_ADMIN]))
            .filter_by(is_active=True)
            .all()
        )

    actor = getattr(rejected_by, 'full_name', None) or 'Management'
    reason = (period.rejection_reason or '').strip() or 'No reason provided.'
    subject = f'Period returned to draft — {period.period_label}'
    wa_body = (
        f'{period.period_label} was returned to draft by {actor}. '
        f'Reason: {reason[:200]}. Update figures and submit again.'
    )
    results = []
    seen = set()
    for user in recipients:
        if not user or not user.email or user.email in seen:
            continue
        seen.add(user.email)
        result = send_system_notice(
            user.email,
            subject,
            title='Period needs changes',
            paragraphs=[
                f'Hello {user.full_name},',
                f'{actor} returned {period.period_label} to draft.',
                f'Reason: {reason}',
                'Update the figures if needed, recalculate, and submit for review again.',
            ],
            cta_label='Open period',
            cta_endpoint='periods.detail_period',
            cta_kwargs={'period_id': period.id},
        )
        entry = {'user': user.email, 'email': result}
        entry['whatsapp'] = _maybe_whatsapp(resolve_user_whatsapp_phone(user), wa_body)
        results.append(entry)
    return {'ok': True, 'results': results}


def notify_management_withdrawal_requested(request_obj, actor=None):
    """Alert owners/admins when a shareholder requests capital return."""
    from apps.models.user import User
    from apps.services.display_settings_service import money_label
    from apps.services.email_service import send_system_notice

    recipients = (
        User.query.filter(User.role.in_([User.ROLE_OWNER, User.ROLE_ADMIN]))
        .filter_by(is_active=True)
        .all()
    )
    sh_name = request_obj.shareholder.name if request_obj.shareholder else 'Shareholder'
    amount = money_label(request_obj.amount)
    subject = f'Capital withdrawal request — {sh_name}'
    wa_body = (
        f'Capital withdrawal pending: {sh_name} requested {amount}. '
        f'Review in Capital Withdrawals.'
    )
    results = []
    for user in recipients:
        result = send_system_notice(
            user.email,
            subject,
            title='Capital withdrawal pending',
            paragraphs=[
                f'Hello {user.full_name},',
                f'{sh_name} requested return of {amount}.',
                f'Reason: {(request_obj.reason or "")[:400]}',
                'Review and approve or reject in Capital Withdrawals.',
            ],
            cta_label='Review request',
            cta_endpoint='shareholders.review_withdrawal',
            cta_kwargs={'request_id': request_obj.id},
        )
        entry = {'user': user.email, 'email': result}
        entry['whatsapp'] = _maybe_whatsapp(resolve_user_whatsapp_phone(user), wa_body)
        results.append(entry)
    return {'ok': True, 'results': results}


def notify_shareholder_withdrawal_status(request_obj, status_label):
    """Notify the shareholder when their withdrawal request changes status."""
    from apps.services.display_settings_service import money_label
    from apps.services.email_service import send_system_notice

    shareholder = request_obj.shareholder
    if not shareholder:
        return {'sent': False, 'mode': 'no_shareholder'}

    amount = money_label(request_obj.amount)
    deadline = (
        request_obj.deadline_at.strftime('%Y-%m-%d')
        if request_obj.deadline_at
        else '—'
    )
    paragraphs = [
        f'Hello {shareholder.name},',
        f'Your capital withdrawal request for {amount} is now: {status_label}.',
    ]
    if request_obj.status == 'approved':
        paragraphs.append(
            f'The company has until {deadline} to return capital (up to six months from approval).'
        )
    if request_obj.review_notes:
        paragraphs.append(f'Notes: {request_obj.review_notes}')
    if request_obj.capital_return_date:
        paragraphs.append(f'Capital return date: {request_obj.capital_return_date}')

    email_result = {'sent': False, 'mode': 'no_email'}
    if shareholder.email:
        email_result = send_system_notice(
            shareholder.email,
            f'Capital withdrawal {status_label.lower()} — {amount}',
            title=f'Withdrawal {status_label}',
            paragraphs=paragraphs,
            cta_label='View in portal',
            cta_endpoint='portal.withdrawal',
        )

    wa_body = (
        f'Capital withdrawal {status_label}: {amount}. '
        f'Sign in to the shareholder portal for details.'
    )
    whatsapp_result = _maybe_whatsapp(shareholder.phone, wa_body)
    return {'email': email_result, 'whatsapp': whatsapp_result, 'sent': email_result.get('sent')}


def notify_portal_credentials(user, shareholder, password, created=True):
    """Email + WhatsApp shareholder portal login details after access is granted/updated."""
    if not notification_flag('email_portal_credentials', True):
        return {'sent': False, 'mode': 'disabled'}

    from apps.services.email_service import send_system_notice

    action = 'created' if created else 'updated'
    email_result = send_system_notice(
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
    wa_body = (
        f'Portal access {action} for {shareholder.name}. '
        f'Sign-in: {user.email}. Temporary password: {password}. '
        f'Change your password after first login.'
    )
    whatsapp_result = _maybe_whatsapp(shareholder.phone, wa_body)
    return {'email': email_result, 'whatsapp': whatsapp_result, 'sent': email_result.get('sent')}


def notify_staff_invite(user, password, created_by=None):
    """Email + WhatsApp a new staff user their account details."""
    if not notification_flag('email_staff_invite', True):
        return {'sent': False, 'mode': 'disabled'}

    from apps.services.email_service import send_system_notice

    role_label = (user.role or 'staff').replace('_', ' ').title()
    email_result = send_system_notice(
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
    wa_body = (
        f'Your {role_label} account is ready. '
        f'Sign-in: {user.email}. Temporary password: {password}.'
    )
    whatsapp_result = _maybe_whatsapp(resolve_user_whatsapp_phone(user), wa_body)
    return {'email': email_result, 'whatsapp': whatsapp_result, 'sent': email_result.get('sent')}


def notify_password_changed(user):
    """Confirm a successful password change via email + WhatsApp."""
    if not notification_flag('email_password_change', True):
        return {'sent': False, 'mode': 'disabled'}

    from apps.services.email_service import send_system_notice

    email_result = send_system_notice(
        user.email,
        'Your password was changed',
        title='Password updated',
        paragraphs=[
            f'Hello {user.full_name},',
            'Your account password was changed successfully.',
            'If you did not make this change, contact management immediately.',
        ],
        cta_label='Open account',
        cta_endpoint='auth.account',
    )
    phone = resolve_user_whatsapp_phone(user)
    if not phone and getattr(user, 'shareholder', None):
        phone = user.shareholder.phone
    wa_body = (
        f'Hello {user.full_name}: your account password was changed. '
        f'If this was not you, contact management immediately.'
    )
    whatsapp_result = _maybe_whatsapp(phone, wa_body)
    return {'email': email_result, 'whatsapp': whatsapp_result, 'sent': email_result.get('sent')}


def notify_shareholders_period_update(
    period,
    *,
    message=None,
    reason='profit_update',
    actor=None,
    respect_setting=True,
):
    """
    Email + WhatsApp every shareholder on a period with a profit / distribution update.

    Used automatically when Net Profit changes (if enabled in settings),
    and manually via “Send update to shareholders”.
    """
    if respect_setting and not notification_flag('notify_shareholders_on_profit_update', True):
        return {'ok': False, 'mode': 'disabled', 'sent': 0, 'results': []}

    from apps.services.audit_service import log_action
    from apps.services.display_settings_service import money_label
    from apps.services.email_service import send_system_notice

    calculations = list(period.calculations)
    if not calculations:
        return {'ok': False, 'mode': 'no_calculations', 'sent': 0, 'results': []}

    company_total = money_label(period.total_profit_loss)
    is_profit = (period.total_profit_loss or 0) >= 0
    result_word = 'profit' if is_profit else 'loss'
    note = (message or '').strip()
    reason_label = {
        'profit_update': 'monthly profit figures were updated',
        'manual_update': 'management sent you an update',
        'recalculate': 'the monthly distribution was recalculated',
    }.get(reason, 'there is an update on your monthly distribution')

    sms_enabled = whatsapp_notifications_enabled()
    results = []
    sent_count = 0

    for calc in calculations:
        shareholder = calc.shareholder
        if not shareholder:
            continue
        recipient = (shareholder.email or '').strip()
        your_share = money_label(calc.final_amount)
        paragraphs = [
            f'Hello {shareholder.name},',
            f'This is a notice that {reason_label} for period {period.period_label}.',
            f'Company net {result_word}: {company_total}.',
            f'Your distribution amount: {your_share}.',
        ]
        if note:
            paragraphs.append(f'Message from management: {note}')
        paragraphs.append(
            'Sign in to the shareholder portal for full details. '
            'A formal report and certificate are emailed when the period is approved '
            '(or when reports are sent again).'
        )

        email_result = send_system_notice(
            recipient,
            f'Profit update — {period.period_label}',
            title=f'Update for {period.period_label}',
            paragraphs=paragraphs,
            cta_label='Open portal',
            cta_endpoint='pages.dashboard',
        )
        entry = {
            'shareholder': shareholder.name,
            'email': email_result,
        }
        if sms_enabled and shareholder.phone:
            wa_parts = [
                f'{period.period_label} update: your share is {your_share}.',
                f'Company net {result_word}: {company_total}.',
            ]
            if note:
                wa_parts.append(f'Message: {note[:160]}')
            wa_parts.append('Details by email / portal.')
            entry['whatsapp'] = _maybe_whatsapp(
                shareholder.phone,
                ' '.join(wa_parts),
                enabled=True,
            )
            entry['sms'] = entry['whatsapp']
        if email_result.get('sent') or email_result.get('mode') == 'log':
            sent_count += 1
        results.append(entry)

    log_action(
        'notify_update',
        'monthly_period',
        period.id,
        f'{period.period_label} shareholder update ({reason}): {sent_count}/{len(results)}',
        user=actor,
    )
    return {'ok': True, 'sent': sent_count, 'total': len(results), 'results': results}
