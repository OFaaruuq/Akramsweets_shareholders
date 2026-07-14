from datetime import datetime

from apps import db


class SystemSetting(db.Model):
    __tablename__ = 'system_settings'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def get(key, default=None):
        row = SystemSetting.query.filter_by(key=key).first()
        return row.value if row else default

    @staticmethod
    def set(key, value):
        row = SystemSetting.query.filter_by(key=key).first()
        if row:
            row.value = value
        else:
            row = SystemSetting(key=key, value=value)
            db.session.add(row)
        db.session.commit()
        return row
