"""Dynamic certificate content settings stored in SystemSetting."""

from __future__ import annotations

from pathlib import Path

from flask import current_app, url_for

from apps.models.settings import SystemSetting

DEFAULTS = {
    'cert_subtitle': 'Official Company Brand Certificate',
    'cert_title': 'Monthly Shareholder Certificate',
    'cert_intro_text': 'This certifies the current shareholder',
    'cert_allocation_text': 'and has been allocated the following amount for {period_label}:',
    'cert_profit_label': 'Profit share',
    'cert_loss_label': 'Loss allocation',
    'cert_currency_symbol': '$',
    'cert_number_prefix': 'AS-CERT',
    'cert_approver_fallback': 'Akram Sweets Management',
    'cert_owner_label': 'Company Owner',
    'cert_roster_title': 'Current shareholders this month',
    'cert_label_company_pl': 'Company net P/L for month',
    'cert_label_base_share': 'Base ownership share',
    'cert_label_ytd': 'Year-to-date total',
    'cert_label_odoo': 'Odoo reference',
    'cert_footer_disclaimer': (
        'Generated automatically each month for the current shareholder upon period approval.'
    ),
    'cert_footer_confidential': '{company_name} Shareholders Profit Calculation System — confidential',
    'cert_legal_text': '',
    'cert_show_roster': 'true',
    'cert_show_odoo_reference': 'true',
    'cert_signature_name': '',
    'cert_signature_title': '',
    'cert_signature_image_path': '',
}

ALLOWED_SIGNATURE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
BOOL_TRUE = {'1', 'true', 'yes', 'on'}


def _truthy(value, default=True):
    if value is None or value == '':
        return default
    return str(value).strip().lower() in BOOL_TRUE


def _text(key, fallback=None):
    stored = SystemSetting.get(key)
    if stored is None:
        return fallback if fallback is not None else DEFAULTS.get(key, '')
    return str(stored)


def signature_uploads_dir():
    static_root = Path(current_app.root_path) / 'static' / 'uploads' / 'signatures'
    static_root.mkdir(parents=True, exist_ok=True)
    return static_root


def signature_filesystem_path(relative=None):
    path = relative if relative is not None else SystemSetting.get('cert_signature_image_path')
    if not path:
        return None
    full = Path(current_app.root_path) / 'static' / str(path).replace('\\', '/')
    return str(full) if full.is_file() else None


def signature_url(relative=None):
    path = relative if relative is not None else SystemSetting.get('cert_signature_image_path')
    if not path:
        return None
    relative = str(path).replace('\\', '/')
    try:
        from flask import has_request_context

        if has_request_context():
            return url_for('static', filename=relative)
    except RuntimeError:
        pass
    assets_root = (current_app.config.get('ASSETS_ROOT') or '/static').rstrip('/')
    return f'{assets_root}/{relative}'


def save_signature_image(file_storage):
    if not file_storage or not getattr(file_storage, 'filename', None):
        return None

    filename = file_storage.filename
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if ext not in ALLOWED_SIGNATURE_EXTENSIONS:
        raise ValueError('Signature must be a PNG, JPG, WEBP, or GIF image.')

    uploads = signature_uploads_dir()
    for old in uploads.iterdir():
        if old.is_file() and old.name.startswith('signature.'):
            old.unlink(missing_ok=True)

    stored_name = f'signature.{ext}'
    destination = uploads / stored_name
    file_storage.save(destination)
    relative = f'uploads/signatures/{stored_name}'
    SystemSetting.set('cert_signature_image_path', relative)
    return relative


def clear_signature_image():
    path = SystemSetting.get('cert_signature_image_path')
    if path:
        full = Path(current_app.root_path) / 'static' / path.replace('\\', '/')
        if full.is_file():
            full.unlink(missing_ok=True)
    SystemSetting.set('cert_signature_image_path', '')


