"""Improve period approval workflow metadata.

Revision ID: 20260715_0006_approval
Revises: 20260715_0005_mudarabah
Create Date: 2026-07-15
"""

from alembic import op
import sqlalchemy as sa


revision = '20260715_0006_approval'
down_revision = '20260715_0005_mudarabah'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if 'monthly_periods' not in tables:
        return

    cols = {c['name'] for c in inspector.get_columns('monthly_periods')}
    # Integer columns only (no ALTER FK) so SQLite + Postgres both upgrade cleanly.
    # ORM still declares ForeignKey relationships on the model.
    additions = [
        ('submitted_for_review_at', sa.Column('submitted_for_review_at', sa.DateTime(), nullable=True)),
        ('submitted_for_review_by_id', sa.Column('submitted_for_review_by_id', sa.Integer(), nullable=True)),
        ('rejection_reason', sa.Column('rejection_reason', sa.Text(), nullable=True)),
        ('rejected_at', sa.Column('rejected_at', sa.DateTime(), nullable=True)),
        ('rejected_by_id', sa.Column('rejected_by_id', sa.Integer(), nullable=True)),
    ]
    for name, column in additions:
        if name not in cols:
            op.add_column('monthly_periods', column)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if 'monthly_periods' not in tables:
        return
    cols = {c['name'] for c in inspector.get_columns('monthly_periods')}
    for name in (
        'rejected_by_id',
        'rejected_at',
        'rejection_reason',
        'submitted_for_review_by_id',
        'submitted_for_review_at',
    ):
        if name in cols:
            op.drop_column('monthly_periods', name)
