"""WhatsApp message delivery log.

Revision ID: 20260719_0010_whatsapp_messages
Revises: 20260718_0009_user_phone
Create Date: 2026-07-19
"""

from alembic import op
import sqlalchemy as sa


revision = '20260719_0010_whatsapp_messages'
down_revision = '20260718_0009_user_phone'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'whatsapp_messages' in set(inspector.get_table_names()):
        return

    op.create_table(
        'whatsapp_messages',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('direction', sa.String(length=20), nullable=False),
        sa.Column('twilio_sid', sa.String(length=64), nullable=True),
        sa.Column('from_address', sa.String(length=64), nullable=True),
        sa.Column('to_address', sa.String(length=64), nullable=True),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=40), nullable=True),
        sa.Column('error_code', sa.String(length=40), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('event_key', sa.String(length=60), nullable=True),
        sa.Column('media_urls', sa.Text(), nullable=True),
        sa.Column('content_sid', sa.String(length=64), nullable=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('shareholder_id', sa.Integer(), sa.ForeignKey('shareholders.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_whatsapp_messages_direction', 'whatsapp_messages', ['direction'])
    op.create_index('ix_whatsapp_messages_twilio_sid', 'whatsapp_messages', ['twilio_sid'])
    op.create_index('ix_whatsapp_messages_to_address', 'whatsapp_messages', ['to_address'])
    op.create_index('ix_whatsapp_messages_status', 'whatsapp_messages', ['status'])
    op.create_index('ix_whatsapp_messages_event_key', 'whatsapp_messages', ['event_key'])
    op.create_index('ix_whatsapp_messages_created_at', 'whatsapp_messages', ['created_at'])


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'whatsapp_messages' not in set(inspector.get_table_names()):
        return
    op.drop_table('whatsapp_messages')