def get_certificate_settings():
    signature_path = _text('cert_signature_image_path', '')
    currency = _text('cert_currency_symbol') or DEFAULTS['cert_currency_symbol']
    if not str(currency).strip():
        currency = DEFAULTS['cert_currency_symbol']
    return {
        'subtitle': (_text('cert_subtitle') or DEFAULTS['cert_subtitle']).strip(),
        'title': (_text('cert_title') or DEFAULTS['cert_title']).strip(),
        'intro_text': (_text('cert_intro_text') or DEFAULTS['cert_intro_text']).strip(),
        'allocation_text': (_text('cert_allocation_text') or DEFAULTS['cert_allocation_text']).strip(),
        'profit_label': (_text('cert_profit_label') or DEFAULTS['cert_profit_label']).strip(),
        'loss_label': (_text('cert_loss_label') or DEFAULTS['cert_loss_label']).strip(),
        'currency_symbol': currency,
        'number_prefix': (_text('cert_number_prefix') or DEFAULTS['cert_number_prefix']).strip() or 'AS-CERT',
        'approver_fallback': (
            _text('cert_approver_fallback') or DEFAULTS['cert_approver_fallback']
        ).strip() or DEFAULTS['cert_approver_fallback'],
        'owner_label': (_text('cert_owner_label') or DEFAULTS['cert_owner_label']).strip(),
        'roster_title': (_text('cert_roster_title') or DEFAULTS['cert_roster_title']).strip(),
        'label_company_pl': (_text('cert_label_company_pl') or DEFAULTS['cert_label_company_pl']).strip(),
        'label_base_share': (_text('cert_label_base_share') or DEFAULTS['cert_label_base_share']).strip(),
        'label_ytd': (_text('cert_label_ytd') or DEFAULTS['cert_label_ytd']).strip(),
        'label_odoo': (_text('cert_label_odoo') or DEFAULTS['cert_label_odoo']).strip(),
        'footer_disclaimer': (
            _text('cert_footer_disclaimer') or DEFAULTS['cert_footer_disclaimer']
        ).strip(),
        'footer_confidential': (
            _text('cert_footer_confidential') or DEFAULTS['cert_footer_confidential']
        ).strip(),
        'legal_text': (_text('cert_legal_text', '') or '').strip(),
        'show_roster': _truthy(SystemSetting.get('cert_show_roster'), True),
        'show_odoo_reference': _truthy(SystemSetting.get('cert_show_odoo_reference'), True),
        'signature_name': (_text('cert_signature_name', '') or '').strip(),
        'signature_title': (_text('cert_signature_title', '') or '').strip(),
        'signature_image_path': signature_path,
        'signature_url': signature_url(signature_path),
        'signature_filesystem_path': signature_filesystem_path(signature_path),
    }


def format_certificate_text(template, **kwargs):
    text = template or ''
    try:
        return text.format(**{k: ('' if v is None else v) for k, v in kwargs.items()})
    except (KeyError, ValueError, IndexError):
        return text


def save_certificate_settings(data, signature_file=None, remove_signature=False):
    mapping = {
        'cert_subtitle': data.get('subtitle'),
        'cert_title': data.get('title'),
        'cert_intro_text': data.get('intro_text'),
        'cert_allocation_text': data.get('allocation_text'),
        'cert_profit_label': data.get('profit_label'),
        'cert_loss_label': data.get('loss_label'),
        'cert_currency_symbol': data.get('currency_symbol'),
        'cert_number_prefix': data.get('number_prefix'),
        'cert_approver_fallback': data.get('approver_fallback'),
        'cert_owner_label': data.get('owner_label'),
        'cert_roster_title': data.get('roster_title'),
        'cert_label_company_pl': data.get('label_company_pl'),
        'cert_label_base_share': data.get('label_base_share'),
        'cert_label_ytd': data.get('label_ytd'),
        'cert_label_odoo': data.get('label_odoo'),
        'cert_footer_disclaimer': data.get('footer_disclaimer'),
        'cert_footer_confidential': data.get('footer_confidential'),
        'cert_legal_text': data.get('legal_text'),
        'cert_signature_name': data.get('signature_name'),
        'cert_signature_title': data.get('signature_title'),
    }
    for key, value in mapping.items():
        default = DEFAULTS.get(key, '')
        if value is None:
            SystemSetting.set(key, default)
            continue
        text = str(value)
        if key == 'cert_currency_symbol':
            # Allow trailing spaces (e.g. "USD ") for amount formatting.
            SystemSetting.set(key, text if text.strip() else default)
        elif key == 'cert_legal_text':
            SystemSetting.set(key, text.strip())
        else:
            SystemSetting.set(key, text.strip() if text.strip() or key not in DEFAULTS else default)

    SystemSetting.set('cert_show_roster', 'true' if data.get('show_roster') else 'false')
    SystemSetting.set('cert_show_odoo_reference', 'true' if data.get('show_odoo_reference') else 'false')

    if remove_signature:
        clear_signature_image()
    elif signature_file and getattr(signature_file, 'filename', None):
        save_signature_image(signature_file)

    return get_certificate_settings()


def ensure_default_certificate_settings():
    for key, value in DEFAULTS.items():
        if SystemSetting.get(key) is None:
            SystemSetting.set(key, value)
    return get_certificate_settings()
