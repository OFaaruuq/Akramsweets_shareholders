"""Brand identity settings used by certificates, emails, and the UI."""

from __future__ import annotations

import re
from pathlib import Path

from flask import current_app, url_for

from apps.models.settings import SystemSetting

DEFAULT_PRIMARY = '#8A1B24'
DEFAULT_SECONDARY = '#C8924B'
DEFAULT_ACCENT = '#F5E8D4'
DEFAULT_COMPANY_NAME = 'Akram Sweets'

HEX_COLOR_RE = re.compile(r'^#?[0-9A-Fa-f]{6}$')
ALLOWED_LOGO_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}


def _normalize_hex(value, default):
    if not value:
        return default
    value = str(value).strip()
    if not HEX_COLOR_RE.match(value):
        return default
    if not value.startswith('#'):
        value = f'#{value}'
    return value.upper()


def brand_uploads_dir():
    static_root = Path(current_app.root_path) / 'static' / 'uploads' / 'brand'
    static_root.mkdir(parents=True, exist_ok=True)
    return static_root


def get_brand_settings():
    logo_path = SystemSetting.get('brand_logo_path') or ''
    return {
        'company_name': (SystemSetting.get('brand_company_name') or DEFAULT_COMPANY_NAME).strip() or DEFAULT_COMPANY_NAME,
        'primary_color': _normalize_hex(SystemSetting.get('brand_primary_color'), DEFAULT_PRIMARY),
        'secondary_color': _normalize_hex(SystemSetting.get('brand_secondary_color'), DEFAULT_SECONDARY),
        'accent_color': _normalize_hex(SystemSetting.get('brand_accent_color'), DEFAULT_ACCENT),
        'logo_path': logo_path,
        'logo_url': brand_logo_url(logo_path),
        'logo_filesystem_path': brand_logo_filesystem_path(logo_path),
    }


def brand_logo_url(logo_path=None):
    path = logo_path if logo_path is not None else SystemSetting.get('brand_logo_path')
    if not path:
        return None
    relative = path.replace('\\', '/')
    try:
        from flask import has_request_context

        if has_request_context():
            return url_for('static', filename=relative)
    except RuntimeError:
        pass
    assets_root = (current_app.config.get('ASSETS_ROOT') or '/static').rstrip('/')
    return f'{assets_root}/{relative}'


def brand_logo_filesystem_path(logo_path=None):
    path = logo_path if logo_path is not None else SystemSetting.get('brand_logo_path')
    if not path:
        return None
    full = Path(current_app.root_path) / 'static' / path.replace('\\', '/')
    return str(full) if full.is_file() else None


def save_brand_logo(file_storage):
    if not file_storage or not getattr(file_storage, 'filename', None):
        return None

    filename = file_storage.filename
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if ext not in ALLOWED_LOGO_EXTENSIONS:
        raise ValueError('Logo must be a PNG, JPG, WEBP, or GIF image.')

    uploads = brand_uploads_dir()
    # Clear previous uploaded logos to avoid orphan files.
    for old in uploads.iterdir():
        if old.is_file() and old.name.startswith('logo.'):
            old.unlink(missing_ok=True)

    stored_name = f'logo.{ext}'
    destination = uploads / stored_name
    file_storage.save(destination)
    relative = f'uploads/brand/{stored_name}'
    SystemSetting.set('brand_logo_path', relative)
    return relative


def clear_brand_logo():
    path = SystemSetting.get('brand_logo_path')
    if path:
        full = Path(current_app.root_path) / 'static' / path.replace('\\', '/')
        # Keep the generated default logo file; only clear the setting / custom uploads.
        if full.is_file() and full.name != 'logo-default.png':
            full.unlink(missing_ok=True)
    SystemSetting.set('brand_logo_path', '')
    ensure_default_logo()


def save_brand_settings(
    company_name,
    primary_color,
    secondary_color,
    accent_color,
    logo_file=None,
    remove_logo=False,
):
    SystemSetting.set('brand_company_name', (company_name or DEFAULT_COMPANY_NAME).strip() or DEFAULT_COMPANY_NAME)
    SystemSetting.set('brand_primary_color', _normalize_hex(primary_color, DEFAULT_PRIMARY))
    SystemSetting.set('brand_secondary_color', _normalize_hex(secondary_color, DEFAULT_SECONDARY))
    SystemSetting.set('brand_accent_color', _normalize_hex(accent_color, DEFAULT_ACCENT))

    if remove_logo:
        clear_brand_logo()
    elif logo_file and getattr(logo_file, 'filename', None):
        save_brand_logo(logo_file)

    return get_brand_settings()


def ensure_default_logo():
    """Create a simple branded default logo if none is uploaded yet."""
    existing = brand_logo_filesystem_path()
    if existing:
        return existing

    uploads = brand_uploads_dir()
    destination = uploads / 'logo-default.png'
    if not destination.is_file():
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            return None

        size = 512
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        primary = DEFAULT_PRIMARY.lstrip('#')
        secondary = DEFAULT_SECONDARY.lstrip('#')
        primary_rgb = tuple(int(primary[i:i + 2], 16) for i in (0, 2, 4))
        secondary_rgb = tuple(int(secondary[i:i + 2], 16) for i in (0, 2, 4))

        margin = 24
        draw.ellipse([margin, margin, size - margin, size - margin], fill=primary_rgb)
        draw.ellipse([78, 78, size - 78, size - 78], outline=secondary_rgb, width=14)
        try:
            font = ImageFont.truetype('arial.ttf', 160)
        except OSError:
            font = ImageFont.load_default()
        text = 'AS'
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(((size - tw) / 2, (size - th) / 2 - 10), text, fill=(255, 255, 255, 255), font=font)
        img.save(destination, format='PNG')

    relative = 'uploads/brand/logo-default.png'
    if not SystemSetting.get('brand_logo_path'):
        SystemSetting.set('brand_logo_path', relative)
    return str(destination)


def ensure_default_brand_settings():
    defaults = {
        'brand_company_name': DEFAULT_COMPANY_NAME,
        'brand_primary_color': DEFAULT_PRIMARY,
        'brand_secondary_color': DEFAULT_SECONDARY,
        'brand_accent_color': DEFAULT_ACCENT,
    }
    for key, value in defaults.items():
        if SystemSetting.get(key) is None:
            SystemSetting.set(key, value)
    ensure_default_logo()
