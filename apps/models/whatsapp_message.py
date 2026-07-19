"""Persisted Twilio WhatsApp outbound / inbound messages for delivery tracking."""

from datetime import datetime

from apps import db


class WhatsAppMessage(db.Model):
    __tablename__ = 'whatsapp_messages'

    DIRECTION_OUTBOUND = 'outbound'
    DIRECTION_INBOUND = 'inbound'

    id = db.Column(db.Integer, primary_key=True)
    direction = db.Column(db.String(20), nullable=False, default=DIRECTION_OUTBOUND, index=True)
    twilio_sid = db.Column(db.String(64), nullable=True, index=True)
    from_address = db.Column(db.String(64), nullable=True)
    to_address = db.Column(db.String(64), nullable=True, index=True)
    body = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(40), nullable=True, index=True)
    error_code = db.Column(db.String(40), nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    event_key = db.Column(db.String(60), nullable=True, index=True)
    media_urls = db.Column(db.Text, nullable=True)
    content_sid = db.Column(db.String(64), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    shareholder_id = db.Column(db.Integer, db.ForeignKey('shareholders.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = db.relationship('User', foreign_keys=[user_id])
    shareholder = db.relationship('Shareholder', foreign_keys=[shareholder_id])
