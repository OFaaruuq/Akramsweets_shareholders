from datetime import datetime

from apps import db


class SpecialArrangement(db.Model):
    """Owner bonus: recipient receives extra % taken from other shareholders' base shares."""

    __tablename__ = 'special_arrangements'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    recipient_shareholder_id = db.Column(db.Integer, db.ForeignKey('shareholders.id'), nullable=False)
    bonus_percent = db.Column(db.Numeric(7, 4), nullable=False)
    applies_to_all_others = db.Column(db.Boolean, default=True, nullable=False)
    apply_on_profit = db.Column(db.Boolean, default=True, nullable=False)
    apply_on_loss = db.Column(db.Boolean, default=True, nullable=False)
    effective_from = db.Column(db.Date, nullable=False)
    effective_to = db.Column(db.Date, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    recipient = db.relationship('Shareholder', foreign_keys=[recipient_shareholder_id])
