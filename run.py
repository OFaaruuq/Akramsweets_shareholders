# -*- encoding: utf-8 -*-
"""WSGI / CLI entrypoint for Akram Sweets Shareholders."""

import os
from sys import exit

from dotenv import load_dotenv

_ROOT = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(_ROOT, '.env'))

from flask_minify import Minify

from apps.config import redact_database_uri, resolve_config
from apps import create_app

try:
    app_config = resolve_config()
except (KeyError, RuntimeError) as exc:
    exit(f'Error: {exc}')

app = create_app(app_config)
DEBUG = bool(getattr(app_config, 'DEBUG', False))

if not DEBUG:
    Minify(app=app, html=True, js=False, cssless=False)

if DEBUG:
    app.logger.info('DEBUG            = %s', DEBUG)
    app.logger.info('Page Compression = FALSE')
    app.logger.info('DBMS             = %s', redact_database_uri(app_config.SQLALCHEMY_DATABASE_URI))
    app.logger.info('ASSETS_ROOT      = %s', app_config.ASSETS_ROOT)

if __name__ == '__main__':
    app.run()
