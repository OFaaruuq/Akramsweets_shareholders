"""Add period payment status tracking.

Revision ID: 20260715_0008_payment_status
Revises: 20260715_0007_shareholder_reg
Create Date: 2026-07-15
"""

from alembic import op
import sqlalchemy as sa


revision = '20260715_0008_payment_status'
down_revision = '20260715_0007_shareholder_reg'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if 'monthly_periods' not in tables:
        return

    cols = {c['name'] for c in inspector.get_columns('monthly_periods')}
    additions = [
        ('payment_status', sa.Column('payment_status', sa.String(length=20), nullable=False, server_default='pending')),
        ('payment_completed_at', sa.Column('payment_completed_at', sa.DateTime(), nullable=True)),
        ('payment_completed_by_id', sa.Column('payment_completed_by_id', sa.Integer(), nullable=True)),
    ]
    for name, column in additions:
        if name not in cols:
            op.add_column('monthly_periods', column)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'monthly_periods' not in inspector.get_table_names():
        return
    cols = {c['name'] for c in inspector.get_columns('monthly_periods')}
    for name in ('payment_completed_by_id', 'payment_completed_at', 'payment_status'):
        if name in cols:
            op.drop_column('monthly_periods', name)
