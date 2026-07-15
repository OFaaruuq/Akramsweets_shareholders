"""Baseline schema for Akram Sweets Shareholders.

Revision ID: 20260714_0001_baseline
Revises:
Create Date: 2026-07-14

Creates all core tables when missing so `flask db upgrade` works on a clean database.
"""

from alembic import op
import sqlalchemy as sa


revision = '20260714_0001_baseline'
down_revision = None
branch_labels = None
depends_on = None


def _tables(bind):
    return set(sa.inspect(bind).get_table_names())


def upgrade():
    bind = op.get_bind()
    tables = _tables(bind)

    if 'shareholders' not in tables:
        op.create_table(
            'shareholders',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', sa.String(length=120), nullable=False),
            sa.Column('email', sa.String(length=120), nullable=False),
            sa.Column('phone', sa.String(length=40), nullable=True),
            sa.Column('country', sa.String(length=80), nullable=True),
            sa.Column('country_code', sa.String(length=8), nullable=True),
            sa.Column('is_owner', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
        )
        tables.add('shareholders')

    if 'users' not in tables:
        op.create_table(
            'users',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('email', sa.String(length=120), nullable=False),
            sa.Column('password_hash', sa.String(length=256), nullable=False),
            sa.Column('full_name', sa.String(length=120), nullable=False),
            sa.Column('role', sa.String(length=20), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('shareholder_id', sa.Integer(), sa.ForeignKey('shareholders.id'), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
        )
        op.create_index('ix_users_email', 'users', ['email'], unique=True)
        tables.add('users')

    if 'ownership_records' not in tables:
        op.create_table(
            'ownership_records',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('shareholder_id', sa.Integer(), sa.ForeignKey('shareholders.id'), nullable=False),
            sa.Column('ownership_percent', sa.Numeric(7, 4), nullable=False),
            sa.Column('effective_from', sa.Date(), nullable=False),
            sa.Column('effective_to', sa.Date(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        )

    if 'special_arrangements' not in tables:
        op.create_table(
            'special_arrangements',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', sa.String(length=120), nullable=False),
            sa.Column('recipient_shareholder_id', sa.Integer(), sa.ForeignKey('shareholders.id'), nullable=False),
            sa.Column('bonus_percent', sa.Numeric(7, 4), nullable=False),
            sa.Column('applies_to_all_others', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('apply_on_profit', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('apply_on_loss', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('effective_from', sa.Date(), nullable=False),
            sa.Column('effective_to', sa.Date(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
        )

    if 'monthly_periods' not in tables:
        op.create_table(
            'monthly_periods',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('year', sa.Integer(), nullable=False),
            sa.Column('month', sa.Integer(), nullable=False),
            sa.Column('total_profit_loss', sa.Numeric(14, 2), nullable=False, server_default='0'),
            sa.Column('income', sa.Numeric(14, 2), nullable=False, server_default='0'),
            sa.Column('gross_profit', sa.Numeric(14, 2), nullable=False, server_default='0'),
            sa.Column('total_gross_profit', sa.Numeric(14, 2), nullable=False, server_default='0'),
            sa.Column('total_income', sa.Numeric(14, 2), nullable=False, server_default='0'),
            sa.Column('total_revenues', sa.Numeric(14, 2), nullable=False, server_default='0'),
            sa.Column('cost_of_goods', sa.Numeric(14, 2), nullable=False, server_default='0'),
            sa.Column('total_expenses', sa.Numeric(14, 2), nullable=False, server_default='0'),
            sa.Column('other_income', sa.Numeric(14, 2), nullable=False, server_default='0'),
            sa.Column('entry_mode', sa.String(length=20), nullable=False, server_default='pnl'),
            sa.Column('odoo_reference', sa.String(length=255), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'),
            sa.Column('calculated_at', sa.DateTime(), nullable=True),
            sa.Column('approved_at', sa.DateTime(), nullable=True),
            sa.Column('approved_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('reports_sent_at', sa.DateTime(), nullable=True),
            sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
        )

    if 'shareholder_calculations' not in tables:
        op.create_table(
            'shareholder_calculations',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('period_id', sa.Integer(), sa.ForeignKey('monthly_periods.id'), nullable=False),
            sa.Column('shareholder_id', sa.Integer(), sa.ForeignKey('shareholders.id'), nullable=False),
            sa.Column('ownership_percent', sa.Numeric(7, 4), nullable=False),
            sa.Column('base_share', sa.Numeric(14, 2), nullable=False, server_default='0'),
            sa.Column('arrangement_deduction', sa.Numeric(14, 2), nullable=False, server_default='0'),
            sa.Column('arrangement_received', sa.Numeric(14, 2), nullable=False, server_default='0'),
            sa.Column('manual_adjustment', sa.Numeric(14, 2), nullable=False, server_default='0'),
            sa.Column('final_amount', sa.Numeric(14, 2), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(), nullable=False),
        )

    if 'manual_adjustments' not in tables:
        op.create_table(
            'manual_adjustments',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('period_id', sa.Integer(), sa.ForeignKey('monthly_periods.id'), nullable=False),
            sa.Column('shareholder_id', sa.Integer(), sa.ForeignKey('shareholders.id'), nullable=False),
            sa.Column('amount', sa.Numeric(14, 2), nullable=False),
            sa.Column('reason', sa.Text(), nullable=False),
            sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
        )

    if 'shareholder_certificates' not in tables:
        op.create_table(
            'shareholder_certificates',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('period_id', sa.Integer(), sa.ForeignKey('monthly_periods.id'), nullable=False),
            sa.Column('shareholder_id', sa.Integer(), sa.ForeignKey('shareholders.id'), nullable=False),
            sa.Column('certificate_number', sa.String(length=64), nullable=False),
            sa.Column('generated_at', sa.DateTime(), nullable=False),
            sa.Column('emailed_at', sa.DateTime(), nullable=True),
            sa.Column('email_status', sa.String(length=20), nullable=False, server_default='pending'),
            sa.UniqueConstraint('certificate_number'),
            sa.UniqueConstraint('period_id', 'shareholder_id', name='uq_certificate_period_shareholder'),
        )

    if 'audit_logs' not in tables:
        op.create_table(
            'audit_logs',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('action', sa.String(length=80), nullable=False),
            sa.Column('entity_type', sa.String(length=80), nullable=False),
            sa.Column('entity_id', sa.Integer(), nullable=True),
            sa.Column('details', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
        )

    if 'system_settings' not in tables:
        op.create_table(
            'system_settings',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('key', sa.String(length=80), nullable=False),
            sa.Column('value', sa.Text(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.UniqueConstraint('key'),
        )

    if 'todo_dismissals' not in tables:
        op.create_table(
            'todo_dismissals',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('source_key', sa.String(length=120), nullable=False),
            sa.Column('dismissed_at', sa.DateTime(), nullable=False),
            sa.Column('dismissed_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        )
        op.create_index('ix_todo_dismissals_source_key', 'todo_dismissals', ['source_key'], unique=True)

    if 'login_otps' not in tables:
        op.create_table(
            'login_otps',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('code_hash', sa.String(length=128), nullable=False),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('consumed_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
        )
        op.create_index('ix_login_otps_user_id', 'login_otps', ['user_id'])


def downgrade():
    # Destructive full downgrade is intentionally not supported for baseline.
    pass
