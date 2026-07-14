from datetime import datetime

from apps import db


class TodoDismissal(db.Model):
    """Tracks dismissed workflow todos so they stay hidden until the issue is resolved."""

    __tablename__ = 'todo_dismissals'

    id = db.Column(db.Integer, primary_key=True)
    source_key = db.Column(db.String(120), unique=True, nullable=False, index=True)
    dismissed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    dismissed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    dismissed_by = db.relationship('User', foreign_keys=[dismissed_by_id])
