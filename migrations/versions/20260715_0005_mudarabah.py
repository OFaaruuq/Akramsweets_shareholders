"""Mudarabah 50/50 pools, shareholder capital fields, withdrawal requests.

Revision ID: 20260715_0005_mudarabah
Revises: 20260715_0004_avatar
Create Date: 2026-07-15
"""

from alembic import op
import sqlalchemy as sa


revision = '20260715_0005_mudarabah'
down_revision = '20260715_0004_avatar'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if 'monthly_periods' in tables:
        cols = {c['name'] for c in inspector.get_columns('monthly_periods')}
        if 'shareholders_pool' not in cols:
            op.add_column(
                'monthly_periods',
                sa.Column('shareholders_pool', sa.Numeric(14, 2), nullable=False, server_default='0'),
            )
        if 'managing_partner_share' not in cols:
            op.add_column(
                'monthly_periods',
                sa.Column('managing_partner_share', sa.Numeric(14, 2), nullable=False, server_default='0'),
            )
        if 'mudarabah_shareholder_percent' not in cols:
            op.add_column(
                'monthly_periods',
                sa.Column(
                    'mudarabah_shareholder_percent',
                    sa.Numeric(7, 4),
                    nullable=False,
                    server_default='50',
                ),
            )
        # Backfill: existing periods treated as pre-Mudarabah full distribution →
        # set pool = net, partner = 0 for historical rows that already distributed 100%.
        # New calcs will overwrite with 50/50. Prefer documenting; for new installs default 0.
        op.execute(
            """
            UPDATE monthly_periods
            SET shareholders_pool = COALESCE(total_profit_loss, 0),
                managing_partner_share = 0,
                mudarabah_shareholder_percent = 50
            WHERE COALESCE(shareholders_pool, 0) = 0
              AND COALESCE(managing_partner_share, 0) = 0
            """
        )

    if 'shareholders' in tables:
        cols = {c['name'] for c in inspector.get_columns('shareholders')}
        if 'investment_amount' not in cols:
            op.add_column(
                'shareholders',
                sa.Column('investment_amount', sa.Numeric(14, 2), nullable=False, server_default='0'),
            )
        if 'share_count' not in cols:
            op.add_column(
                'shareholders',
                sa.Column('share_count', sa.Numeric(14, 4), nullable=False, server_default='0'),
            )
        if 'investment_date' not in cols:
            op.add_column('shareholders', sa.Column('investment_date', sa.Date(), nullable=True))

    if 'capital_withdrawal_requests' not in tables:
        op.create_table(
            'capital_withdrawal_requests',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('shareholder_id', sa.Integer(), sa.ForeignKey('shareholders.id'), nullable=False),
            sa.Column('amount', sa.Numeric(14, 2), nullable=False),
            sa.Column('reason', sa.Text(), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
            sa.Column('requested_at', sa.DateTime(), nullable=False),
            sa.Column('deadline_at', sa.DateTime(), nullable=False),
            sa.Column('reviewed_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('reviewed_at', sa.DateTime(), nullable=True),
            sa.Column('review_notes', sa.Text(), nullable=True),
            sa.Column('capital_return_date', sa.Date(), nullable=True),
            sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if 'capital_withdrawal_requests' in tables:
        op.drop_table('capital_withdrawal_requests')

    if 'shareholders' in tables:
        cols = {c['name'] for c in inspector.get_columns('shareholders')}
        for name in ('investment_date', 'share_count', 'investment_amount'):
            if name in cols:
                op.drop_column('shareholders', name)

    if 'monthly_periods' in tables:
        cols = {c['name'] for c in inspector.get_columns('monthly_periods')}
        for name in (
            'mudarabah_shareholder_percent',
            'managing_partner_share',
            'shareholders_pool',
        ):
            if name in cols:
                op.drop_column('monthly_periods', name)
