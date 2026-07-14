from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import BooleanField, DateField, DecimalField, IntegerField, PasswordField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional, Regexp

from apps.services.period_service import MONTH_CHOICES, compute_net_from_breakdown


class ShareholderForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(max=120)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    phone = StringField('Phone', validators=[Optional(), Length(max=40)])
    country_code = SelectField('Country', validators=[DataRequired()], coerce=str)
    is_owner = BooleanField('Company owner')
    is_active = BooleanField('Active', default=True)
    notes = TextAreaField('Notes', validators=[Optional()])
    ownership_percent = DecimalField(
        'Ownership %',
        places=4,
        validators=[DataRequired(), NumberRange(min=0.0001, max=100)],
    )
    effective_from = DateField('Effective from', validators=[DataRequired()], format='%Y-%m-%d')
    create_portal = BooleanField('Also create portal login for this shareholder')
    portal_email = StringField('Portal login email', validators=[Optional(), Email(), Length(max=120)])
    portal_password = PasswordField('Portal password', validators=[Optional(), Length(min=6, max=128)])
    submit = SubmitField('Save Shareholder')


class PeriodForm(FlaskForm):
    entry_mode = SelectField(
        'How to enter profit / loss',
        choices=[
            ('breakdown', 'Calculate from P&L breakdown (Odoo figures)'),
            ('manual', 'Enter net profit / loss directly'),
        ],
        default='breakdown',
        validators=[DataRequired()],
    )
    year = IntegerField('Year', validators=[DataRequired(), NumberRange(min=2000, max=2100)])
    month = SelectField(
        'Month',
        choices=MONTH_CHOICES,
        coerce=int,
        validators=[DataRequired()],
    )
    total_revenues = DecimalField(
        'Total revenues',
        places=2,
        validators=[Optional(), NumberRange(min=0)],
        default=0,
    )
    cost_of_goods = DecimalField(
        'Cost of goods sold',
        places=2,
        validators=[Optional(), NumberRange(min=0)],
        default=0,
    )
    total_expenses = DecimalField(
        'Operating expenses',
        places=2,
        validators=[Optional(), NumberRange(min=0)],
        default=0,
    )
    other_income = DecimalField(
        'Other income',
        places=2,
        validators=[Optional(), NumberRange(min=0)],
        default=0,
    )
    total_profit_loss = DecimalField(
        'Net profit / loss',
        places=2,
        validators=[Optional()],
    )
    odoo_reference = StringField('Odoo reference', validators=[Optional(), Length(max=255)])
    notes = TextAreaField('Internal notes', validators=[Optional(), Length(max=5000)])
    submit = SubmitField('Save & Calculate Distribution')

    def validate(self, extra_validators=None):
        if not super().validate(extra_validators):
            return False

        if self.entry_mode.data == 'manual':
            if self.total_profit_loss.data is None:
                self.total_profit_loss.errors.append('Enter the net profit or loss amount.')
                return False
            return True

        revenues = self.total_revenues.data or 0
        cogs = self.cost_of_goods.data or 0
        expenses = self.total_expenses.data or 0
        other = self.other_income.data or 0
        if revenues == 0 and cogs == 0 and expenses == 0 and other == 0:
            self.total_revenues.errors.append('Enter at least one P&L figure from Odoo.')
            return False

        self.total_profit_loss.data = compute_net_from_breakdown(revenues, cogs, expenses, other)
        return True


class AdjustmentForm(FlaskForm):
    shareholder_id = SelectField('Shareholder', coerce=int, validators=[DataRequired()])
    amount = DecimalField('Adjustment amount', places=2, validators=[DataRequired()])
    reason = TextAreaField('Reason', validators=[DataRequired(), Length(min=3, max=2000)])
    submit = SubmitField('Add Adjustment')


class ArrangementForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(max=120)])
    recipient_shareholder_id = SelectField('Recipient', coerce=int, validators=[DataRequired()])
    bonus_percent = DecimalField('Bonus %', places=4, validators=[DataRequired(), NumberRange(min=0, max=100)])
    applies_to_all_others = BooleanField('Apply to all other shareholders', default=True)
    apply_on_profit = BooleanField('Apply on profit', default=True)
    apply_on_loss = BooleanField('Apply on loss', default=True)
    effective_from = DateField('Effective from', validators=[DataRequired()], format='%Y-%m-%d')
    effective_to = DateField('Effective to', validators=[Optional()], format='%Y-%m-%d')
    notes = TextAreaField('Notes', validators=[Optional()])
    submit = SubmitField('Save Arrangement')


class SystemSettingsForm(FlaskForm):
    auto_email_on_approval = BooleanField(
        'Automatically email shareholders with certificates when a period is approved',
        default=True,
    )
    report_delivery_day = IntegerField('Report delivery day of month', validators=[Optional(), NumberRange(min=1, max=28)])
    mail_from = StringField('From email', validators=[Optional(), Email()])
    mail_server = StringField('SMTP server', validators=[Optional(), Length(max=120)])
    mail_port = IntegerField('SMTP port', validators=[Optional(), NumberRange(min=1, max=65535)])
    mail_username = StringField('SMTP username', validators=[Optional(), Length(max=120)])
    mail_password = StringField('SMTP password', validators=[Optional(), Length(max=120)])

    brand_company_name = StringField('Company name', validators=[DataRequired(), Length(max=120)])
    brand_primary_color = StringField(
        'Primary brand color',
        validators=[DataRequired(), Regexp(r'^#?[0-9A-Fa-f]{6}$', message='Use a hex color like #8A1B24')],
        default='#8A1B24',
    )
    brand_secondary_color = StringField(
        'Secondary brand color',
        validators=[DataRequired(), Regexp(r'^#?[0-9A-Fa-f]{6}$', message='Use a hex color like #C8924B')],
        default='#C8924B',
    )
    brand_accent_color = StringField(
        'Accent / background color',
        validators=[DataRequired(), Regexp(r'^#?[0-9A-Fa-f]{6}$', message='Use a hex color like #F5E8D4')],
        default='#F5E8D4',
    )
    brand_logo = FileField(
        'Certificate / brand logo',
        validators=[Optional(), FileAllowed(['png', 'jpg', 'jpeg', 'webp', 'gif'], 'Images only!')],
    )
    remove_brand_logo = BooleanField('Remove current logo')
    submit = SubmitField('Save Settings')


class DashboardSettingsForm(FlaskForm):
    total_revenues = DecimalField(
        'Total Revenues (from Odoo)',
        places=2,
        validators=[Optional(), NumberRange(min=0)],
        default=0,
    )
    total_expenses = DecimalField(
        'Total Expenses (from Odoo)',
        places=2,
        validators=[Optional(), NumberRange(min=0)],
        default=0,
    )
    cost_of_goods = DecimalField(
        'Cost of Goods Sold',
        places=2,
        validators=[Optional(), NumberRange(min=0)],
        default=0,
    )
    other_income = DecimalField(
        'Other Income',
        places=2,
        validators=[Optional(), NumberRange(min=0)],
        default=0,
    )
    operating_notes = TextAreaField(
        'Operating notes (shown on dashboard)',
        validators=[Optional(), Length(max=2000)],
    )
    submit = SubmitField('Save Dashboard Figures')


class CorrectionReopenForm(FlaskForm):
    reason = TextAreaField(
        'Reason for reopening this approved period',
        validators=[DataRequired(), Length(min=10, max=2000)],
    )
    submit = SubmitField('Reopen for Correction')
