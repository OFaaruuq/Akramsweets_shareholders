# -*- encoding: utf-8 -*-

import os
import random
import string

from dotenv import load_dotenv

# Load .env files without overriding process env (tests / shell exports always win).
# Workspace .env first, then project .env fills any remaining keys.
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
_WORKSPACE_ROOT = os.path.abspath(os.path.join(_PROJECT_ROOT, '..'))
load_dotenv(os.path.join(_WORKSPACE_ROOT, '.env'))
load_dotenv(os.path.join(_PROJECT_ROOT, '.env'))


def _env_bool(name, default=False):
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in ('1', 'true', 'yes', 'on')


def _normalize_database_url(url):
    """Render/Heroku may provide postgres://; SQLAlchemy expects postgresql+psycopg2://."""
    if url.startswith('postgres://'):
        return url.replace('postgres://', 'postgresql+psycopg2://', 1)
    if url.startswith('postgresql://') and '+psycopg2' not in url:
        return url.replace('postgresql://', 'postgresql+psycopg2://', 1)
    return url


def build_database_uri(basedir):
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        return _normalize_database_url(database_url)

    db_engine = os.getenv('DB_ENGINE', 'postgresql+psycopg2').lower()

    if db_engine in ('sqlite', 'sqlite3'):
        db_file = os.getenv('SQLITE_PATH', os.path.join(basedir, 'db.sqlite3'))
        return 'sqlite:///' + db_file

    # Accept shorthand values from .env / Render
    if db_engine in ('postgres', 'postgresql', 'pgsql'):
        db_engine = 'postgresql+psycopg2'
    elif db_engine == 'postgresql+psycopg2' or db_engine.startswith('postgresql'):
        pass
    else:
        # Unknown engine — default to PostgreSQL
        db_engine = 'postgresql+psycopg2'

    db_username = os.getenv('DB_USERNAME', 'akram_user')
    db_pass = os.getenv('DB_PASS', 'akram_pass')
    db_host = os.getenv('DB_HOST', '127.0.0.1')
    db_port = os.getenv('DB_PORT', '5432')
    db_name = os.getenv('DB_NAME', 'akram_shareholders')

    auth = f'{db_username}:{db_pass}' if db_pass else db_username
    return f'{db_engine}://{auth}@{db_host}:{db_port}/{db_name}'


class Config(object):

    basedir = os.path.abspath(os.path.dirname(__file__))

    ASSETS_ROOT = os.getenv('ASSETS_ROOT', '/static')

    SECRET_KEY = os.getenv('SECRET_KEY', None)
    if not SECRET_KEY:
        SECRET_KEY = ''.join(random.choice(string.ascii_lowercase) for i in range(32))

    SOCIAL_AUTH_GITHUB = False
    GITHUB_ID = None
    GITHUB_SECRET = None

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = build_database_uri(basedir)
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }
    WTF_CSRF_ENABLED = True

    # SMTP — used for login OTP and shareholder report emails
    MAIL_SERVER = os.getenv('MAIL_SERVER') or None
    MAIL_PORT = int(os.getenv('MAIL_PORT', '587'))
    MAIL_USERNAME = os.getenv('MAIL_USERNAME') or None
    # Strip spaces from Gmail app passwords pasted with grouping
    _mail_password = os.getenv('MAIL_PASSWORD')
    MAIL_PASSWORD = ''.join(_mail_password.split()) if _mail_password else None
    MAIL_FROM = os.getenv('MAIL_FROM') or os.getenv('MAIL_DEFAULT_SENDER') or None
    MAIL_DEFAULT_SENDER = MAIL_FROM
    MAIL_USE_TLS = _env_bool('MAIL_USE_TLS', True)

    # Login email OTP (required by default)
    LOGIN_OTP_ENABLED = _env_bool('LOGIN_OTP_ENABLED', True)
    OTP_LENGTH = int(os.getenv('OTP_LENGTH', '6'))
    OTP_EXPIRY_MINUTES = int(os.getenv('OTP_EXPIRY_MINUTES', '10'))
    OTP_MAX_ATTEMPTS = int(os.getenv('OTP_MAX_ATTEMPTS', '5'))
    OTP_TEST_CAPTURE = _env_bool('OTP_TEST_CAPTURE', False)


class ProductionConfig(Config):
    DEBUG = False

    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_DURATION = 3600


class DebugConfig(Config):
    DEBUG = True


config_dict = {
    'Production': ProductionConfig,
    'Debug': DebugConfig
}
