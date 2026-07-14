"""Ensure database schema matches current models (development helper)."""

from sqlalchemy import inspect


REQUIRED_TABLES = {
    'users',
    'shareholders',
    'ownership_records',
    'special_arrangements',
    'monthly_periods',
    'shareholder_calculations',
    'shareholder_certificates',
    'manual_adjustments',
    'audit_logs',
    'system_settings',
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


def ensure_schema(app, db, seed_callback):
    with app.app_context():
        if schema_is_current(db):
            db.create_all()
            seed_callback()
            return

        if app.debug:
            print('> Database schema outdated - rebuilding tables (DEBUG mode).')
            reset_database(db)
            seed_callback()
            return

        raise RuntimeError(
            'Database schema is outdated. Stop the app, delete apps/db.sqlite3, and restart.'
        )
