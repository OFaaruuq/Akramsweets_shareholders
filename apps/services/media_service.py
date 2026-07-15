"""Admin-managed application images used across UI, emails, certificates, and login."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path

from flask import current_app, url_for
from werkzeug.utils import secure_filename

from apps.models.settings import SystemSetting

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB

# Slots that can be assigned to uploaded library images (or managed system assets).
IMAGE_SLOTS = {
    'brand_logo': {
        'label': 'Brand / company logo',
        'description': 'Sidebar, login, emails, certificates, and PDF reports.',
        'managed': 'brand',
    },
    'cert_signature': {
        'label': 'Certificate signature',
        'description': 'Drawn on monthly shareholder certificates.',
        'managed': 'signature',
    },
    'login_background': {
        'label': 'Login page background',
        'description': 'Hero panel on the sign-in and OTP screens.',
        'managed': 'library',
    },
    'email_header': {
        'label': 'Email header image',
        'description': 'Optional banner used in branded system emails.',
        'managed': 'library',
    },
    'dashboard_banner': {
        'label': 'Dashboard banner',
        'description': 'Optional banner shown at the top of the staff dashboard.',
        'managed': 'library',
    },
}

LIBRARY_SETTING_KEY = 'media_library'
SLOT_SETTING_PREFIX = 'image_slot_'


def media_uploads_dir():
    path = Path(current_app.root_path) / 'static' / 'uploads' / 'media'
    path.mkdir(parents=True, exist_ok=True)
    return path


def _static_url(relative):
    if not relative:
        return None
    relative = str(relative).replace('\\', '/')
    try:
        from flask import has_request_context

        if has_request_context():
            return url_for('static', filename=relative)
    except RuntimeError:
        pass
    assets_root = (current_app.config.get('ASSETS_ROOT') or '/static').rstrip('/')
    return f'{assets_root}/{relative}'


def _filesystem_path(relative):
    if not relative:
        return None
    full = Path(current_app.root_path) / 'static' / str(relative).replace('\\', '/')
    return str(full) if full.is_file() else None


def _extension(filename):
    if not filename or '.' not in filename:
        return ''
    return filename.rsplit('.', 1)[-1].lower()


def _validate_image_file(file_storage):
    if not file_storage or not getattr(file_storage, 'filename', None):
        raise ValueError('Choose an image file to upload.')
    ext = _extension(file_storage.filename)
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError('Images must be PNG, JPG, WEBP, or GIF.')
    # Size check when stream supports seeking
    try:
        file_storage.stream.seek(0, 2)
        size = file_storage.stream.tell()
        file_storage.stream.seek(0)
        if size > MAX_IMAGE_BYTES:
            raise ValueError('Image must be 5 MB or smaller.')
    except (OSError, AttributeError):
        pass
    return ext


def _load_library():
    raw = SystemSetting.get(LIBRARY_SETTING_KEY) or '[]'
    try:
        data = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        data = []
    if not isinstance(data, list):
        data = []
    return data


def _save_library(items):
    SystemSetting.set(LIBRARY_SETTING_KEY, json.dumps(items))


def list_library_images():
    items = []
    for row in _load_library():
        relative = row.get('path') or ''
        items.append({
            'id': row.get('id'),
            'title': row.get('title') or row.get('original_name') or 'Image',
            'original_name': row.get('original_name') or '',
            'path': relative,
            'url': _static_url(relative),
            'filesystem_path': _filesystem_path(relative),
            'uploaded_at': row.get('uploaded_at') or '',
            'slot': row.get('slot') or '',
        })
    # Newest first
    items.sort(key=lambda row: row.get('uploaded_at') or '', reverse=True)
    return items


def upload_library_image(file_storage, title=None, slot=None):
    ext = _validate_image_file(file_storage)
    if slot and slot not in IMAGE_SLOTS:
        raise ValueError('Unknown image usage slot.')
    if slot in ('brand_logo', 'cert_signature'):
        raise ValueError('Use the dedicated Brand Logo or Signature controls for those assets.')

    safe_stem = secure_filename(Path(file_storage.filename).stem) or 'image'
    safe_stem = re.sub(r'[^a-zA-Z0-9_-]+', '-', safe_stem).strip('-')[:40] or 'image'
    image_id = uuid.uuid4().hex[:12]
    stored_name = f'{safe_stem}-{image_id}.{ext}'
    destination = media_uploads_dir() / stored_name
    file_storage.save(destination)

    relative = f'uploads/media/{stored_name}'
    item = {
        'id': image_id,
        'title': (title or safe_stem).strip()[:120],
        'original_name': file_storage.filename,
        'path': relative,
        'uploaded_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
        'slot': '',
    }
    library = _load_library()
    library.append(item)
    _save_library(library)

    if slot:
        assign_slot(slot, image_id)

    return item


def delete_library_image(image_id):
    library = _load_library()
    remaining = []
    deleted = None
    for row in library:
        if row.get('id') == image_id:
            deleted = row
            continue
        remaining.append(row)
    if not deleted:
        raise ValueError('Image not found.')

    # Clear any slots pointing at this image
    for slot in IMAGE_SLOTS:
        if get_slot_assignment(slot) == image_id:
            clear_slot(slot)

    relative = deleted.get('path') or ''
    full = _filesystem_path(relative)
    if full:
        Path(full).unlink(missing_ok=True)

    _save_library(remaining)
    return deleted


def get_slot_assignment(slot):
    if slot not in IMAGE_SLOTS:
        return None
    return (SystemSetting.get(f'{SLOT_SETTING_PREFIX}{slot}') or '').strip() or None


def clear_slot(slot):
    if slot not in IMAGE_SLOTS:
        return
    SystemSetting.set(f'{SLOT_SETTING_PREFIX}{slot}', '')
    # Clear library item slot markers
    library = _load_library()
    changed = False
    for row in library:
        if row.get('slot') == slot:
            row['slot'] = ''
            changed = True
    if changed:
        _save_library(library)


def assign_slot(slot, image_id):
    if slot not in IMAGE_SLOTS:
        raise ValueError('Unknown image usage slot.')
    meta = IMAGE_SLOTS[slot]
    if meta['managed'] != 'library':
        raise ValueError('That slot is managed by a dedicated upload control.')

    library = _load_library()
    found = None
    for row in library:
        if row.get('id') == image_id:
            found = row
            break
    if not found:
        raise ValueError('Image not found in the media library.')
    if not _filesystem_path(found.get('path')):
        raise ValueError('Image file is missing on disk. Re-upload it.')

    # One image per slot; clear previous assignment markers
    for row in library:
        if row.get('slot') == slot:
            row['slot'] = ''
    found['slot'] = slot
    _save_library(library)
    SystemSetting.set(f'{SLOT_SETTING_PREFIX}{slot}', image_id)
    return found


def get_slot_image(slot):
    """Return URL/path info for a library-managed slot, or None."""
    if slot not in IMAGE_SLOTS or IMAGE_SLOTS[slot]['managed'] != 'library':
        return None
    image_id = get_slot_assignment(slot)
    if not image_id:
        return None
    for row in list_library_images():
        if row['id'] == image_id and row.get('url'):
            return row
    return None


def get_application_images():
    """
    Snapshot of every managed application image for admin UI and templates.

    Includes brand logo, certificate signature, and assigned library slots.
    """
    from apps.services.brand_service import ensure_default_logo, get_brand_settings
    from apps.services.certificate_settings_service import get_certificate_settings

    ensure_default_logo()
    brand = get_brand_settings()
    cert = get_certificate_settings()

    slots = {}
    for key, meta in IMAGE_SLOTS.items():
        if meta['managed'] == 'brand':
            slots[key] = {
                'key': key,
                'label': meta['label'],
                'description': meta['description'],
                'managed': meta['managed'],
                'url': brand.get('logo_url'),
                'path': brand.get('logo_path'),
                'filesystem_path': brand.get('logo_filesystem_path'),
                'title': brand.get('company_name') or 'Brand logo',
            }
        elif meta['managed'] == 'signature':
            slots[key] = {
                'key': key,
                'label': meta['label'],
                'description': meta['description'],
                'managed': meta['managed'],
                'url': cert.get('signature_url'),
                'path': cert.get('signature_image_path'),
                'filesystem_path': cert.get('signature_filesystem_path'),
                'title': cert.get('signature_name') or 'Signature',
            }
        else:
            assigned = get_slot_image(key)
            slots[key] = {
                'key': key,
                'label': meta['label'],
                'description': meta['description'],
                'managed': meta['managed'],
                'url': assigned['url'] if assigned else None,
                'path': assigned['path'] if assigned else None,
                'filesystem_path': assigned['filesystem_path'] if assigned else None,
                'title': assigned['title'] if assigned else None,
                'image_id': assigned['id'] if assigned else None,
            }

    return {
        'slots': slots,
        'library': list_library_images(),
        'login_background_url': (slots['login_background'].get('url') if slots.get('login_background') else None),
        'email_header_url': (slots['email_header'].get('url') if slots.get('email_header') else None),
        'dashboard_banner_url': (slots['dashboard_banner'].get('url') if slots.get('dashboard_banner') else None),
    }
