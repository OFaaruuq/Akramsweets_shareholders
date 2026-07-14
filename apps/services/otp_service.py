"""Login OTP generation, verification, and email delivery."""

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
    # Numeric OTP only — easier to type from email
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


def begin_otp_challenge(user: User, remember: bool = False) -> tuple[bool, str]:
    """Create a fresh OTP, email it, and stash challenge state in the session."""
    from apps.services.email_service import send_login_otp_email

    # Invalidate previous unused codes for this user
    LoginOTP.query.filter_by(user_id=user.id, consumed_at=None).update(
        {'consumed_at': datetime.utcnow()},
        synchronize_session=False,
    )

    code = _generate_code()
    otp = LoginOTP(
        user_id=user.id,
        code_hash=LoginOTP.hash_code(code),
        expires_at=datetime.utcnow() + timedelta(minutes=otp_expiry_minutes()),
        attempts=0,
    )
    db.session.add(otp)
    db.session.commit()

    result = send_login_otp_email(user, code, expires_minutes=otp_expiry_minutes())
    if not result.get('sent'):
        reason = result.get('reason') or result.get('error') or 'email_failed'
        logger.warning('OTP email failed for %s: %s', user.email, reason)
        # Keep OTP row but clear session so user must restart login
        clear_otp_session()
        return False, reason

    session[SESSION_USER_KEY] = user.id
    session[SESSION_REMEMBER_KEY] = bool(remember)
    session[SESSION_EMAIL_KEY] = mask_email(user.email)
    session.modified = True

    # Test hook — never expose in production responses
    if current_app.config.get('OTP_TEST_CAPTURE'):
        current_app.config['OTP_LAST_CODE'] = code

    logger.info('Login OTP emailed to %s (expires in %s min)', user.email, otp_expiry_minutes())
    return True, 'sent'


def pending_otp_user() -> User | None:
    user_id = session.get(SESSION_USER_KEY)
    if not user_id:
        return None
    user = User.query.get(user_id)
    if not user or not user.is_active:
        clear_otp_session()
        return None
    return user


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
