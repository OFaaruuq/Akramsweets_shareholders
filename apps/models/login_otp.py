from datetime import datetime, timedelta
import hashlib
import hmac
import secrets

from apps import db


class LoginOTP(db.Model):
    """One-time password issued after a successful password check at login."""

    __tablename__ = 'login_otps'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    code_hash = db.Column(db.String(128), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    consumed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', foreign_keys=[user_id])

    @staticmethod
    def hash_code(code: str) -> str:
        return hashlib.sha256(code.encode('utf-8')).hexdigest()

    def matches(self, code: str) -> bool:
        return hmac.compare_digest(self.code_hash, self.hash_code(code.strip()))

    def is_expired(self) -> bool:
        return datetime.utcnow() >= self.expires_at

    def is_usable(self) -> bool:
        return self.consumed_at is None and not self.is_expired()
