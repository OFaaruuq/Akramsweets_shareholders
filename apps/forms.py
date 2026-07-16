from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import (
    BooleanField,
    DateField,
    DecimalField,
    IntegerField,
    PasswordField,
    SelectField,
    SelectMultipleField,
    StringField,
    SubmitField,
    TextAreaField,
    widgets,
)
from wtforms.validators import DataRequired, Email, InputRequired, Length, NumberRange, Optional, Regexp

from apps.services.period_service import MONTH_CHOICES


class ShareholderForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(min=2, max=120)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    phone = StringField(
        'Phone',
        validators=[
            Optional(),
            Length(max=40),
            Regexp(r'^[\d\s\+\-\(\)\.]*$', message='Use digits and phone punctuation only.'),
        ],
    )
    country_code = SelectField('Country', validators=[DataRequired()], coerce=str)
    is_owner = BooleanField('Company owner')
    is_active = BooleanField('Active', default=True)
    notes = TextAreaField('Notes', validators=[Optional(), Length(max=5000)])
    ownership_percent = DecimalField(
        'Ownership %',
        places=4,
        validators=[DataRequired(), NumberRange(min=0.0001, max=100)],
    )
    effective_from = DateField('Effective from', validators=[DataRequired()], format='%Y-%m-%d')
    investment_amount = DecimalField(
        'Investment amount',
        places=2,
        validators=[Optional(), NumberRange(min=0)],
        default=0,
        description='Registered capital invested by this shareholder.',
    )
    share_count = DecimalField(
        'Number of shares',
        places=4,
        validators=[Optional(), NumberRange(min=0)],
        default=0,
        description='Registered share units for this shareholder.',
    )
    investment_date = DateField('Investment date', validators=[Optional()], format='%Y-%m-%d')
    create_portal = BooleanField('Also create portal login for this shareholder')
    portal_email = StringField('Portal login email', validators=[Optional(), Email(), Length(max=120)])
    portal_password = PasswordField('Portal password', validators=[Optional(), Length(min=6, max=128)])
    sync_portal_email = BooleanField(
        'Sync portal login email when shareholder email changes',
        default=False,
    )
    suggest_shares = BooleanField(
        'Auto-fill shares from ownership % (uses company total shares)',
        default=False,
    )
    submit = SubmitField('Save Shareholder')


class CapitalWithdrawalForm(FlaskForm):
    amount = DecimalField(
        'Amount to withdraw',
        places=2,
        validators=[DataRequired(), NumberRange(min=0.01)],
    )
    reason = TextAreaField('Reason', validators=[DataRequired(), Length(min=3, max=5000)])
    submit = SubmitField('Submit Withdrawal Request')


class CapitalWithdrawalReviewForm(FlaskForm):
    review_notes = TextAreaField('Review notes', validators=[Optional(), Length(max=5000)])
    capital_return_date = DateField(
        'Capital return date',
        validators=[Optional()],
        format='%Y-%m-%d',
    )
    submit_approve = SubmitField('Approve')
    submit_reject = SubmitField('Reject')
    submit_complete = SubmitField('Mark Capital Returned')
    submit_cancel = SubmitField('Cancel Request')


class PeriodForm(FlaskForm):
    """
    Monthly Mudarabah profit distribution entry.

    Only Approved Monthly Net Profit (from Odoo) drives distribution.
    Optional P&L reference lines are stored only when provided and never used in the split.
    """

    year = IntegerField('Year', validators=[DataRequired(), NumberRange(min=2000, max=2100)])
    month = SelectField(
        'Month',
        choices=MONTH_CHOICES,
        coerce=int,
        validators=[DataRequired()],
    )
    total_profit_loss = DecimalField(
        'Approved Monthly Net Profit (Imported from Odoo ERP)',
        places=2,
        validators=[InputRequired(message='Enter Approved Monthly Net Profit from Odoo (negative for a loss).')],
        description=(
            'Only this figure is used for Mudarabah distribution. '
            'Shareholders\' pool = Net Profit × configured Mudarabah %; '
            'remainder is the managing partner (company) share.'
        ),
    )
    odoo_reference = StringField(
        'Odoo period / journal reference',
        validators=[Optional(), Length(max=255)],
    )
    # Optional Odoo P&L reference — not used for shareholder calculation
    income = DecimalField('Income (Odoo reference)', places=2, validators=[Optional()], default=0)
    gross_profit = DecimalField('Gross Profit (Odoo reference)', places=2, validators=[Optional()], default=0)
    total_gross_profit = DecimalField(
        'Total Gross Profit (Odoo reference)', places=2, validators=[Optional()], default=0
    )
    total_income = DecimalField('Total Income (Odoo reference)', places=2, validators=[Optional()], default=0)
    total_expenses = DecimalField(
        'Operating Expenses (Odoo reference)', places=2, validators=[Optional()], default=0
    )
    notes = TextAreaField('Internal notes', validators=[Optional(), Length(max=5000)])
    submit = SubmitField('Save & Calculate Mudarabah Distribution')

    def validate(self, extra_validators=None):
        if not super().validate(extra_validators):
            return False
        if self.total_profit_loss.data is None:
            self.total_profit_loss.errors.append(
                'Enter Approved Monthly Net Profit (Imported from Odoo ERP).'
            )
            return False
        return True


