from datetime import datetime

from apps import db


class Shareholder(db.Model):
    __tablename__ = 'shareholders'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True, index=True)
    phone = db.Column(db.String(40), nullable=True)
    country = db.Column(db.String(80), nullable=True)
    country_code = db.Column(db.String(8), nullable=True)
    is_owner = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    investment_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    share_count = db.Column(db.Numeric(14, 4), nullable=False, default=0)
    investment_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    ownership_records = db.relationship(
        'OwnershipRecord',
        backref='shareholder',
        lazy='dynamic',
        order_by='OwnershipRecord.effective_from.desc()',
    )
    withdrawal_requests = db.relationship(
        'CapitalWithdrawalRequest',
        backref='shareholder',
        lazy='dynamic',
        order_by='CapitalWithdrawalRequest.requested_at.desc()',
    )

    def __repr__(self):
        return f'<Shareholder {self.name}>'


class OwnershipRecord(db.Model):
    __tablename__ = 'ownership_records'

    id = db.Column(db.Integer, primary_key=True)
    shareholder_id = db.Column(db.Integer, db.ForeignKey('shareholders.id'), nullable=False)
    ownership_percent = db.Column(db.Numeric(7, 4), nullable=False)
    effective_from = db.Column(db.Date, nullable=False)
    effective_to = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    created_by = db.relationship('User', foreign_keys=[created_by_id])


class CapitalWithdrawalRequest(db.Model):
    """Shareholder capital return request (up to 6 months per agreement)."""

    __tablename__ = 'capital_withdrawal_requests'

    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'

    STATUSES = (
        STATUS_PENDING,
        STATUS_APPROVED,
        STATUS_REJECTED,
        STATUS_COMPLETED,
        STATUS_CANCELLED,
    )

    id = db.Column(db.Integer, primary_key=True)
    shareholder_id = db.Column(db.Integer, db.ForeignKey('shareholders.id'), nullable=False)
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default=STATUS_PENDING)
    requested_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    deadline_at = db.Column(db.DateTime, nullable=False)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    review_notes = db.Column(db.Text, nullable=True)
    capital_return_date = db.Column(db.Date, nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    reviewed_by = db.relationship('User', foreign_keys=[reviewed_by_id])
    created_by = db.relationship('User', foreign_keys=[created_by_id])

    @property
    def is_open(self):
        return self.status in (self.STATUS_PENDING, self.STATUS_APPROVED)
