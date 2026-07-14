# -*- encoding: utf-8 -*-

import os
import random
import string

from dotenv import load_dotenv

load_dotenv()


def _normalize_database_url(url):
    """Render/Heroku may provide postgres://; SQLAlchemy expects postgresql://."""
    if url.startswith('postgres://'):
        return url.replace('postgres://', 'postgresql+psycopg2://', 1)
    return url


def build_database_uri(basedir):
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        return _normalize_database_url(database_url)

    db_engine = os.getenv('DB_ENGINE', 'sqlite').lower()

    if db_engine in ('sqlite', 'sqlite3'):
        db_file = os.getenv('SQLITE_PATH', os.path.join(basedir, 'db.sqlite3'))
        return 'sqlite:///' + db_file

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

    GITHUB_ID = os.getenv('GITHUB_ID', None)
    GITHUB_SECRET = os.getenv('GITHUB_SECRET', None)

    if GITHUB_ID and GITHUB_SECRET:
        SOCIAL_AUTH_GITHUB = True

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = build_database_uri(basedir)
    WTF_CSRF_ENABLED = True

    # SMTP (optional). Prefer System Settings UI; env vars are the fallback.
    MAIL_SERVER = os.getenv('MAIL_SERVER') or None
    MAIL_PORT = int(os.getenv('MAIL_PORT', '587'))
    MAIL_USERNAME = os.getenv('MAIL_USERNAME') or None
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD') or None
    MAIL_FROM = os.getenv('MAIL_FROM') or None


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
