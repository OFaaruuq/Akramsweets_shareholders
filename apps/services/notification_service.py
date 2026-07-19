"""Dual-channel notifications: every outbound notice uses Email + WhatsApp together."""

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


def resolve_shareholder_whatsapp_phone(shareholder):
    """Shareholder phone, or phone on their linked portal user account."""
    if not shareholder:
        return None
    phone = (getattr(shareholder, 'phone', None) or '').strip()
    if phone:
        return phone
    account = getattr(shareholder, 'user_account', None)
    if account:
        return resolve_user_whatsapp_phone(account)
    return None


def _maybe_whatsapp(
    phone,
    message,
    *,
    enabled=None,
    event_key=None,
    media_urls=None,
    content_variables=None,
    user_id=None,
    shareholder_id=None,
):
    if enabled is None:
        enabled = whatsapp_notifications_enabled()
    if not enabled:
        return {'sent': False, 'mode': 'disabled', 'channel': 'whatsapp'}
    if not phone:
        return {'sent': False, 'mode': 'skipped', 'channel': 'whatsapp', 'reason': 'no phone number'}
    return send_whatsapp_message(
        phone,
        message,
        event_key=event_key,
        media_urls=media_urls,
        content_variables=content_variables,
        user_id=user_id,
        shareholder_id=shareholder_id,
    )


def channel_reached(result) -> bool:
    """True when a channel actually delivered or was logged for SMTP stub."""
    if not result:
        return False
    if result.get('sent'):
        return True
    return result.get('mode') in ('log',)


def any_channel_reached(entry: dict) -> bool:
    return channel_reached(entry.get('email')) or channel_reached(entry.get('whatsapp'))


def count_dual_results(results) -> dict:
    """Aggregate email/WhatsApp success counts from a list of dual-channel entries."""
    results = results or []
    email_sent = sum(1 for r in results if (r.get('email') or {}).get('sent'))
    email_log = sum(1 for r in results if (r.get('email') or {}).get('mode') == 'log')
    wa_sent = sum(1 for r in results if (r.get('whatsapp') or {}).get('sent'))
    wa_stub = sum(1 for r in results if (r.get('whatsapp') or {}).get('mode') == 'stub')
    reached = sum(1 for r in results if any_channel_reached(r))
    return {
        'email_sent': email_sent,
        'email_log': email_log,
        'whatsapp_sent': wa_sent,
        'whatsapp_stub': wa_stub,
        'reached': reached,
        'total': len(results),
    }


def flash_dual_summary(counts: dict, *, noun='notification') -> tuple[str, str]:
    """
    Build (message, category) for dual-channel fan-out.

    Prefer mentioning both channels when either succeeded.
    """
    email_n = counts.get('email_sent') or 0
    wa_n = counts.get('whatsapp_sent') or 0
    log_n = counts.get('email_log') or 0
    total = counts.get('total') or 0

    parts = []
    if email_n:
        parts.append(f'{email_n} email')
    if wa_n:
        parts.append(f'{wa_n} WhatsApp')
    if parts:
        return (
            f'{noun.capitalize()} sent via {" + ".join(parts)} '
            f'({counts.get("reached", 0)} of {total} recipient(s)).',
            'success',
        )
    if log_n:
        return (
            f'{noun.capitalize()} logged for {log_n} recipient(s), but SMTP is not configured. '
            'Add SMTP under Settings → System. Enable WhatsApp + Twilio for phone delivery.',
            'warning',
        )
    return (
        f'No {noun}s were delivered. Check shareholder emails/phones and delivery settings.',
        'warning',
    )


