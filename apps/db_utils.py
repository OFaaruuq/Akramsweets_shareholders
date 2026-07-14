"""Ensure database schema matches current models.

Prefer Alembic migrations when available. Additive `create_all()` fills missing
tables. Destructive reset only when DEBUG and ALLOW_SCHEMA_RESET=true.
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import inspect


REQUIRED_TABLES = {
    'users',
    'shareholders',
    'ownership_records',
    'special_arrangements',
    'arrangement_source_shareholders',
    'monthly_periods',
    'shareholder_calculations',
    'shareholder_certificates',
    'manual_adjustments',
    'audit_logs',
    'system_settings',
    'todo_dismissals',
    'login_otps',
}

REQUIRED_COLUMNS = {
    'monthly_periods': {
        'year', 'month', 'total_profit_loss', 'total_revenues', 'cost_of_goods',
        'total_expenses', 'other_income', 'entry_mode', 'status', 'calculated_at',
        'approved_at', 'approved_by_id', 'reports_sent_at',
    },
    'shareholders': {
        'name', 'email', 'phone', 'country', 'country_code', 'is_owner', 'is_active',
    },
    'special_arrangements': {
        'name', 'recipient_shareholder_id', 'bonus_percent', 'applies_to_all_others',
    },
}


def schema_is_current(db):
    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names())
    if not REQUIRED_TABLES.issubset(tables):
        return False

    for table, columns in REQUIRED_COLUMNS.items():
        existing = {col['name'] for col in inspector.get_columns(table)}
        if not columns.issubset(existing):
            return False

    return True


def reset_database(db):
    db.drop_all()
    db.create_all()


def migrations_dir():
    return Path(__file__).resolve().parent.parent / 'migrations'


def _try_alembic_upgrade(app):
    """Apply pending Alembic revisions when a migrations folder exists."""
    versions_dir = migrations_dir() / 'versions'
    if not migrations_dir().is_dir():
        return False
    version_files = [
        path for path in versions_dir.glob('*.py')
        if path.name != '__init__.py'
    ]
    if not version_files:
        return False
    if 'migrate' not in app.extensions:
        app.logger.warning('Alembic upgrade skipped: Flask-Migrate is not initialized.')
        return False
    try:
        from flask_migrate import upgrade

        upgrade()
        return True
    except Exception as exc:
        app.logger.warning('Alembic upgrade skipped: %s', exc)
        return False


def _try_stamp_head(app):
    """Mark an already-created schema as current without re-running DDL."""
    if not migrations_dir().is_dir():
        return
    try:
        from flask_migrate import stamp

        stamp(revision='head')
    except Exception as exc:
        app.logger.warning('Alembic stamp skipped: %s', exc)


def allow_schema_reset(app):
    flag = os.getenv('ALLOW_SCHEMA_RESET', 'false').strip().lower()
    return app.debug and flag in ('1', 'true', 'yes', 'on')


def ensure_schema(app, db, seed_callback):
    with app.app_context():
        inspector = inspect(db.engine)
        existing_tables = set(inspector.get_table_names())

        if not existing_tables:
            db.create_all()
            _try_alembic_upgrade(app)
            _try_stamp_head(app)
            seed_callback()
            return

        # Additive: create any newly added tables (e.g. junction tables).
        db.create_all()
        _try_alembic_upgrade(app)

        if schema_is_current(db):
            seed_callback()
            return

        if allow_schema_reset(app):
            print('> Database schema outdated — resetting because ALLOW_SCHEMA_RESET=true.')
            reset_database(db)
            _try_stamp_head(app)
            seed_callback()
            return

        missing_tables = sorted(REQUIRED_TABLES - set(inspect(db.engine).get_table_names()))
        hint = (
            'Database schema is outdated. '
            'Run: flask --app run.py db upgrade '
            'or (DEBUG only) set ALLOW_SCHEMA_RESET=true once to rebuild. '
            f'Missing tables: {", ".join(missing_tables) or "column mismatch"}.'
        )
        if app.debug:
            print(f'> WARNING: {hint}')
            # Soft-continue in DEBUG after create_all so local work is not blocked
            # when only optional columns differ — still seed.
            seed_callback()
            return

        raise RuntimeError(hint)
