"""Twilio WhatsApp delivery for shareholder and staff notifications."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Optional

from flask import current_app, has_app_context, request

from apps.models.settings import SystemSetting

logger = logging.getLogger(__name__)

# Map logical events → SystemSetting keys for Meta Content Template SIDs
CONTENT_SID_KEYS = {
    'otp': 'twilio_content_sid_otp',
    'report': 'twilio_content_sid_report',
    'credentials': 'twilio_content_sid_credentials',
    'period_update': 'twilio_content_sid_period_update',
    'payment': 'twilio_content_sid_payment',
    'withdrawal': 'twilio_content_sid_withdrawal',
    'staff_invite': 'twilio_content_sid_staff_invite',
    'password': 'twilio_content_sid_password',
    'review': 'twilio_content_sid_review',
    'generic': 'twilio_content_sid_generic',
}


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


def get_content_sid(event_key: Optional[str]) -> Optional[str]:
    """Resolve Meta Content Template SID for an event (optional)."""
    keys = []
    if event_key and event_key in CONTENT_SID_KEYS:
        keys.append(CONTENT_SID_KEYS[event_key])
    keys.append('twilio_content_sid_generic')
    for key in keys:
        if has_app_context():
            try:
                raw = SystemSetting.get(key)
                if raw is not None and str(raw).strip():
                    return str(raw).strip()
            except RuntimeError:
                pass
    return _config_value('TWILIO_WHATSAPP_CONTENT_SID', 'twilio_whatsapp_content_sid') or None


def get_whatsapp_delivery_status():
    """Readiness summary for Settings UI banners."""
    from apps.services.whatsapp_media_service import absolute_url, public_base_url

    cfg = get_twilio_settings()
    missing = []
    if not cfg['account_sid']:
        missing.append('TWILIO_ACCOUNT_SID')
    if not cfg['auth_token']:
        missing.append('TWILIO_AUTH_TOKEN')
    if not cfg['from_number'] and not cfg['messaging_service_sid']:
        missing.append('TWILIO_WHATSAPP_FROM (or TWILIO_MESSAGING_SERVICE_SID)')

    configured = not missing
    base = public_base_url()
    status_url = absolute_url('whatsapp.status_callback')
    inbound_url = absolute_url('whatsapp.inbound_webhook')

    if configured:
        sender = cfg['from_number'] or cfg['messaging_service_sid']
        headline = 'Twilio WhatsApp ready'
        detail = f'Outbound WhatsApp notifications will send from {sender}.'
        if not base:
            detail += (
                ' Set PUBLIC_BASE_URL so Twilio can fetch PDF media and post delivery webhooks.'
            )
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
        'public_base_url': base,
        'status_callback_url': status_url,
        'inbound_webhook_url': inbound_url,
    }


def normalize_whatsapp_address(phone: Optional[str], *, default_country_code: str = '252') -> Optional[str]:
    """
    Normalize a phone number to Twilio's whatsapp:+E164 form.

    Accepts values like +25261..., 25261..., 061..., or whatsapp:+25261...
    Local numbers starting with 0 are converted using ``default_country_code``
    (Somalia 252 by default for Akram Sweets).
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
        cleaned = re.sub(r'\D', '', digits)
        if not cleaned:
            return None
        # Local Somalia-style numbers: 061XXXXXXX → +25261XXXXXXX
        if cleaned.startswith('0') and default_country_code:
            cc = re.sub(r'\D', '', str(default_country_code))
            e164 = f'+{cc}{cleaned.lstrip("0")}'
        else:
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
    digits = re.sub(r'[^\d+]', '', from_number)
    if digits.startswith('+') or digits.isdigit():
        return normalize_whatsapp_address(from_number)
    return from_number