def deliver_notice(
    *,
    email=None,
    phone=None,
    subject,
    title,
    paragraphs,
    wa_body,
    cta_label=None,
    cta_endpoint=None,
    cta_kwargs=None,
    whatsapp_enabled=None,
    event_key=None,
    media_urls=None,
    content_variables=None,
    user_id=None,
    shareholder_id=None,
):
    """
    Send the same notice on Email and WhatsApp.

    Preference flags that gate a notify_* helper apply to both channels together.
    The WhatsApp master toggle still controls whether the WhatsApp leg runs.
    """
    from apps.services.email_service import send_system_notice

    email_result = {'sent': False, 'mode': 'skipped', 'reason': 'no_email'}
    if email and '@' in str(email):
        email_result = send_system_notice(
            email,
            subject,
            title=title,
            paragraphs=paragraphs,
            cta_label=cta_label,
            cta_endpoint=cta_endpoint,
            cta_kwargs=cta_kwargs,
        )

    whatsapp_result = _maybe_whatsapp(
        phone,
        wa_body,
        enabled=whatsapp_enabled,
        event_key=event_key,
        media_urls=media_urls,
        content_variables=content_variables,
        user_id=user_id,
        shareholder_id=shareholder_id,
    )
    channels = []
    if channel_reached(email_result) or email_result.get('sent'):
        channels.append('email')
    if whatsapp_result.get('sent'):
        channels.append('whatsapp')

    return {
        'email': email_result,
        'whatsapp': whatsapp_result,
        'sms': whatsapp_result,  # backwards-compatible
        'sent': bool(email_result.get('sent') or whatsapp_result.get('sent')),
        'reached': any_channel_reached({'email': email_result, 'whatsapp': whatsapp_result}),
        'channels': channels,
    }


def notify_shareholder(
    report_data,
    email_result,
    sms_enabled,
    *,
    certificate_pdf=None,
    report_pdf=None,
    shareholder_id=None,
):
    """Fan-out WhatsApp after a shareholder report email attempt (same event)."""
    results = {'email': email_result}

    company = report_data.get('company_name') or 'Company'
    period_label = report_data.get('period_label') or 'period'
    phone = report_data.get('shareholder_phone')
    if sms_enabled and phone:
        amount_text = money_label(
            report_data.get('final_amount') or 0,
            report_data.get('currency_symbol'),
        )
        wa_body = (
            f'{company}: {period_label} report ready. '
            f'Your final amount is {amount_text}. '
            f'Certificate & full details were sent by email'
            f'{"" if not certificate_pdf else " (PDF also attached on WhatsApp)"}. '
            f'Sign in to the portal for more.'
        )
        media_urls = []
        try:
            from apps.services.whatsapp_media_service import attach_pdfs_enabled, store_whatsapp_media

            if attach_pdfs_enabled():
                if certificate_pdf:
                    stored = store_whatsapp_media(
                        certificate_pdf,
                        f'certificate-{period_label}.pdf'.replace(' ', '_'),
                    )
                    if stored and stored[1].startswith('http'):
                        media_urls.append(stored[1])
                if report_pdf:
                    stored = store_whatsapp_media(
                        report_pdf,
                        f'report-{period_label}.pdf'.replace(' ', '_'),
                    )
                    if stored and stored[1].startswith('http'):
                        media_urls.append(stored[1])
        except Exception:
            logger.exception('WhatsApp PDF media prepare failed')

        results['whatsapp'] = _maybe_whatsapp(
            phone,
            wa_body,
            enabled=True,
            event_key='report',
            media_urls=media_urls or None,
            content_variables={
                '1': str(report_data.get('shareholder_name') or ''),
                '2': str(period_label),
                '3': str(amount_text),
            },
            shareholder_id=shareholder_id,
        )
        results['sms'] = results['whatsapp']

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
    if results.get('whatsapp', {}).get('sent'):
        logger.info(
            'Shareholder %s notified by WhatsApp (%s)',
            report_data.get('shareholder_name'),
            results['whatsapp'].get('recipient'),
        )

    return results


