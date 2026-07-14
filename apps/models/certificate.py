from datetime import datetime

from apps import db


class ShareholderCertificate(db.Model):
    __tablename__ = 'shareholder_certificates'

    id = db.Column(db.Integer, primary_key=True)
    period_id = db.Column(db.Integer, db.ForeignKey('monthly_periods.id'), nullable=False)
    shareholder_id = db.Column(db.Integer, db.ForeignKey('shareholders.id'), nullable=False)
    certificate_number = db.Column(db.String(64), nullable=False, unique=True)
    generated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    emailed_at = db.Column(db.DateTime, nullable=True)
    email_status = db.Column(db.String(20), nullable=False, default='pending')

    period = db.relationship('MonthlyPeriod')
    shareholder = db.relationship('Shareholder')

    __table_args__ = (
        db.UniqueConstraint('period_id', 'shareholder_id', name='uq_certificate_period_shareholder'),
    )
