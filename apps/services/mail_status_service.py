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
    otp_blocked = otp_enabled and not smtp_configured

    settings_url = None
    try:
        settings_url = url_for('app_settings.system_settings')
    except RuntimeError:
        settings_url = '/settings/system'

    if otp_blocked:
        headline = 'Login OTP needs SMTP before anyone can sign in'
        detail = (
            'Email one-time codes are enabled, but SMTP is incomplete '
            f"(missing: {', '.join(missing)}). "
            'Add mail settings under System Settings or in `.env`, '
            'or set `LOGIN_OTP_ENABLED=false` for local development only.'
        )
    elif not smtp_configured:
        headline = 'SMTP is not configured'
        detail = (
            'Certificate and report emails will be logged only until SMTP is set. '
            f"Missing: {', '.join(missing)}."
        )
    elif otp_enabled:
        headline = 'SMTP ready — login OTP enabled'
        detail = (
            f'OTP codes and shareholder emails will send via {server}:{port} '
            f'from {mail_from}.'
        )
    else:
        headline = 'SMTP ready — login OTP disabled'
        detail = (
            'Password-only login is active (`LOGIN_OTP_ENABLED=false`). '
            'Shareholder report emails can still use SMTP.'
        )

    return {
        'smtp_configured': smtp_configured,
        'otp_enabled': otp_enabled,
        'otp_blocked': otp_blocked,
        'missing': missing,
        'mail_server': server,
        'mail_port': port,
        'mail_from': mail_from,
        'headline': headline,
        'detail': detail,
        'settings_url': settings_url,
        'show_warning': otp_blocked or not smtp_configured,
    }
