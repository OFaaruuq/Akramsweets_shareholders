from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from apps import db


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    ROLE_OWNER = 'owner'
    ROLE_FINANCE = 'finance'
    ROLE_ADMIN = 'admin'
    ROLE_SHAREHOLDER = 'shareholder'

    ROLES = (ROLE_OWNER, ROLE_FINANCE, ROLE_ADMIN, ROLE_SHAREHOLDER)

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=ROLE_FINANCE)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    shareholder_id = db.Column(db.Integer, db.ForeignKey('shareholders.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    shareholder = db.relationship('Shareholder', backref=db.backref('user_account', uselist=False))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_management(self):
        return self.role in (self.ROLE_OWNER, self.ROLE_ADMIN)

    def can_manage_rules(self):
        return self.role in (self.ROLE_OWNER, self.ROLE_ADMIN)

    def can_approve_periods(self):
        return self.role in (self.ROLE_OWNER, self.ROLE_ADMIN)

    def can_edit_shareholders(self):
        return self.role in (self.ROLE_OWNER, self.ROLE_ADMIN)

    def can_enter_financials(self):
        return self.role in (self.ROLE_OWNER, self.ROLE_ADMIN, self.ROLE_FINANCE)

    def can_manage_users(self):
        return self.role in (self.ROLE_OWNER, self.ROLE_ADMIN)

    def can_view_audit_log(self):
        return self.role in (self.ROLE_OWNER, self.ROLE_ADMIN)

    def is_shareholder(self):
        return self.role == self.ROLE_SHAREHOLDER and self.shareholder_id is not None

    def home_endpoint(self):
        return 'pages.dashboard'
