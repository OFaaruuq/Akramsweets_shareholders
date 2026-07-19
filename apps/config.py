# -*- encoding: utf-8 -*-
"""Application configuration — single source for env loading and DB URI."""

from __future__ import annotations

import os
import random
import string
from urllib.parse import quote_plus

from dotenv import load_dotenv

# Project .env only (process env always wins). Do not load parent workspace .env —
# that bleeds settings across projects and breaks clean-server deploys.
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
load_dotenv(os.path.join(_PROJECT_ROOT, '.env'))


def _env_bool(name, default=False):
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in ('1', 'true', 'yes', 'on')


def _env_int(name, default):
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == '':
        return default
    try:
        return int(str(raw).strip())
    except ValueError:
        return default


def _normalize_database_url(url):
    """Render/Heroku may provide postgres://; SQLAlchemy expects postgresql+psycopg2://."""
    url = (url or '').strip()
    if url.startswith('postgres://'):
        return url.replace('postgres://', 'postgresql+psycopg2://', 1)
    if url.startswith('postgresql://') and '+psycopg2' not in url:
        return url.replace('postgresql://', 'postgresql+psycopg2://', 1)
    return url


def build_database_uri(basedir):
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        return _normalize_database_url(database_url)

    db_engine = (os.getenv('DB_ENGINE') or 'postgresql+psycopg2').strip().lower()

    if db_engine in ('sqlite', 'sqlite3'):
        db_file = os.getenv('SQLITE_PATH') or os.path.join(basedir, 'db.sqlite3')
        return 'sqlite:///' + db_file

    if db_engine in ('postgres', 'postgresql', 'pgsql'):
        db_engine = 'postgresql+psycopg2'
    elif not (db_engine == 'postgresql+psycopg2' or db_engine.startswith('postgresql')):
        db_engine = 'postgresql+psycopg2'

    db_username = os.getenv('DB_USERNAME', 'akram_user') or 'akram_user'
    db_pass = os.getenv('DB_PASS', 'akram_pass')
    db_host = os.getenv('DB_HOST', '127.0.0.1') or '127.0.0.1'
    db_port = os.getenv('DB_PORT', '5432') or '5432'
    db_name = os.getenv('DB_NAME', 'akram_shareholders') or 'akram_shareholders'

    user = quote_plus(db_username)
    if db_pass is None or db_pass == '':
        auth = user
    else:
        auth = f'{user}:{quote_plus(db_pass)}'
    return f'{db_engine}://{auth}@{db_host}:{db_port}/{db_name}'


def redact_database_uri(uri):
    """Safe URI for logs (strip credentials)."""
    if not uri:
        return ''
    if '://' not in uri:
        return uri
    scheme, rest = uri.split('://', 1)
    if '@' in rest:
        rest = rest.split('@', 1)[1]
        return f'{scheme}://***@{rest}'
    return f'{scheme}://{rest}'


class Config(object):
    basedir = os.path.abspath(os.path.dirname(__file__))

    ASSETS_ROOT = os.getenv('ASSETS_ROOT', '/static')
    SECRET_KEY = os.getenv('SECRET_KEY') or None

    SOCIAL_AUTH_GITHUB = False
    GITHUB_ID = None
    GITHUB_SECRET = None

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = build_database_uri(basedir)

    if SQLALCHEMY_DATABASE_URI.startswith('sqlite'):
        SQLALCHEMY_ENGINE_OPTIONS = {'connect_args': {'check_same_thread': False}}
    else:
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_pre_ping': True,
            'pool_recycle': 300,
        }

    WTF_CSRF_ENABLED = True

    MAIL_SERVER = os.getenv('MAIL_SERVER') or None
    MAIL_PORT = _env_int('MAIL_PORT', 587)
    MAIL_USERNAME = os.getenv('MAIL_USERNAME') or None
    _mail_password = os.getenv('MAIL_PASSWORD')
    MAIL_PASSWORD = ''.join(_mail_password.split()) if _mail_password else None
    MAIL_FROM = os.getenv('MAIL_FROM') or os.getenv('MAIL_DEFAULT_SENDER') or None
    MAIL_DEFAULT_SENDER = MAIL_FROM
    MAIL_USE_TLS = _env_bool('MAIL_USE_TLS', True)

    LOGIN_OTP_ENABLED = _env_bool('LOGIN_OTP_ENABLED', True)
    OTP_LENGTH = _env_int('OTP_LENGTH', 6)
    OTP_EXPIRY_MINUTES = _env_int('OTP_EXPIRY_MINUTES', 10)
    OTP_MAX_ATTEMPTS = _env_int('OTP_MAX_ATTEMPTS', 5)
    OTP_TEST_CAPTURE = _env_bool('OTP_TEST_CAPTURE', False)

    # Twilio WhatsApp (optional — enable in Settings → Email & delivery)
    TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID') or None
    TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN') or None
    TWILIO_WHATSAPP_FROM = os.getenv('TWILIO_WHATSAPP_FROM') or None
    TWILIO_MESSAGING_SERVICE_SID = os.getenv('TWILIO_MESSAGING_SERVICE_SID') or None
    # Optional Meta-approved Content Template SID for production outbound messages
    TWILIO_WHATSAPP_CONTENT_SID = os.getenv('TWILIO_WHATSAPP_CONTENT_SID') or None
    # Public HTTPS origin so Twilio can fetch PDF media and post webhooks
    PUBLIC_BASE_URL = (os.getenv('PUBLIC_BASE_URL') or '').rstrip('/') or None


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_DURATION = 3600


class DebugConfig(Config):
    DEBUG = True


config_dict = {
    'Production': ProductionConfig,
    'Debug': DebugConfig,
}


def resolve_config(name=None):
    """
    Resolve Debug/Production config.

    Prefer DEBUG=true/false. Falls back to FLASK_ENV only for legacy values
    (development/production), never treating FLASK_ENV as a config_dict key.
    """
    if name:
        key = str(name).strip().capitalize()
    else:
        debug_flag = os.getenv('DEBUG')
        if debug_flag is not None and str(debug_flag).strip() != '':
            key = 'Debug' if _env_bool('DEBUG', False) else 'Production'
        else:
            flask_env = (os.getenv('FLASK_ENV') or '').strip().lower()
            if flask_env in ('production', 'prod'):
                key = 'Production'
            else:
                key = 'Debug'

    if key not in config_dict:
        raise KeyError(f'Invalid config mode {key!r}. Expected Production or Debug.')

    cfg = config_dict[key]
    if key == 'Production':
        secret = os.getenv('SECRET_KEY')
        if not secret or len(secret.strip()) < 16:
            raise RuntimeError(
                'SECRET_KEY must be set to a strong value (16+ characters) in production. '
                'Add it to the environment or project .env before starting the app.'
            )
        cfg.SECRET_KEY = secret.strip()
    elif not cfg.SECRET_KEY:
        cfg.SECRET_KEY = ''.join(random.choice(string.ascii_lowercase) for _ in range(32))
    return cfg