def notify_management_period_submitted(period, submitted_by=None):
    """Email + WhatsApp owners/admins when finance submits a period for review."""
    if not notification_flag('notify_management_on_review', True):
        return {'sent': False, 'mode': 'disabled'}

    from apps.models.user import User
    from apps.services.audit_service import log_action

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
        dual = deliver_notice(
            email=user.email,
            phone=resolve_user_whatsapp_phone(user),
            subject=subject,
            title='Period awaiting approval',
            paragraphs=[
                f'Hello {user.full_name},',
                intro,
                'Open Monthly Periods to review calculations, arrangements, and approve when ready.',
            ],
            wa_body=wa_body,
            cta_label='Open period',
            cta_endpoint='periods.detail_period',
            cta_kwargs={'period_id': period.id},
            event_key='review',
            content_variables={'1': user.full_name or '', '2': period.period_label, '3': intro[:200]},
            user_id=user.id,
        )
        results.append({'user': user.email, **dual})

    log_action(
        'notify',
        'management',
        period.id,
        f'Review alert emailed/WhatsApp for {period.period_label} ({len(results)} recipient(s))',
        user=submitted_by,
    )
    return {'ok': True, 'results': results}


def notify_management_period_approved(period, approved_by=None):
    """Email + WhatsApp owners/admins when a period is approved and locked."""
    if not notification_flag('notify_management_on_review', True):
        return {'sent': False, 'mode': 'disabled'}

    from apps.models.user import User
    from apps.services.audit_service import log_action

    recipients = (
        User.query.filter(User.role.in_([User.ROLE_OWNER, User.ROLE_ADMIN]))
        .filter_by(is_active=True)
        .all()
    )
    actor = getattr(approved_by, 'full_name', None) or 'Management'
    subject = f'Period approved — {period.period_label}'
    intro = (
        f'{actor} approved and locked {period.period_label}. '
        f'Company total: {money_label(period.total_profit_loss)}. '
        f'Shareholders pool: {money_label(period.shareholders_pool)}.'
    )
    wa_body = (
        f'{period.period_label} is approved and locked by {actor}. '
        f'Pool {money_label(period.shareholders_pool)}. '
        f'Reports/certificates will send per delivery settings.'
    )
    results = []
    for user in recipients:
        dual = deliver_notice(
            email=user.email,
            phone=resolve_user_whatsapp_phone(user),
            subject=subject,
            title='Period approved',
            paragraphs=[
                f'Hello {user.full_name},',
                intro,
                'Shareholder reports and certificates are generated; delivery follows system settings.',
            ],
            wa_body=wa_body,
            cta_label='Open period',
            cta_endpoint='periods.detail_period',
            cta_kwargs={'period_id': period.id},
            event_key='review',
            content_variables={
                '1': user.full_name or '',
                '2': period.period_label,
                '3': 'approved',
            },
            user_id=user.id,
        )
        results.append({'user': user.email, **dual})

    log_action(
        'notify',
        'management',
        period.id,
        f'Approval alert emailed/WhatsApp for {period.period_label} ({len(results)} recipient(s))',
        user=approved_by,
    )
    return {'ok': True, 'results': results}


def notify_finance_period_rejected(period, rejected_by=None):
    """Email + WhatsApp finance when management returns a period to draft (reject or reopen)."""
    if not notification_flag('notify_management_on_review', True):
        return {'sent': False, 'mode': 'disabled'}

    from apps.models.user import User

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
        dual = deliver_notice(
            email=user.email,
            phone=resolve_user_whatsapp_phone(user),
            subject=subject,
            title='Period needs changes',
            paragraphs=[
                f'Hello {user.full_name},',
                f'{actor} returned {period.period_label} to draft.',
                f'Reason: {reason}',
                'Update the figures if needed, recalculate, and submit for review again.',
            ],
            wa_body=wa_body,
            cta_label='Open period',
            cta_endpoint='periods.detail_period',
            cta_kwargs={'period_id': period.id},
            event_key='review',
            user_id=user.id,
        )
        results.append({'user': user.email, **dual})
    return {'ok': True, 'results': results}