def _log_outbound(
    *,
    to_addr,
    from_addr,
    body,
    status,
    twilio_sid=None,
    error=None,
    event_key=None,
    media_urls=None,
    content_sid=None,
    user_id=None,
    shareholder_id=None,
):
    try:
        from apps import db
        from apps.models.whatsapp_message import WhatsAppMessage

        row = WhatsAppMessage(
            direction=WhatsAppMessage.DIRECTION_OUTBOUND,
            twilio_sid=twilio_sid,
            from_address=from_addr,
            to_address=to_addr,
            body=(body or '')[:4000] if body else None,
            status=status,
            error_message=(str(error)[:2000] if error else None),
            event_key=event_key,
            media_urls=json.dumps(media_urls) if media_urls else None,
            content_sid=content_sid,
            user_id=user_id,
            shareholder_id=shareholder_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.session.add(row)
        db.session.commit()
        return row
    except Exception:
        logger.exception('Failed to persist WhatsApp outbound log')
        try:
            from apps import db

            db.session.rollback()
        except Exception:
            pass
        return None


def send_whatsapp_message(
    phone,
    body,
    *,
    content_sid=None,
    content_variables=None,
    media_urls=None,
    event_key=None,
    user_id=None,
    shareholder_id=None,
    use_template=True,
):
    """
    Send a WhatsApp message via Twilio.

    Free-form ``body`` works in the Twilio sandbox and inside the 24-hour
    customer-care window. For production business-initiated messages outside
    that window, configure a Meta-approved Content Template SID per event.
    ``media_urls`` must be publicly reachable HTTPS URLs (certificate/report PDFs).
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
    resolved_sid = content_sid
    if use_template and not resolved_sid:
        resolved_sid = get_content_sid(event_key)

    media_list = [u for u in (media_urls or []) if u]
    if not body and not resolved_sid and not media_list:
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
            (body or resolved_sid or '')[:120],
        )
        _log_outbound(
            to_addr=to_addr,
            from_addr=cfg.get('from_number'),
            body=body,
            status='stub',
            event_key=event_key,
            media_urls=media_list,
            content_sid=resolved_sid,
            user_id=user_id,
            shareholder_id=shareholder_id,
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

    from apps.services.whatsapp_media_service import absolute_url

    client = Client(cfg['account_sid'], cfg['auth_token'])
    create_kwargs = {'to': to_addr}
    from_addr = None
    if cfg.get('messaging_service_sid'):
        create_kwargs['messaging_service_sid'] = cfg['messaging_service_sid']
    else:
        from_addr = _whatsapp_from_address(cfg)
        if not from_addr:
            return {
                'sent': False,
                'mode': 'error',
                'channel': 'whatsapp',
                'recipient': to_addr,
                'reason': 'invalid_twilio_whatsapp_from',
            }
        create_kwargs['from_'] = from_addr

    status_cb = absolute_url('whatsapp.status_callback')
    if status_cb and status_cb.startswith('http'):
        create_kwargs['status_callback'] = status_cb

    if resolved_sid:
        create_kwargs['content_sid'] = resolved_sid
        if content_variables:
            create_kwargs['content_variables'] = (
                content_variables
                if isinstance(content_variables, str)
                else json.dumps(content_variables)
            )
    else:
        if body:
            create_kwargs['body'] = body
        if media_list:
            # Twilio WhatsApp typically accepts one media URL per message
            create_kwargs['media_url'] = [media_list[0]]

    try:
        message = client.messages.create(**create_kwargs)
    except Exception as exc:
        logger.exception('Twilio WhatsApp send failed to %s', to_addr)
        _log_outbound(
            to_addr=to_addr,
            from_addr=from_addr or cfg.get('from_number'),
            body=body,
            status='failed',
            error=exc,
            event_key=event_key,
            media_urls=media_list,
            content_sid=resolved_sid,
            user_id=user_id,
            shareholder_id=shareholder_id,
        )
        return {
            'sent': False,
            'mode': 'error',
            'channel': 'whatsapp',
            'recipient': to_addr,
            'reason': 'twilio_error',
            'error': str(exc),
        }

    status = getattr(message, 'status', None) or 'queued'
    _log_outbound(
        to_addr=to_addr,
        from_addr=from_addr or cfg.get('from_number'),
        body=body,
        status=status,
        twilio_sid=message.sid,
        event_key=event_key,
        media_urls=(None if resolved_sid else media_list[:1]) if media_list else None,
        content_sid=resolved_sid,
        user_id=user_id,
        shareholder_id=shareholder_id,
    )

    # Media follow-ups: remaining PDFs, or all PDFs when the first message used a Content Template
    media_followups = media_list if resolved_sid else media_list[1:]
    extra_results = []
    for idx, extra_url in enumerate(media_followups):
        try:
            label = 'Certificate PDF' if idx == 0 and resolved_sid else 'Profit report PDF'
            extra_kwargs = {
                'to': to_addr,
                'body': f'{label} for your records.',
                'media_url': [extra_url],
            }
            if cfg.get('messaging_service_sid'):
                extra_kwargs['messaging_service_sid'] = cfg['messaging_service_sid']
            else:
                extra_kwargs['from_'] = from_addr
            if status_cb and status_cb.startswith('http'):
                extra_kwargs['status_callback'] = status_cb
            extra_msg = client.messages.create(**extra_kwargs)
            _log_outbound(
                to_addr=to_addr,
                from_addr=from_addr or cfg.get('from_number'),
                body=extra_kwargs['body'],
                status=getattr(extra_msg, 'status', None) or 'queued',
                twilio_sid=extra_msg.sid,
                event_key=f'{event_key}_media' if event_key else 'media',
                media_urls=[extra_url],
                user_id=user_id,
                shareholder_id=shareholder_id,
            )
            extra_results.append(extra_msg.sid)
        except Exception:
            logger.exception('WhatsApp follow-up media failed to %s', to_addr)

    logger.info(
        'WhatsApp sent to %s (sid=%s status=%s event=%s)',
        to_addr,
        message.sid,
        status,
        event_key,
    )
    return {
        'sent': True,
        'mode': 'twilio',
        'channel': 'whatsapp',
        'recipient': to_addr,
        'sid': message.sid,
        'status': status,
        'extra_sids': extra_results,
        'content_sid': resolved_sid,
    }


def update_message_status_from_webhook(form_data: dict) -> Optional[object]:
    """Apply Twilio status callback fields to the matching WhatsAppMessage row."""
    sid = (form_data.get('MessageSid') or form_data.get('SmsSid') or '').strip()
    status = (form_data.get('MessageStatus') or form_data.get('SmsStatus') or '').strip()
    if not sid:
        return None
    from apps import db
    from apps.models.whatsapp_message import WhatsAppMessage

    row = WhatsAppMessage.query.filter_by(twilio_sid=sid).first()
    if not row:
        row = WhatsAppMessage(
            direction=WhatsAppMessage.DIRECTION_OUTBOUND,
            twilio_sid=sid,
            to_address=(form_data.get('To') or '').strip() or None,
            from_address=(form_data.get('From') or '').strip() or None,
            status=status or 'unknown',
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.session.add(row)
    else:
        row.status = status or row.status
        row.updated_at = datetime.utcnow()
    err_code = form_data.get('ErrorCode')
    err_msg = form_data.get('ErrorMessage')
    if err_code:
        row.error_code = str(err_code)[:40]
    if err_msg:
        row.error_message = str(err_msg)[:2000]
    db.session.commit()
    return row


def record_inbound_message(form_data: dict) -> Optional[object]:
    """Store an inbound WhatsApp message and optionally auto-reply."""
    from apps import db
    from apps.models.whatsapp_message import WhatsAppMessage

    from_addr = (form_data.get('From') or '').strip()
    to_addr = (form_data.get('To') or '').strip()
    body = (form_data.get('Body') or '').strip()
    sid = (form_data.get('MessageSid') or form_data.get('SmsSid') or '').strip()

    row = WhatsAppMessage(
        direction=WhatsAppMessage.DIRECTION_INBOUND,
        twilio_sid=sid or None,
        from_address=from_addr or None,
        to_address=to_addr or None,
        body=body[:4000] if body else None,
        status='received',
        event_key='inbound',
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    num_media = int(form_data.get('NumMedia') or 0)
    if num_media > 0:
        urls = [form_data.get(f'MediaUrl{i}') for i in range(num_media) if form_data.get(f'MediaUrl{i}')]
        row.media_urls = json.dumps(urls)
    db.session.add(row)
    db.session.commit()

    if _auto_reply_enabled() and from_addr:
        reply = _auto_reply_text()
        # Strip whatsapp: prefix for normalize
        phone = from_addr.replace('whatsapp:', '')
        send_whatsapp_message(phone, reply, event_key='auto_reply', use_template=False)
    return row


def _auto_reply_enabled() -> bool:
    raw = SystemSetting.get('whatsapp_auto_reply_enabled')
    if raw is None or str(raw).strip() == '':
        return True
    return str(raw).strip().lower() in ('1', 'true', 'yes', 'on')


def _auto_reply_text() -> str:
    text = (SystemSetting.get('whatsapp_auto_reply_text') or '').strip()
    if text:
        return text
    return (
        'Thank you for contacting Akram Sweets Shareholders. '
        'This channel sends official notices (reports, OTP, withdrawals). '
        'For support, please use the portal or email management.'
    )


def validate_twilio_request() -> bool:
    """Validate X-Twilio-Signature when possible; allow if token missing (dev)."""
    cfg = get_twilio_settings()
    token = cfg.get('auth_token')
    if not token:
        return True
    try:
        from twilio.request_validator import RequestValidator

        validator = RequestValidator(token)
        signature = request.headers.get('X-Twilio-Signature', '')
        url = request.url
        # Prefer public URL if behind proxy
        from apps.services.whatsapp_media_service import public_base_url

        base = public_base_url()
        if base:
            url = f'{base}{request.path}'
            if request.query_string:
                url = f'{url}?{request.query_string.decode()}'
        return validator.validate(url, request.form, signature)
    except Exception:
        logger.exception('Twilio signature validation error')
        return False


def resolve_user_whatsapp_phone(user):
    """Prefer the user's own phone, then a linked shareholder phone."""
    if not user:
        return None
    own = getattr(user, 'phone', None)
    if own and str(own).strip():
        return str(own).strip()
    shareholder = getattr(user, 'shareholder', None)
    if shareholder and shareholder.phone:
        return shareholder.phone
    return None


def mask_phone(phone: Optional[str]) -> str:
    """Mask a phone for UI (show last 4 digits)."""
    if not phone:
        return ''
    digits = re.sub(r'\D', '', str(phone))
    if len(digits) < 4:
        return '***'
    return f'+…{digits[-4:]}'