class AdjustmentForm(FlaskForm):
    shareholder_id = SelectField('Shareholder', coerce=int, validators=[DataRequired()])
    amount = DecimalField('Adjustment amount', places=2, validators=[DataRequired()])
    reason = TextAreaField('Reason', validators=[DataRequired(), Length(min=3, max=2000)])
    submit = SubmitField('Add Adjustment')


class MultiCheckboxField(SelectMultipleField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()


class ArrangementForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(max=120)])
    recipient_shareholder_id = SelectField('Recipient', coerce=int, validators=[DataRequired()])
    bonus_percent = DecimalField(
        'Bonus %',
        places=4,
        validators=[DataRequired(), NumberRange(min=0.0001, max=100)],
    )
    applies_to_all_others = BooleanField('Apply to all other shareholders', default=True)
    source_shareholder_ids = MultiCheckboxField(
        'Source shareholders',
        coerce=int,
        validators=[Optional()],
    )
    apply_on_profit = BooleanField('Apply on profit', default=True)
    apply_on_loss = BooleanField('Apply on loss', default=True)
    effective_from = DateField('Effective from', validators=[DataRequired()], format='%Y-%m-%d')
    effective_to = DateField('Effective to', validators=[Optional()], format='%Y-%m-%d')
    notes = TextAreaField('Notes', validators=[Optional()])
    submit = SubmitField('Save Arrangement')

    def validate(self, extra_validators=None):
        if not super().validate(extra_validators=extra_validators):
            return False

        if self.effective_to.data and self.effective_from.data:
            if self.effective_to.data < self.effective_from.data:
                self.effective_to.errors.append('Effective to must be on or after effective from.')
                return False

        if not self.applies_to_all_others.data:
            sources = list(self.source_shareholder_ids.data or [])
            if not sources:
                self.source_shareholder_ids.errors.append(
                    'Select at least one source shareholder, or enable “Apply to all other shareholders”.',
                )
                return False
            if self.recipient_shareholder_id.data in sources:
                self.source_shareholder_ids.errors.append(
                    'The recipient cannot also be listed as a source shareholder.',
                )
                return False

        if not self.apply_on_profit.data and not self.apply_on_loss.data:
            self.apply_on_profit.errors.append('Choose profit, loss, or both.')
            return False

        return True


