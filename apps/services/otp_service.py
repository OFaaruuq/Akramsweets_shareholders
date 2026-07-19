"""Login OTP generation, verification, and email / WhatsApp delivery."""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta

from flask import current_app, session

from apps import db
from apps.models.login_otp import LoginOTP
from apps.models.user import User

logger = logging.getLogger(__name__)

SESSION_USER_KEY = 'otp_user_id'
SESSION_REMEMBER_KEY = 'otp_remember'
SESSION_EMAIL_KEY = 'otp_email_mask'
SESSION_PHONE_KEY = 'otp_phone_mask'
SESSION_CHANNELS_KEY = 'otp_channels'


def otp_enabled() -> bool:
    value = str(current_app.config.get('LOGIN_OTP_ENABLED', 'true')).lower()
    return value in ('1', 'true', 'yes', 'on')


def otp_length() -> int:
    try:
        length = int(current_app.config.get('OTP_LENGTH', 6))
    except (TypeError, ValueError):
        length = 6
    return max(4, min(length, 8))


def otp_expiry_minutes() -> int:
    try:
        minutes = int(current_app.config.get('OTP_EXPIRY_MINUTES', 10))
    except (TypeError, ValueError):
        minutes = 10
    return max(2, min(minutes, 60))


def otp_max_attempts() -> int:
    try:
        attempts = int(current_app.config.get('OTP_MAX_ATTEMPTS', 5))
    except (TypeError, ValueError):
        attempts = 5
    return max(3, min(attempts, 10))


def _generate_code() -> str:
    length = otp_length()
    # Numeric OTP only — easier to type from email / WhatsApp
    upper = 10 ** length
    return str(secrets.randbelow(upper)).zfill(length)


def mask_email(email: str) -> str:
    email = (email or '').strip()
    if '@' not in email:
        return email
    local, _, domain = email.partition('@')
    if len(local) <= 2:
        masked_local = local[:1] + '*'
    else:
        masked_local = local[:2] + ('*' * min(len(local) - 2, 5))
    return f'{masked_local}@{domain}'


def clear_otp_session() -> None:
    session.pop(SESSION_USER_KEY, None)
    session.pop(SESSION_REMEMBER_KEY, None)
    session.pop(SESSION_EMAIL_KEY, None)
    session.pop(SESSION_PHONE_KEY, None)
    session.pop(SESSION_CHANNELS_KEY, None)


def _delivery_ok(result: dict | None) -> bool:
    """Require a real send — stub/log modes must not unlock the OTP step."""
    return bool(result and result.get('sent'))


def _send_otp_whatsapp(user: User, code: str, expires_minutes: int) -> dict | None:
    from apps.services.notification_service import whatsapp_notifications_enabled
    from apps.services.twilio_whatsapp_service import (
        mask_phone,
        resolve_user_whatsapp_phone,
        send_whatsapp_message,
    )

    if not whatsapp_notifications_enabled():
        return None
    phone = resolve_user_whatsapp_phone(user)
    if not phone:
        return None

    company = current_app.config.get('APP_NAME') or 'Akram Sweets'
    try:
        from apps.services.brand_service import get_brand_settings

        company = get_brand_settings().get('company_name') or company
    except Exception:
        pass

    body = (
        f'{company} login code: {code}. '
        f'Valid for {expires_minutes} minutes. Do not share this code.'
    )
    result = send_whatsapp_message(
        phone,
        body,
        event_key='otp',
        content_variables={'1': user.full_name or '', '2': code, '3': str(expires_minutes)},
        user_id=user.id,
    )
    result = dict(result or {})
    result['masked_phone'] = mask_phone(phone)
    return result


