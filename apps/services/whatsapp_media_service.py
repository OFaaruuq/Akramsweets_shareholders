"""Temporary public media files for Twilio WhatsApp (PDF certificates / reports)."""

from __future__ import annotations

import logging
import secrets
import time
from pathlib import Path

from flask import current_app, has_app_context, url_for

from apps.models.settings import SystemSetting

logger = logging.getLogger(__name__)

# token -> {path, expires_at, filename}
_MEDIA_INDEX: dict[str, dict] = {}
_TTL_SECONDS = 60 * 60 * 6  # 6 hours


def _media_root() -> Path:
    root = Path(current_app.root_path).parent / 'media' / 'whatsapp_tmp'
    root.mkdir(parents=True, exist_ok=True)
    return root


def public_base_url() -> str:
    """Prefer Settings / env PUBLIC_BASE_URL so Twilio can fetch media & callbacks."""
    if has_app_context():
        stored = (SystemSetting.get('public_base_url') or '').strip().rstrip('/')
        if stored:
            return stored
        cfg = (current_app.config.get('PUBLIC_BASE_URL') or '').strip().rstrip('/')
        if cfg:
            return cfg
    import os

    return (os.getenv('PUBLIC_BASE_URL') or '').strip().rstrip('/')


def absolute_url(endpoint: str, **kwargs) -> str | None:
    base = public_base_url()
    try:
        path = url_for(endpoint, _external=False, **kwargs)
    except Exception:
        return None
    if base:
        return f'{base}{path}'
    try:
        return url_for(endpoint, _external=True, **kwargs)
    except Exception:
        return None


def store_whatsapp_media(data: bytes, filename: str) -> tuple[str, str] | None:
    """
    Persist bytes and return (token, public_url).

    Requires a resolvable PUBLIC_BASE_URL (or request host) so Twilio can download.
    """
    if not data:
        return None
    token = secrets.token_urlsafe(24)
    safe_name = ''.join(ch if ch.isalnum() or ch in '._-' else '_' for ch in (filename or 'file.bin'))
    path = _media_root() / f'{token}_{safe_name}'
    path.write_bytes(data)
    _MEDIA_INDEX[token] = {
        'path': str(path),
        'filename': safe_name,
        'expires_at': time.time() + _TTL_SECONDS,
    }
    url = absolute_url('whatsapp.media_file', token=token, filename=safe_name)
    if not url or url.startswith('/'):
        logger.warning(
            'WhatsApp media stored but PUBLIC_BASE_URL is missing — Twilio cannot fetch PDFs. '
            'Set PUBLIC_BASE_URL in .env or Settings.'
        )
        return token, url or ''
    return token, url


def resolve_media(token: str, filename: str | None = None) -> tuple[Path, str] | None:
    _cleanup_expired()
    meta = _MEDIA_INDEX.get(token)
    if not meta:
        # Allow disk recovery after process restart within TTL window via filename match
        root = _media_root()
        matches = list(root.glob(f'{token}_*'))
        if not matches:
            return None
        path = matches[0]
        return path, path.name.split('_', 1)[-1] if '_' in path.name else path.name
    if meta['expires_at'] < time.time():
        _purge_token(token)
        return None
    path = Path(meta['path'])
    if not path.is_file():
        _purge_token(token)
        return None
    return path, meta.get('filename') or path.name


def _purge_token(token: str) -> None:
    meta = _MEDIA_INDEX.pop(token, None)
    if not meta:
        return
    try:
        Path(meta['path']).unlink(missing_ok=True)
    except OSError:
        pass


def _cleanup_expired() -> None:
    now = time.time()
    for token, meta in list(_MEDIA_INDEX.items()):
        if meta.get('expires_at', 0) < now:
            _purge_token(token)


def attach_pdfs_enabled() -> bool:
    raw = SystemSetting.get('whatsapp_attach_pdfs')
    if raw is None or str(raw).strip() == '':
        return True
    return str(raw).strip().lower() in ('1', 'true', 'yes', 'on')
