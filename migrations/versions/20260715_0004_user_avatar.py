"""Add avatar_path to users for profile images.

Revision ID: 20260715_0004_avatar
Revises: 20260715_0003_pnl
Create Date: 2026-07-15
"""

from alembic import op
import sqlalchemy as sa


revision = '20260715_0004_avatar'
down_revision = '20260715_0003_pnl'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'users' not in inspector.get_table_names():
        return
    existing = {col['name'] for col in inspector.get_columns('users')}
    if 'avatar_path' not in existing:
        op.add_column('users', sa.Column('avatar_path', sa.String(length=255), nullable=True))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'users' not in inspector.get_table_names():
        return
    existing = {col['name'] for col in inspector.get_columns('users')}
    if 'avatar_path' in existing:
        op.drop_column('users', 'avatar_path')
