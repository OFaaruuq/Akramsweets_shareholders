"""Ensure database schema matches current models.

Prefer Alembic migrations. Additive create_all fills gaps on first boot.
Destructive reset only when DEBUG and ALLOW_SCHEMA_RESET=true.
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError


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
        'year', 'month', 'total_profit_loss', 'income', 'gross_profit',
        'total_gross_profit', 'total_income', 'total_revenues', 'cost_of_goods',
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


def allow_schema_reset(app):
    flag = os.getenv('ALLOW_SCHEMA_RESET', 'false').strip().lower()
    return app.debug and flag in ('1', 'true', 'yes', 'on')


def _try_alembic_upgrade(app):
    versions_dir = migrations_dir() / 'versions'
    if not migrations_dir().is_dir():
        return False
    version_files = [p for p in versions_dir.glob('*.py') if p.name != '__init__.py']
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
        if not app.debug:
            raise
        return False


def _try_stamp_head(app):
    if not migrations_dir().is_dir() or 'migrate' not in app.extensions:
        return
    try:
        from flask_migrate import stamp

        stamp(revision='head')
    except Exception as exc:
        app.logger.warning('Alembic stamp skipped: %s', exc)


def _current_alembic_revision(db):
    try:
        tables = set(inspect(db.engine).get_table_names())
        if 'alembic_version' not in tables:
            return None
        with db.engine.connect() as conn:
            row = conn.execute(text('SELECT version_num FROM alembic_version')).fetchone()
        return row[0] if row else None
    except Exception:
        return None


def _set_alembic_revision(db, revision):
    """Force alembic_version to a known revision (used to repair renamed history)."""
    with db.engine.begin() as conn:
        tables = set(inspect(db.engine).get_table_names())
        if 'alembic_version' not in tables:
            conn.execute(text('CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)'))
            conn.execute(
                text('INSERT INTO alembic_version (version_num) VALUES (:rev)'),
                {'rev': revision},
            )
            return
        conn.execute(text('DELETE FROM alembic_version'))
        conn.execute(
            text('INSERT INTO alembic_version (version_num) VALUES (:rev)'),
            {'rev': revision},
        )


def _known_migration_revisions():
    """Revision ids present under migrations/versions (basename ids)."""
    versions = migrations_dir() / 'versions'
    if not versions.is_dir():
        return set()
    ids = set()
    for path in versions.glob('*.py'):
        if path.name.startswith('_'):
            continue
        try:
            text_src = path.read_text(encoding='utf-8')
        except OSError:
            continue
        for line in text_src.splitlines():
            if line.startswith('revision') and '=' in line:
                # revision = '20260715_0003_pnl'
                value = line.split('=', 1)[1].strip().strip("'\"")
                if value and value != 'None':
                    ids.add(value)
                break
    return ids


def _repair_orphaned_revision(app, db):
    """
    Older installs may be stamped with a pre-baseline / renamed revision id.
    If the live schema matches models, move alembic_version to head.
    """
    current = _current_alembic_revision(db)
    known = _known_migration_revisions()
    if current in known:
        return
    if not schema_is_current(db):
        return
    app.logger.warning(
        'Repairing Alembic revision %r → head (schema already matches models).',
        current,
    )
    try:
        _try_stamp_head(app)
        # Fallback if stamp is unavailable: write the newest known revision.
        repaired = _current_alembic_revision(db)
        if repaired not in known and known:
            head = sorted(known)[-1]
            _set_alembic_revision(db, head)
    except Exception as exc:
        app.logger.warning('Alembic revision repair skipped: %s', exc)


def ensure_schema(app, db, seed_callback):
    with app.app_context():
        try:
            inspector = inspect(db.engine)
            existing_tables = set(inspector.get_table_names())
        except OperationalError as exc:
            raise RuntimeError(
                'Cannot connect to the database. Check DATABASE_URL / DB_* settings, '
                'that PostgreSQL is running, and that credentials are correct.'
            ) from exc

        if not existing_tables:
            upgraded = _try_alembic_upgrade(app)
            if not upgraded or not schema_is_current(db):
                db.create_all()
                _try_stamp_head(app)
            seed_callback()
            return

        # Repair renamed revision ids before upgrade so flask db upgrade works.
        _repair_orphaned_revision(app, db)
        db.create_all()
        try:
            _try_alembic_upgrade(app)
        except Exception:
            if not app.debug:
                raise
        _repair_orphaned_revision(app, db)

        if schema_is_current(db):
            seed_callback()
            return

        if allow_schema_reset(app):
            app.logger.warning('Schema outdated — resetting because ALLOW_SCHEMA_RESET=true.')
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
            app.logger.warning(hint)
            seed_callback()
            return

        raise RuntimeError(hint)
