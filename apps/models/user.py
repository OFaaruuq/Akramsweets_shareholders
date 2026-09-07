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

    ROLE_LABELS = {
        ROLE_OWNER: 'Super Admin (Owner)',
        ROLE_ADMIN: 'System Administrator',
        ROLE_FINANCE: 'Finance / Accounts',
        ROLE_SHAREHOLDER: 'Shareholder',
    }

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(40), nullable=True)
    role = db.Column(db.String(20), nullable=False, default=ROLE_FINANCE)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    shareholder_id = db.Column(db.Integer, db.ForeignKey('shareholders.id'), nullable=True)
    avatar_path = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    shareholder = db.relationship('Shareholder', backref=db.backref('user_account', uselist=False))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def avatar_url(self):
        from apps.services.avatar_service import user_avatar_url

        return user_avatar_url(self)

    @property
    def has_custom_avatar(self):
        from apps.services.avatar_service import user_has_custom_avatar

        return user_has_custom_avatar(self)

    @property
    def role_label(self):
        return self.ROLE_LABELS.get(self.role, (self.role or 'user').replace('_', ' ').title())

    def is_company_owner_account(self):
        """Linked to an active Company Owner shareholder on the capital register."""
        sh = self.shareholder
        return bool(sh is not None and sh.is_owner and sh.is_active)

    def is_superadmin(self):
        """Full Super Admin: staff Owner role, or Company Owner shareholder login."""
        if self.role == self.ROLE_OWNER:
            return True
        return self.is_company_owner_account()

    def is_owner_user(self):
        return self.is_superadmin()

    def is_management(self):
        return self.is_superadmin() or self.role == self.ROLE_ADMIN

    def can_manage_rules(self):
        return self.is_management()

    def can_approve_periods(self):
        return self.is_management()

    def can_edit_shareholders(self):
        return self.is_management()

    def can_enter_financials(self):
        return self.is_management() or self.role == self.ROLE_FINANCE

    def can_manage_users(self):
        """Staff user directory — Super Admin and System Admins."""
        return self.is_management()

    def can_assign_owner_role(self):
        """Only Super Admin may create or promote Super Admin accounts."""
        return self.is_superadmin()

    def can_manage_system_settings(self):
        """Brand, SMTP, Mudarabah %, share value, images — Super Admin + Admin."""
        return self.is_management()

    def can_view_audit_log(self):
        return self.is_management()

    def can_manage_target_user(self, target):
        """
        Whether this user may edit/deactivate another staff account.

        - Super Admin (Owner) can manage anyone except removing the last active owner.
        - System Admin cannot edit Super Admin (Owner) accounts.
        """
        if not self.can_manage_users() or not target:
            return False
        if target.is_shareholder():
            return False
        if target.is_superadmin() and not self.is_superadmin():
            return False
        return True

    def is_shareholder(self):
        """Portal-only investor. Company owners are Super Admins with full staff access."""
        if self.is_superadmin():
            return False
        return self.role == self.ROLE_SHAREHOLDER and self.shareholder_id is not None

    def has_shareholder_portal(self):
        """Has a linked shareholder record (own statements), including Company Owner Super Admins."""
        return self.shareholder_id is not None and self.shareholder is not None

    def home_endpoint(self):
        """Canonical post-login home: portal for investors, staff dashboard otherwise."""
        if self.is_shareholder():
            return 'portal.dashboard'
        return 'pages.dashboard'

    @classmethod
    def active_superadmin_count(cls, exclude_id=None):
        query = cls.query.filter_by(role=cls.ROLE_OWNER, is_active=True)
        if exclude_id:
            query = query.filter(cls.id != exclude_id)
        return query.count()
