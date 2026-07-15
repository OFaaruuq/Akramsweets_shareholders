# -*- encoding: utf-8 -*-
"""WSGI entrypoint for gunicorn / waitress / reverse proxies.

Usage:
  gunicorn wsgi:app
  gunicorn run:app   # also works; prefer wsgi:app in production
"""

from run import app  # noqa: F401
