from datetime import datetime

from apps import db


arrangement_source_shareholders = db.Table(
    'arrangement_source_shareholders',
    db.Column(
        'arrangement_id',
        db.Integer,
        db.ForeignKey('special_arrangements.id', ondelete='CASCADE'),
        primary_key=True,
    ),
    db.Column(
        'shareholder_id',
        db.Integer,
        db.ForeignKey('shareholders.id', ondelete='CASCADE'),
        primary_key=True,
    ),
)


class SpecialArrangement(db.Model):
    """Bonus: recipient receives extra % taken from selected (or all other) shareholders' base shares."""

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
    source_shareholders = db.relationship(
        'Shareholder',
        secondary=arrangement_source_shareholders,
        lazy='joined',
        order_by='Shareholder.name',
    )

    def source_ids(self):
        """Shareholder IDs that fund this bonus (empty when applies_to_all_others)."""
        return {shareholder.id for shareholder in self.source_shareholders}

    def source_label(self):
        if self.applies_to_all_others:
            return 'All other shareholders'
        names = [s.name for s in self.source_shareholders]
        return ', '.join(names) if names else 'No sources selected'

    def contributing_shareholder_ids(self, active_shareholder_ids):
        """IDs among active shareholders that should be deducted for this arrangement."""
        active = set(active_shareholder_ids)
        recipient_id = self.recipient_shareholder_id
        if self.applies_to_all_others:
            return {sid for sid in active if sid != recipient_id}
        return {sid for sid in self.source_ids() if sid in active and sid != recipient_id}