def begin_otp_challenge(user: User, remember: bool = False) -> tuple[bool, str]:
    """Create a fresh OTP, deliver via email and/or WhatsApp, stash session state."""
    from apps.services.email_service import send_login_otp_email

    # Invalidate previous unused codes for this user
    LoginOTP.query.filter_by(user_id=user.id, consumed_at=None).update(
        {'consumed_at': datetime.utcnow()},
        synchronize_session=False,
    )

    code = _generate_code()
    expires = otp_expiry_minutes()
    otp = LoginOTP(
        user_id=user.id,
        code_hash=LoginOTP.hash_code(code),
        expires_at=datetime.utcnow() + timedelta(minutes=expires),
        attempts=0,
    )
    db.session.add(otp)
    db.session.commit()

    email_result = send_login_otp_email(user, code, expires_minutes=expires)
    whatsapp_result = _send_otp_whatsapp(user, code, expires)

    email_ok = _delivery_ok(email_result)
    whatsapp_ok = _delivery_ok(whatsapp_result)

    if not email_ok and not whatsapp_ok:
        reason = (
            (email_result or {}).get('reason')
            or (whatsapp_result or {}).get('reason')
            or (email_result or {}).get('error')
            or 'delivery_failed'
        )
        logger.warning(
            'OTP delivery failed for %s (email=%s whatsapp=%s)',
            user.email,
            (email_result or {}).get('mode') or (email_result or {}).get('reason'),
            (whatsapp_result or {}).get('mode') or (whatsapp_result or {}).get('reason'),
        )
        clear_otp_session()
        return False, reason

    channels = []
    if email_ok:
        channels.append('email')
    if whatsapp_ok:
        channels.append('whatsapp')

    session[SESSION_USER_KEY] = user.id
    session[SESSION_REMEMBER_KEY] = bool(remember)
    session[SESSION_EMAIL_KEY] = mask_email(user.email)
    session[SESSION_PHONE_KEY] = (whatsapp_result or {}).get('masked_phone') or ''
    session[SESSION_CHANNELS_KEY] = channels
    session.modified = True

    # Test hook — never expose in production responses
    if current_app.config.get('OTP_TEST_CAPTURE'):
        current_app.config['OTP_LAST_CODE'] = code

    logger.info(
        'Login OTP delivered to %s via %s (expires in %s min)',
        user.email,
        '+'.join(channels),
        expires,
    )
    if email_ok and whatsapp_ok:
        return True, 'sent_both'
    if whatsapp_ok and not email_ok:
        return True, 'sent_whatsapp'
    return True, 'sent_email'


def pending_otp_user() -> User | None:
    user_id = session.get(SESSION_USER_KEY)
    if not user_id:
        return None
    user = User.query.get(user_id)
    if not user or not user.is_active:
        clear_otp_session()
        return None
    return user


def otp_delivery_hint() -> dict:
    """Masked destinations for the verify-OTP page."""
    return {
        'channels': list(session.get(SESSION_CHANNELS_KEY) or ['email']),
        'masked_email': session.get(SESSION_EMAIL_KEY) or '',
        'masked_phone': session.get(SESSION_PHONE_KEY) or '',
    }


def resend_otp() -> tuple[bool, str]:
    user = pending_otp_user()
    if not user:
        return False, 'no_pending_challenge'
    remember = bool(session.get(SESSION_REMEMBER_KEY))
    return begin_otp_challenge(user, remember=remember)


def verify_otp_code(code: str) -> tuple[User | None, str]:
    user = pending_otp_user()
    if not user:
        return None, 'no_pending_challenge'

    otp = (
        LoginOTP.query.filter_by(user_id=user.id, consumed_at=None)
        .order_by(LoginOTP.created_at.desc())
        .first()
    )
    if not otp:
        clear_otp_session()
        return None, 'no_otp'

    if otp.is_expired():
        otp.consumed_at = datetime.utcnow()
        db.session.commit()
        clear_otp_session()
        return None, 'expired'

    otp.attempts += 1
    if otp.attempts > otp_max_attempts():
        otp.consumed_at = datetime.utcnow()
        db.session.commit()
        clear_otp_session()
        return None, 'too_many_attempts'

    if not otp.matches(code or ''):
        db.session.commit()
        return None, 'invalid'

    otp.consumed_at = datetime.utcnow()
    db.session.commit()
    remember = bool(session.get(SESSION_REMEMBER_KEY))
    clear_otp_session()
    # Stash remember flag briefly for the route to read
    session['_otp_remember_once'] = remember
    session.modified = True
    return user, 'ok'


def pop_remember_flag() -> bool:
    return bool(session.pop('_otp_remember_once', False))
