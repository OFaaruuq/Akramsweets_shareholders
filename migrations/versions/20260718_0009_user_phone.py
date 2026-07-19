"""Add phone column on users for staff WhatsApp.

Revision ID: 20260718_0009_user_phone
Revises: 20260715_0008_payment_status
Create Date: 2026-07-18
"""

from alembic import op
import sqlalchemy as sa


revision = '20260718_0009_user_phone'
down_revision = '20260715_0008_payment_status'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if 'users' not in tables:
        return

    cols = {c['name'] for c in inspector.get_columns('users')}
    if 'phone' not in cols:
        op.add_column('users', sa.Column('phone', sa.String(length=40), nullable=True))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'users' not in inspector.get_table_names():
        return
    cols = {c['name'] for c in inspector.get_columns('users')}
    if 'phone' in cols:
        op.drop_column('users', 'phone')
