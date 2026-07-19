"""SMTP / login OTP readiness checks for UI guidance."""

from __future__ import annotations

from flask import current_app, has_app_context, url_for

from apps.models.settings import SystemSetting


def _setting_or_config(setting_key, config_key=None):
    value = (SystemSetting.get(setting_key) or '').strip()
    if value:
        return value
    if not has_app_context():
        return ''
    cfg_key = config_key or setting_key.upper()
    return str(current_app.config.get(cfg_key) or '').strip()


def otp_is_enabled():
    """Same rules as otp_service.otp_enabled — string-safe config parsing."""
    from apps.services.otp_service import otp_enabled

    if has_app_context():
        return otp_enabled()
    return True


def get_mail_delivery_status():
    """Return SMTP/OTP readiness used by login and settings banners."""
    server = _setting_or_config('mail_server', 'MAIL_SERVER')
    port = _setting_or_config('mail_port', 'MAIL_PORT') or '587'
    username = _setting_or_config('mail_username', 'MAIL_USERNAME')
    password = _setting_or_config('mail_password', 'MAIL_PASSWORD')
    mail_from = _setting_or_config('mail_from', 'MAIL_FROM') or _setting_or_config(
        'mail_username', 'MAIL_DEFAULT_SENDER'
    )

    missing = []
    if not server:
        missing.append('SMTP server')
    if not username:
        missing.append('SMTP username')
    if not password:
        missing.append('SMTP password')
    if not mail_from:
        missing.append('From email')

    smtp_configured = not missing
    otp_enabled = otp_is_enabled()

    whatsapp_ready = False
    whatsapp_enabled = False
    try:
        from apps.services.notification_service import whatsapp_notifications_enabled
        from apps.services.twilio_whatsapp_service import twilio_whatsapp_configured

        whatsapp_enabled = whatsapp_notifications_enabled()
        whatsapp_ready = twilio_whatsapp_configured() and whatsapp_enabled
    except Exception:
        pass

    # OTP can deliver via email (SMTP) and/or WhatsApp when both are configured
    otp_blocked = otp_enabled and not smtp_configured and not whatsapp_ready

    from_domain = (mail_from.split('@')[-1] or '').lower() if mail_from and '@' in mail_from else ''
    consumer_mailbox = from_domain in {
        'gmail.com',
        'googlemail.com',
        'yahoo.com',
        'yahoo.co.uk',
        'outlook.com',
        'hotmail.com',
        'live.com',
        'icloud.com',
    }
    using_gmail_smtp = 'gmail.com' in (server or '').lower()
    # Personal Gmail SMTP often shows in Sent but Zoho/corporate inboxes quarantine the mail
    deliverability_risk = smtp_configured and (consumer_mailbox or using_gmail_smtp)

    settings_url = None
    try:
        settings_url = url_for('app_settings.system_settings', section='email')
    except RuntimeError:
        settings_url = '/settings/system/email'

    if otp_blocked:
        headline = 'Login OTP needs email or WhatsApp before anyone can sign in'
        detail = (
            'One-time codes are enabled, but neither SMTP nor Twilio WhatsApp is ready '
            f"(SMTP missing: {', '.join(missing) or 'none'}). "
            'Configure SMTP and/or Twilio + enable WhatsApp under System Settings, '
            'or set `LOGIN_OTP_ENABLED=false` for local development only.'
        )
    elif not smtp_configured:
        headline = 'SMTP is not configured'
        detail = (
            'Certificate and report emails will be logged only until SMTP is set. '
            f"Missing: {', '.join(missing)}. "
            + (
                'WhatsApp can still deliver notices when Twilio is configured and enabled.'
                if whatsapp_ready
                else 'Enable Twilio WhatsApp as a second channel once SMTP is set.'
            )
        )
    elif deliverability_risk:
        headline = 'SMTP accepts mail — but @akramsweets.com may not receive it'
        detail = (
            f'OTP is leaving via {server} as {mail_from} (appears in Gmail Sent). '
            'Company mailboxes on Zoho (akramsweets.com) often quarantine or spam-folder '
            'login codes from a personal Gmail address. '
            'Fix: send from a Zoho mailbox such as noreply@akramsweets.com '
            '(smtp.zoho.com, port 587) so SPF/DKIM/DMARC align, '
            'and ask users to check Zoho Spam / Admin Quarantine. '
            + ('WhatsApp OTP is also available when enabled.' if whatsapp_ready else '')
        )
    elif otp_enabled:
        channels = [f'email via {server}:{port}']
        if whatsapp_ready:
            channels.append('WhatsApp (Twilio)')
        headline = 'Delivery ready — login OTP enabled'
        detail = (
            f'OTP and shareholder notices use {" + ".join(channels)} '
            f'(from {mail_from}).'
        )
    else:
        headline = 'SMTP ready — login OTP disabled'
        detail = (
            'Password-only login is active (`LOGIN_OTP_ENABLED=false`). '
            'Shareholder report emails can still use SMTP'
            + (' and WhatsApp.' if whatsapp_ready else '.')
        )

    return {
        'smtp_configured': smtp_configured,
        'otp_enabled': otp_enabled,
        'otp_blocked': otp_blocked,
        'whatsapp_ready': whatsapp_ready,
        'whatsapp_enabled': whatsapp_enabled,
        'missing': missing,
        'mail_server': server,
        'mail_port': port,
        'mail_from': mail_from,
        'headline': headline,
        'detail': detail,
        'settings_url': settings_url,
        'deliverability_risk': deliverability_risk,
        'show_warning': otp_blocked or not smtp_configured or deliverability_risk,
    }