def notify_management_withdrawal_requested(request_obj, actor=None):
    """Alert owners/admins when a shareholder requests capital return (email + WhatsApp)."""
    from apps.models.user import User

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
        dual = deliver_notice(
            email=user.email,
            phone=resolve_user_whatsapp_phone(user),
            subject=subject,
            title='Capital withdrawal pending',
            paragraphs=[
                f'Hello {user.full_name},',
                f'{sh_name} requested return of {amount}.',
                f'Reason: {(request_obj.reason or "")[:400]}',
                'Review and approve or reject in Capital Withdrawals.',
            ],
            wa_body=wa_body,
            cta_label='Review request',
            cta_endpoint='shareholders.review_withdrawal',
            cta_kwargs={'request_id': request_obj.id},
            event_key='withdrawal',
            user_id=user.id,
        )
        results.append({'user': user.email, **dual})
    return {'ok': True, 'results': results}


def notify_shareholder_withdrawal_status(request_obj, status_label):
    """Notify the shareholder when their withdrawal request changes status."""
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

    wa_body = (
        f'Capital withdrawal {status_label}: {amount}. '
        f'Sign in to the shareholder portal for details.'
    )
    return deliver_notice(
        email=shareholder.email,
        phone=resolve_shareholder_whatsapp_phone(shareholder),
        subject=f'Capital withdrawal {status_label.lower()} — {amount}',
        title=f'Withdrawal {status_label}',
        paragraphs=paragraphs,
        wa_body=wa_body,
        cta_label='View in portal',
        cta_endpoint='portal.withdrawal',
        event_key='withdrawal',
        shareholder_id=shareholder.id,
    )


def notify_portal_credentials(user, shareholder, password, created=True):
    """Email + WhatsApp shareholder portal login details after access is granted/updated."""
    if not notification_flag('email_portal_credentials', True):
        return {'sent': False, 'mode': 'disabled'}

    action = 'created' if created else 'updated'
    wa_body = (
        f'Portal access {action} for {shareholder.name}. '
        f'Sign-in: {user.email}. Temporary password: {password}. '
        f'Change your password after first login.'
    )
    phone = resolve_user_whatsapp_phone(user) or resolve_shareholder_whatsapp_phone(shareholder)
    return deliver_notice(
        email=user.email,
        phone=phone,
        subject=f'Your shareholder portal access was {action}',
        title=f'Portal access {action}',
        paragraphs=[
            f'Hello {user.full_name},',
            f'Portal access for {shareholder.name} has been {action}.',
            f'Sign-in email: {user.email}',
            f'Temporary password: {password}',
            'Please sign in and change your password after your first login.',
        ],
        wa_body=wa_body,
        cta_label='Open portal login',
        cta_endpoint='auth.login',
        event_key='credentials',
        content_variables={
            '1': user.full_name or '',
            '2': user.email,
            '3': password,
        },
        user_id=user.id,
        shareholder_id=shareholder.id,
    )


def notify_staff_invite(user, password, created_by=None):
    """Email + WhatsApp a new staff user their account details."""
    if not notification_flag('email_staff_invite', True):
        return {'sent': False, 'mode': 'disabled'}

    role_label = (user.role or 'staff').replace('_', ' ').title()
    wa_body = (
        f'Your {role_label} account is ready. '
        f'Sign-in: {user.email}. Temporary password: {password}.'
    )
    return deliver_notice(
        email=user.email,
        phone=resolve_user_whatsapp_phone(user),
        subject='Your staff account is ready',
        title='Staff account created',
        paragraphs=[
            f'Hello {user.full_name},',
            f'A {role_label} account was created for you'
            + (f' by {created_by.full_name}.' if created_by else '.'),
            f'Sign-in email: {user.email}',
            f'Temporary password: {password}',
            'Sign in and change your password as soon as possible.',
        ],
        wa_body=wa_body,
        cta_label='Sign in',
        cta_endpoint='auth.login',
        event_key='staff_invite',
        content_variables={'1': user.full_name or '', '2': user.email, '3': password},
        user_id=user.id,
    )


