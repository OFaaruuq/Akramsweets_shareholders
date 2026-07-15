"""Unique shareholder email + index for registration integrity.

Revision ID: 20260715_0007_shareholder_reg
Revises: 20260715_0006_approval
Create Date: 2026-07-15
"""

from alembic import op
import sqlalchemy as sa


revision = '20260715_0007_shareholder_reg'
down_revision = '20260715_0006_approval'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if 'shareholders' not in tables:
        return

    # Deduplicate emails before unique index (keep lowest id).
    rows = bind.execute(sa.text('SELECT id, lower(email) AS email FROM shareholders ORDER BY id')).fetchall()
    seen = {}
    for row in rows:
        email = (row.email or '').strip().lower()
        if not email:
            continue
        if email in seen:
            # Rename duplicate so unique constraint can apply
            new_email = f'duplicate-{row.id}-{email}'
            if len(new_email) > 120:
                new_email = new_email[:120]
            bind.execute(
                sa.text('UPDATE shareholders SET email = :email WHERE id = :id'),
                {'email': new_email, 'id': row.id},
            )
        else:
            seen[email] = row.id
            bind.execute(
                sa.text('UPDATE shareholders SET email = :email WHERE id = :id'),
                {'email': email, 'id': row.id},
            )

    indexes = {idx['name'] for idx in inspector.get_indexes('shareholders')}
    if 'ix_shareholders_email' not in indexes and 'uq_shareholders_email' not in indexes:
        try:
            op.create_index('ix_shareholders_email', 'shareholders', ['email'], unique=True)
        except Exception:
            # Some dialects already have a unique constraint under another name
            pass


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'shareholders' not in inspector.get_table_names():
        return
    indexes = {idx['name'] for idx in inspector.get_indexes('shareholders')}
    if 'ix_shareholders_email' in indexes:
        op.drop_index('ix_shareholders_email', table_name='shareholders')
