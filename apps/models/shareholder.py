from datetime import datetime

from apps import db


class Shareholder(db.Model):
    __tablename__ = 'shareholders'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(40), nullable=True)
    country = db.Column(db.String(80), nullable=True)
    country_code = db.Column(db.String(8), nullable=True)
    is_owner = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    ownership_records = db.relationship(
        'OwnershipRecord',
        backref='shareholder',
        lazy='dynamic',
        order_by='OwnershipRecord.effective_from.desc()',
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