def notify_password_changed(user):
    """Confirm a successful password change via email + WhatsApp."""
    if not notification_flag('email_password_change', True):
        return {'sent': False, 'mode': 'disabled'}

    phone = resolve_user_whatsapp_phone(user)
    wa_body = (
        f'Hello {user.full_name}: your account password was changed. '
        f'If this was not you, contact management immediately.'
    )
    return deliver_notice(
        email=user.email,
        phone=phone,
        subject='Your password was changed',
        title='Password updated',
        paragraphs=[
            f'Hello {user.full_name},',
            'Your account password was changed successfully.',
            'If you did not make this change, contact management immediately.',
        ],
        wa_body=wa_body,
        cta_label='Open account',
        cta_endpoint='auth.account',
        event_key='password',
        user_id=user.id,
    )


def notify_shareholders_payment_completed(period, actor=None):
    """Email + WhatsApp shareholders when a period is marked payment completed."""
    from apps.services.audit_service import log_action

    calculations = list(period.calculations)
    if not calculations:
        return {'ok': False, 'mode': 'no_calculations', 'sent': 0}

    results = []
    for calc in calculations:
        shareholder = calc.shareholder
        if not shareholder:
            continue
        amount = money_label(calc.final_amount)
        dual = deliver_notice(
            email=shareholder.email,
            phone=resolve_shareholder_whatsapp_phone(shareholder),
            subject=f'Payment completed — {period.period_label}',
            title=f'Payment completed · {period.period_label}',
            paragraphs=[
                f'Hello {shareholder.name},',
                f'Payment for period {period.period_label} has been marked completed.',
                f'Your distribution amount: {amount}.',
                'Sign in to the portal if you need the statement or certificate.',
            ],
            wa_body=(
                f'{period.period_label}: payment completed. Your share {amount}. '
                f'Details in portal/email.'
            ),
            cta_label='Open portal',
            cta_endpoint='portal.dashboard',
            event_key='payment',
            content_variables={
                '1': shareholder.name,
                '2': period.period_label,
                '3': amount,
            },
            shareholder_id=shareholder.id,
        )
        results.append({'shareholder': shareholder.name, **dual})

    counts = count_dual_results(results)
    log_action(
        'notify',
        'monthly_period',
        period.id,
        (
            f'{period.period_label} payment-completed notices: '
            f'{counts["reached"]}/{counts["total"]} '
            f'(email={counts["email_sent"]}, whatsapp={counts["whatsapp_sent"]})'
        ),
        user=actor,
    )
    return {'ok': True, 'sent': counts['reached'], 'total': counts['total'], 'results': results, 'counts': counts}


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

    results = []
    for calc in calculations:
        shareholder = calc.shareholder
        if not shareholder:
            continue
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

        wa_parts = [
            f'{period.period_label} update: your share is {your_share}.',
            f'Company net {result_word}: {company_total}.',
        ]
        if note:
            wa_parts.append(f'Message: {note[:160]}')
        wa_parts.append('Details by email / portal.')

        dual = deliver_notice(
            email=shareholder.email,
            phone=resolve_shareholder_whatsapp_phone(shareholder),
            subject=f'Profit update — {period.period_label}',
            title=f'Update for {period.period_label}',
            paragraphs=paragraphs,
            wa_body=' '.join(wa_parts),
            cta_label='Open portal',
            cta_endpoint='portal.dashboard',
            event_key='period_update',
            content_variables={
                '1': shareholder.name,
                '2': period.period_label,
                '3': your_share,
            },
            shareholder_id=shareholder.id,
        )
        results.append({'shareholder': shareholder.name, **dual})

    counts = count_dual_results(results)
    log_action(
        'notify_update',
        'monthly_period',
        period.id,
        (
            f'{period.period_label} shareholder update ({reason}): '
            f'{counts["reached"]}/{counts["total"]} '
            f'(email={counts["email_sent"]}, whatsapp={counts["whatsapp_sent"]})'
        ),
        user=actor,
    )
    return {
        'ok': True,
        'sent': counts['reached'],
        'total': counts['total'],
        'results': results,
        'counts': counts,
    }
