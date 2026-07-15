"""Add full manual P&L statement fields on monthly periods.

Revision ID: 20260715_0003_pnl
Revises: 20260714_0002_selective
Create Date: 2026-07-15
"""

from alembic import op
import sqlalchemy as sa


revision = '20260715_0003_pnl'
down_revision = '20260714_0002_selective'
branch_labels = None
depends_on = None


NEW_COLUMNS = (
    ('income', sa.Numeric(14, 2), '0'),
    ('gross_profit', sa.Numeric(14, 2), '0'),
    ('total_gross_profit', sa.Numeric(14, 2), '0'),
    ('total_income', sa.Numeric(14, 2), '0'),
)


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'monthly_periods' not in inspector.get_table_names():
        return

    existing = {col['name'] for col in inspector.get_columns('monthly_periods')}
    for name, col_type, default in NEW_COLUMNS:
        if name in existing:
            continue
        op.add_column(
            'monthly_periods',
            sa.Column(name, col_type, nullable=False, server_default=default),
        )

    # Backfill from legacy breakdown fields where new columns are still zero.
    if {'income', 'gross_profit', 'total_gross_profit', 'total_income'}.issubset(
        existing.union({c[0] for c in NEW_COLUMNS})
    ):
        op.execute(
            """
            UPDATE monthly_periods
            SET
              income = CASE WHEN COALESCE(income, 0) = 0 THEN COALESCE(total_revenues, 0) ELSE income END,
              gross_profit = CASE
                WHEN COALESCE(gross_profit, 0) = 0
                THEN COALESCE(total_revenues, 0) - COALESCE(cost_of_goods, 0)
                ELSE gross_profit
              END,
              total_gross_profit = CASE
                WHEN COALESCE(total_gross_profit, 0) = 0
                THEN COALESCE(total_revenues, 0) - COALESCE(cost_of_goods, 0) + COALESCE(other_income, 0)
                ELSE total_gross_profit
              END,
              total_income = CASE
                WHEN COALESCE(total_income, 0) = 0
                THEN COALESCE(total_revenues, 0) + COALESCE(other_income, 0)
                ELSE total_income
              END
            """
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'monthly_periods' not in inspector.get_table_names():
        return
    existing = {col['name'] for col in inspector.get_columns('monthly_periods')}
    for name, _, _ in reversed(NEW_COLUMNS):
        if name in existing:
            op.drop_column('monthly_periods', name)