class SystemSettingsForm(FlaskForm):
    auto_email_on_approval = BooleanField(
        'Automatically email shareholders with certificates when a period is approved',
        default=True,
    )
    sms_notifications_enabled = BooleanField(
        'Also send WhatsApp via Twilio when a phone number is on file (requires TWILIO_* in .env)',
        default=False,
    )
    notify_management_on_review = BooleanField(
        'Email owners/admins when a period is submitted for review',
        default=True,
    )
    email_portal_credentials = BooleanField(
        'Email shareholders their portal login details when access is granted or reset',
        default=True,
    )
    email_staff_invite = BooleanField(
        'Email new staff users their account credentials',
        default=True,
    )
    email_password_change = BooleanField(
        'Email confirmation when a shareholder changes their password',
        default=True,
    )
    notify_shareholders_on_profit_update = BooleanField(
        'Automatically email all shareholders when monthly profit figures are updated',
        default=True,
    )
    share_value = DecimalField(
        'Value of 1 share',
        places=2,
        validators=[DataRequired(message='Enter the value of one share.'), NumberRange(min=0)],
        default=1000,
        description='Example: 1000 means 1 share = 1000 in your currency.',
    )
    total_company_shares = DecimalField(
        'Total company shares (optional)',
        places=4,
        validators=[Optional(), NumberRange(min=0)],
        description='If set, ownership % is also shown as an equivalent share count and capital.',
    )
    mudarabah_shareholder_percent = DecimalField(
        'Shareholders\' Mudarabah share (%)',
        places=4,
        validators=[DataRequired(), NumberRange(min=0, max=100)],
        default=50,
        description=(
            'Percent of Monthly Net Profit that goes to the shareholders\' profit pool. '
            'The remainder is the managing partner (company) share. Configurable anytime.'
        ),
    )
    capital_return_deadline_days = IntegerField(
        'Capital return deadline (days after approval)',
        validators=[DataRequired(), NumberRange(min=1, max=3650)],
        default=183,
        description='Number of days the company has to return capital after a withdrawal is approved.',
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

    cert_subtitle = StringField('Certificate subtitle', validators=[DataRequired(), Length(max=200)])
    cert_title = StringField('Certificate title', validators=[DataRequired(), Length(max=200)])
    cert_intro_text = StringField('Intro line', validators=[DataRequired(), Length(max=300)])
    cert_allocation_text = StringField(
        'Allocation line',
        validators=[DataRequired(), Length(max=400)],
        description='Use {period_label} for the month label.',
    )
    cert_profit_label = StringField('Profit amount label', validators=[DataRequired(), Length(max=80)])
    cert_loss_label = StringField('Loss amount label', validators=[DataRequired(), Length(max=80)])
    cert_currency_symbol = StringField('Currency symbol', validators=[DataRequired(), Length(max=8)])
    cert_number_prefix = StringField('Certificate number prefix', validators=[DataRequired(), Length(max=40)])
    cert_approver_fallback = StringField(
        'Approver name fallback',
        validators=[DataRequired(), Length(max=120)],
    )
    cert_owner_label = StringField('Owner badge label', validators=[DataRequired(), Length(max=80)])
    cert_roster_title = StringField('Shareholder roster title', validators=[DataRequired(), Length(max=160)])
    cert_label_company_pl = StringField('Company P/L label', validators=[DataRequired(), Length(max=120)])
    cert_label_base_share = StringField('Base share label', validators=[DataRequired(), Length(max=120)])
    cert_label_ytd = StringField('YTD total label', validators=[DataRequired(), Length(max=120)])
    cert_label_odoo = StringField('Odoo reference label', validators=[DataRequired(), Length(max=120)])
    cert_footer_disclaimer = StringField('Footer disclaimer', validators=[DataRequired(), Length(max=400)])
    cert_footer_confidential = StringField(
        'Confidential footer',
        validators=[DataRequired(), Length(max=300)],
        description='Use {company_name} for the company name.',
    )
    cert_legal_text = TextAreaField(
        'Legal / additional text',
        validators=[Optional(), Length(max=2000)],
        description='Optional paragraph shown above the signature area.',
    )
    cert_show_roster = BooleanField('Show current shareholders roster on certificates', default=True)
    cert_show_odoo_reference = BooleanField('Show Odoo reference when available', default=True)
    cert_signature_name = StringField('Signature name', validators=[Optional(), Length(max=120)])
    cert_signature_title = StringField('Signature title', validators=[Optional(), Length(max=120)])
    cert_signature_image = FileField(
        'Signature image',
        validators=[Optional(), FileAllowed(['png', 'jpg', 'jpeg', 'webp', 'gif'], 'Images only!')],
    )
    remove_cert_signature = BooleanField('Remove signature image')

    submit = SubmitField('Save Settings')


class BrandLogoForm(FlaskForm):
    brand_logo = FileField(
        'Brand / company logo',
        validators=[Optional(), FileAllowed(['png', 'jpg', 'jpeg', 'webp', 'gif'], 'Images only!')],
    )
    remove_brand_logo = BooleanField('Remove current logo (restore default)')
    submit = SubmitField('Save brand logo')


class CertificateSignatureImageForm(FlaskForm):
    cert_signature_image = FileField(
        'Certificate signature image',
        validators=[Optional(), FileAllowed(['png', 'jpg', 'jpeg', 'webp', 'gif'], 'Images only!')],
    )
    remove_cert_signature = BooleanField('Remove signature image')
    submit = SubmitField('Save signature image')


class MediaLibraryUploadForm(FlaskForm):
    image = FileField(
        'Image file',
        validators=[DataRequired(), FileAllowed(['png', 'jpg', 'jpeg', 'webp', 'gif'], 'Images only!')],
    )
    title = StringField('Title', validators=[Optional(), Length(max=120)])
    slot = SelectField(
        'Assign to',
        choices=[
            ('', 'Media library only'),
            ('login_background', 'Login page background'),
            ('email_header', 'Email header image'),
            ('dashboard_banner', 'Dashboard banner'),
        ],
        validators=[Optional()],
        default='',
    )
    submit = SubmitField('Upload image')


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


class PeriodRejectForm(FlaskForm):
    reason = TextAreaField(
        'Reason for returning to draft',
        validators=[DataRequired(), Length(min=5, max=2000)],
        description='Finance will see this reason and must fix and re-submit.',
    )
    submit = SubmitField('Return to Draft')


class ShareholderUpdateForm(FlaskForm):
    message = TextAreaField(
        'Optional message to shareholders',
        validators=[Optional(), Length(max=2000)],
        description='Included in the email update to every shareholder on this period.',
    )
    submit = SubmitField('Send Update to Shareholders')
