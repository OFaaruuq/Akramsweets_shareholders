from datetime import datetime

from apps import db


class MonthlyPeriod(db.Model):
    __tablename__ = 'monthly_periods'

    STATUS_DRAFT = 'draft'
    STATUS_REVIEW = 'review'
    STATUS_APPROVED = 'approved'

    STATUSES = (STATUS_DRAFT, STATUS_REVIEW, STATUS_APPROVED)

    # Post-approval payment tracking
    PAYMENT_PENDING = 'pending'
    PAYMENT_COMPLETED = 'completed'
    PAYMENT_STATUSES = (PAYMENT_PENDING, PAYMENT_COMPLETED)

    WORKFLOW_LABELS = {
        STATUS_DRAFT: 'Draft',
        STATUS_REVIEW: 'Management Approval',
        STATUS_APPROVED: 'Locked',
    }

    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    total_profit_loss = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    # Mudarabah pools (derived from Net Profit × configured shareholder %)
    shareholders_pool = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    managing_partner_share = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    mudarabah_shareholder_percent = db.Column(db.Numeric(7, 4), nullable=False, default=50)
    # Full P&L statement (optional notes). Net Profit = total_profit_loss.
    income = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    gross_profit = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    total_gross_profit = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    total_income = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    # Legacy / compatibility fields (kept in sync for older reports/charts)
    total_revenues = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    cost_of_goods = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    total_expenses = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    other_income = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    entry_mode = db.Column(db.String(20), nullable=False, default='pnl')
    odoo_reference = db.Column(db.String(255), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default=STATUS_DRAFT)
    calculated_at = db.Column(db.DateTime, nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    approved_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    submitted_for_review_at = db.Column(db.DateTime, nullable=True)
    submitted_for_review_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    rejection_reason = db.Column(db.Text, nullable=True)
    rejected_at = db.Column(db.DateTime, nullable=True)
    rejected_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    reports_sent_at = db.Column(db.DateTime, nullable=True)
    payment_status = db.Column(db.String(20), nullable=False, default=PAYMENT_PENDING)
    payment_completed_at = db.Column(db.DateTime, nullable=True)
    payment_completed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    approved_by = db.relationship('User', foreign_keys=[approved_by_id])
    submitted_for_review_by = db.relationship('User', foreign_keys=[submitted_for_review_by_id])
    rejected_by = db.relationship('User', foreign_keys=[rejected_by_id])
    payment_completed_by = db.relationship('User', foreign_keys=[payment_completed_by_id])
    created_by = db.relationship('User', foreign_keys=[created_by_id])
    calculations = db.relationship(
        'ShareholderCalculation',
        backref='period',
        lazy='dynamic',
        cascade='all, delete-orphan',
    )
    adjustments = db.relationship(
        'ManualAdjustment',
        backref='period',
        lazy='dynamic',
        cascade='all, delete-orphan',
    )

    __table_args__ = (
        db.UniqueConstraint('year', 'month', name='uq_period_year_month'),
    )

    @property
    def period_label(self):
        return f'{self.year}-{self.month:02d}'

    @property
    def is_locked(self):
        return self.status == self.STATUS_APPROVED

    @property
    def is_editable(self):
        """Figures may only change in draft. Review is frozen until approve or reject."""
        return self.status == self.STATUS_DRAFT

    @property
    def awaits_approval(self):
        return self.status == self.STATUS_REVIEW

    @property
    def payment_completed(self):
        return self.payment_status == self.PAYMENT_COMPLETED

    @property
    def workflow_label(self):
        if self.payment_completed:
            return 'Payment Completed'
        return self.WORKFLOW_LABELS.get(self.status, (self.status or '').title())

    @property
    def workflow_steps(self):
        """UI stepper: Draft → Finance Review → Management Approval → Locked → Payment Completed."""
        steps = [
            {'key': 'draft', 'label': 'Draft'},
            {'key': 'finance_review', 'label': 'Finance Review'},
            {'key': 'management', 'label': 'Management Approval'},
            {'key': 'locked', 'label': 'Locked'},
            {'key': 'payment', 'label': 'Payment Completed'},
        ]
        if self.payment_completed:
            active = 'payment'
        elif self.status == self.STATUS_APPROVED:
            active = 'locked'
        elif self.status == self.STATUS_REVIEW:
            active = 'management'
        elif self.calculated_at:
            active = 'finance_review'
        else:
            active = 'draft'
        keys = [s['key'] for s in steps]
        active_idx = keys.index(active)
        for i, step in enumerate(steps):
            step['done'] = i < active_idx
            step['current'] = i == active_idx
        return steps

    @property
    def as_of_date(self):
        from calendar import monthrange
        last_day = monthrange(self.year, self.month)[1]
        return datetime(self.year, self.month, last_day).date()

    @property
    def computed_net_profit_loss(self):
        """Reference check only — distribution always uses entered Net Profit."""
        from decimal import Decimal
        return Decimal(self.total_income or 0) - Decimal(self.total_expenses or 0)

    @property
    def uses_breakdown(self):
        return self.entry_mode in ('breakdown', 'pnl')

    @property
    def net_profit(self):
        return self.total_profit_loss

    @property
    def company_share(self):
        """Managing partner share (Mudarabah remainder — company brand name)."""
        return self.managing_partner_share


class ShareholderCalculation(db.Model):
    __tablename__ = 'shareholder_calculations'

    id = db.Column(db.Integer, primary_key=True)
    period_id = db.Column(db.Integer, db.ForeignKey('monthly_periods.id'), nullable=False)
    shareholder_id = db.Column(db.Integer, db.ForeignKey('shareholders.id'), nullable=False)
    ownership_percent = db.Column(db.Numeric(7, 4), nullable=False)
    base_share = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    arrangement_deduction = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    arrangement_received = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    manual_adjustment = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    final_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    shareholder = db.relationship('Shareholder')

    __table_args__ = (
        db.UniqueConstraint('period_id', 'shareholder_id', name='uq_period_shareholder_calc'),
    )


class ManualAdjustment(db.Model):
    __tablename__ = 'manual_adjustments'

    id = db.Column(db.Integer, primary_key=True)
    period_id = db.Column(db.Integer, db.ForeignKey('monthly_periods.id'), nullable=False)
    shareholder_id = db.Column(db.Integer, db.ForeignKey('shareholders.id'), nullable=False)
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    shareholder = db.relationship('Shareholder')
    created_by = db.relationship('User')
