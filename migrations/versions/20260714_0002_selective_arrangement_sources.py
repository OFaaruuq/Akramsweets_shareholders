"""Add selective arrangement source shareholders.

Revision ID: 20260714_0002_selective
Revises: 20260714_0001_baseline
Create Date: 2026-07-14
"""

from alembic import op
import sqlalchemy as sa


revision = '20260714_0002_selective'
down_revision = '20260714_0001_baseline'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if 'arrangement_source_shareholders' not in tables:
        op.create_table(
            'arrangement_source_shareholders',
            sa.Column('arrangement_id', sa.Integer(), nullable=False),
            sa.Column('shareholder_id', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(
                ['arrangement_id'],
                ['special_arrangements.id'],
                ondelete='CASCADE',
            ),
            sa.ForeignKeyConstraint(
                ['shareholder_id'],
                ['shareholders.id'],
                ondelete='CASCADE',
            ),
            sa.PrimaryKeyConstraint('arrangement_id', 'shareholder_id'),
        )


def downgrade():
    bind = op.get_bind()
    if 'arrangement_source_shareholders' in set(sa.inspect(bind).get_table_names()):
        op.drop_table('arrangement_source_shareholders')
