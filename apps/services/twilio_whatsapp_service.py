"""Twilio WhatsApp delivery for shareholder and staff notifications."""

from __future__ import annotations

import logging
import re
from typing import Optional

from flask import current_app, has_app_context

from apps.models.settings import SystemSetting

logger = logging.getLogger(__name__)


def _config_value(name, setting_key=None):
    """Prefer SystemSetting override, then Flask/app config / process env."""
    if setting_key and has_app_context():
        try:
            raw = SystemSetting.get(setting_key)
            if raw is not None and str(raw).strip() != '':
                return str(raw).strip()
        except RuntimeError:
            pass
    if has_app_context():
        value = current_app.config.get(name)
        if value is not None and str(value).strip() != '':
            return str(value).strip()
    import os

    return (os.getenv(name) or '').strip()


def get_twilio_settings():
    account_sid = _config_value('TWILIO_ACCOUNT_SID', 'twilio_account_sid')
    auth_token = _config_value('TWILIO_AUTH_TOKEN', 'twilio_auth_token')
    from_number = _config_value('TWILIO_WHATSAPP_FROM', 'twilio_whatsapp_from')
    messaging_service_sid = _config_value(
        'TWILIO_MESSAGING_SERVICE_SID', 'twilio_messaging_service_sid'
    )
    return {
        'account_sid': account_sid,
        'auth_token': auth_token,
        'from_number': from_number,
        'messaging_service_sid': messaging_service_sid,
    }


def twilio_whatsapp_configured():
    cfg = get_twilio_settings()
    has_auth = bool(cfg['account_sid'] and cfg['auth_token'])
    has_sender = bool(cfg['from_number'] or cfg['messaging_service_sid'])
    return has_auth and has_sender


def get_whatsapp_delivery_status():
    """Readiness summary for Settings UI banners."""
    cfg = get_twilio_settings()
    missing = []
    if not cfg['account_sid']:
        missing.append('TWILIO_ACCOUNT_SID')
    if not cfg['auth_token']:
        missing.append('TWILIO_AUTH_TOKEN')
    if not cfg['from_number'] and not cfg['messaging_service_sid']:
        missing.append('TWILIO_WHATSAPP_FROM (or TWILIO_MESSAGING_SERVICE_SID)')

    configured = not missing
    if configured:
        sender = cfg['from_number'] or cfg['messaging_service_sid']
        headline = 'Twilio WhatsApp ready'
        detail = f'Outbound WhatsApp notifications will send from {sender}.'
    else:
        headline = 'Twilio WhatsApp is not configured'
        detail = (
            'Enable WhatsApp in Settings and set Twilio credentials in `.env`. '
            f"Missing: {', '.join(missing)}."
        )

    return {
        'configured': configured,
        'missing': missing,
        'from_number': cfg['from_number'],
        'headline': headline,
        'detail': detail,
        'show_warning': not configured,
    }


def normalize_whatsapp_address(phone: Optional[str]) -> Optional[str]:
    """
    Normalize a phone number to Twilio's whatsapp:+E164 form.

    Accepts values like +25261..., 25261..., or whatsapp:+25261...
    """
    if not phone:
        return None
    raw = str(phone).strip()
    if not raw:
        return None

    if raw.lower().startswith('whatsapp:'):
        raw = raw.split(':', 1)[1].strip()

    digits = re.sub(r'[^\d+]', '', raw)
    if not digits:
        return None

    if digits.startswith('+'):
        e164 = '+' + re.sub(r'\D', '', digits)
    else:
        # Local-looking numbers need a country code; keep digits and require +
        cleaned = re.sub(r'\D', '', digits)
        if not cleaned:
            return None
        # If already looks like international (8+ digits starting without 0), prefix +
        if cleaned.startswith('0'):
            logger.warning(
                'WhatsApp phone %s looks local (leading 0); store E.164 with country code',
                phone,
            )
            return None
        e164 = f'+{cleaned}'

    if len(re.sub(r'\D', '', e164)) < 8:
        return None
    return f'whatsapp:{e164}'


def _whatsapp_from_address(cfg):
    from_number = (cfg.get('from_number') or '').strip()
    if not from_number:
        return None
    if from_number.lower().startswith('whatsapp:'):
        return from_number
    if from_number.startswith('+'):
        return f'whatsapp:{from_number}'
    # Allow bare SID-looking values only via messaging_service_sid
    digits = re.sub(r'[^\d+]', '', from_number)
    if digits.startswith('+') or digits.isdigit():
        return normalize_whatsapp_address(from_number)
    return from_number


def send_whatsapp_message(phone, body, *, content_sid=None, content_variables=None):
    """
    Send a WhatsApp message via Twilio.

    Free-form ``body`` works in the Twilio sandbox and inside the 24-hour
    customer-care window. For production business-initiated messages outside
    that window, pass a Meta-approved ``content_sid`` (and variables).
    """
    to_addr = normalize_whatsapp_address(phone)
    if not to_addr:
        return {
            'sent': False,
            'mode': 'skipped',
            'channel': 'whatsapp',
            'reason': 'invalid_or_missing_phone',
            'recipient': phone,
        }

    body = (body or '').strip()
    if not body and not content_sid:
        return {
            'sent': False,
            'mode': 'skipped',
            'channel': 'whatsapp',
            'reason': 'empty_message',
            'recipient': to_addr,
        }

    cfg = get_twilio_settings()
    if not twilio_whatsapp_configured():
        logger.info(
            'WhatsApp stub (Twilio not configured) to %s: %s',
            to_addr,
            (body or content_sid or '')[:120],
        )
        return {
            'sent': False,
            'mode': 'stub',
            'channel': 'whatsapp',
            'recipient': to_addr,
            'reason': 'twilio_not_configured',
        }

    try:
        from twilio.rest import Client
    except ImportError:
        logger.error('twilio package is not installed — run pip install twilio')
        return {
            'sent': False,
            'mode': 'error',
            'channel': 'whatsapp',
            'recipient': to_addr,
            'reason': 'twilio_package_missing',
        }

    client = Client(cfg['account_sid'], cfg['auth_token'])
    create_kwargs = {'to': to_addr}
    if cfg.get('messaging_service_sid'):
        create_kwargs['messaging_service_sid'] = cfg['messaging_service_sid']
    else:
        create_kwargs['from_'] = _whatsapp_from_address(cfg)

    if content_sid:
        create_kwargs['content_sid'] = content_sid
        if content_variables:
            import json

            create_kwargs['content_variables'] = (
                content_variables
                if isinstance(content_variables, str)
                else json.dumps(content_variables)
            )
    else:
        create_kwargs['body'] = body

    try:
        message = client.messages.create(**create_kwargs)
    except Exception as exc:
        logger.exception('Twilio WhatsApp send failed to %s', to_addr)
        return {
            'sent': False,
            'mode': 'error',
            'channel': 'whatsapp',
            'recipient': to_addr,
            'reason': 'twilio_error',
            'error': str(exc),
        }

    logger.info(
        'WhatsApp sent to %s (sid=%s status=%s)',
        to_addr,
        message.sid,
        getattr(message, 'status', None),
    )
    return {
        'sent': True,
        'mode': 'twilio',
        'channel': 'whatsapp',
        'recipient': to_addr,
        'sid': message.sid,
        'status': getattr(message, 'status', None),
    }


def resolve_user_whatsapp_phone(user):
    """Staff phone via linked shareholder record (users have no phone column)."""
    if not user:
        return None
    shareholder = getattr(user, 'shareholder', None)
    if shareholder and shareholder.phone:
        return shareholder.phone
    return None
