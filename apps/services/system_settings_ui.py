"""Categorized System Settings sections (nav + field groups + save helpers)."""

from __future__ import annotations

SETTINGS_SECTIONS = (
    {
        'id': 'profit',
        'label': 'Profit & Capital',
        'icon': 'solar:chart-2-bold-duotone',
        'description': 'Mudarabah split, capital register, and withdrawal deadline.',
    },
    {
        'id': 'brand',
        'label': 'Brand',
        'icon': 'solar:palette-bold-duotone',
        'description': 'Company name, colors, and logo used on certificates and emails.',
    },
    {
        'id': 'certificates',
        'label': 'Certificates',
        'icon': 'solar:diploma-verified-bold-duotone',
        'description': 'Certificate wording, labels, roster, and signature.',
    },
    {
        'id': 'email',
        'label': 'Email & SMTP',
        'icon': 'solar:letter-bold-duotone',
        'description': 'SMTP delivery, notification toggles, and report schedule.',
    },
    {
        'id': 'whatsapp',
        'label': 'WhatsApp',
        'icon': 'solar:chat-round-dots-bold-duotone',
        'description': 'Twilio WhatsApp, PDF attachments, templates, and webhooks.',
    },
)

SECTION_IDS = {s['id'] for s in SETTINGS_SECTIONS}

SECTION_FIELDS = {
    'profit': (
        'mudarabah_shareholder_percent',
        'capital_return_deadline_days',
        'share_value',
        'total_company_shares',
        'company_owned_assets',
    ),
    'brand': (
        'brand_company_name',
        'brand_primary_color',
        'brand_secondary_color',
        'brand_accent_color',
        'brand_logo',
        'remove_brand_logo',
    ),
    'certificates': (
        'cert_subtitle',
        'cert_title',
        'cert_intro_text',
        'cert_allocation_text',
        'cert_profit_label',
        'cert_loss_label',
        'cert_currency_symbol',
        'cert_number_prefix',
        'cert_approver_fallback',
        'cert_owner_label',
        'cert_roster_title',
        'cert_label_company_pl',
        'cert_label_base_share',
        'cert_label_ytd',
        'cert_label_odoo',
        'cert_footer_disclaimer',
        'cert_footer_confidential',
        'cert_legal_text',
        'cert_show_roster',
        'cert_show_odoo_reference',
        'cert_signature_name',
        'cert_signature_title',
        'cert_signature_image',
        'remove_cert_signature',
    ),
    'email': (
        'auto_email_on_approval',
        'notify_management_on_review',
        'email_portal_credentials',
        'email_staff_invite',
        'email_password_change',
        'notify_shareholders_on_profit_update',
        'report_delivery_day',
        'mail_from',
        'mail_server',
        'mail_port',
        'mail_username',
        'mail_password',
    ),
    'whatsapp': (
        'sms_notifications_enabled',
        'whatsapp_attach_pdfs',
        'whatsapp_auto_reply_enabled',
        'whatsapp_auto_reply_text',
        'public_base_url',
        'twilio_content_sid_otp',
        'twilio_content_sid_report',
        'twilio_content_sid_credentials',
        'twilio_content_sid_period_update',
        'twilio_content_sid_payment',
        'twilio_content_sid_withdrawal',
        'twilio_content_sid_staff_invite',
        'twilio_content_sid_password',
        'twilio_content_sid_review',
        'twilio_content_sid_generic',
    ),
}


def normalize_section(section: str | None) -> str:
    key = (section or 'profit').strip().lower()
    return key if key in SECTION_IDS else 'profit'


def section_meta(section: str) -> dict:
    sid = normalize_section(section)
    for item in SETTINGS_SECTIONS:
        if item['id'] == sid:
            return item
    return SETTINGS_SECTIONS[0]


def validate_section(form, section: str) -> bool:
    """Validate CSRF plus only the fields that belong to the active section."""
    ok = True
    csrf = getattr(form, 'csrf_token', None)
    if csrf is not None and not csrf.validate(form):
        ok = False
    for name in SECTION_FIELDS.get(normalize_section(section), ()):
        field = getattr(form, name, None)
        if field is None:
            continue
        if not field.validate(form):
            ok = False
    return ok
