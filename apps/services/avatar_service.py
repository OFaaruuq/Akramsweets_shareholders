"""Per-user profile avatars (staff + shareholder portal accounts)."""

from __future__ import annotations

from pathlib import Path

from flask import current_app, url_for

ALLOWED_AVATAR_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
MAX_AVATAR_BYTES = 5 * 1024 * 1024  # 5 MB
DEFAULT_AVATAR_STATIC = 'images/users/profile.jpg'


def avatar_uploads_dir():
    path = Path(current_app.root_path) / 'static' / 'uploads' / 'avatars'
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


def user_avatar_url(user):
    """Public URL for a user's avatar — always returns a usable image."""
    path = getattr(user, 'avatar_path', None) if user else None
    if path and _filesystem_path(path):
        return _static_url(path)
    return _static_url(DEFAULT_AVATAR_STATIC)


def user_has_custom_avatar(user):
    path = getattr(user, 'avatar_path', None) if user else None
    return bool(path and _filesystem_path(path))


def save_user_avatar(user, file_storage):
    if not user or not getattr(user, 'id', None):
        raise ValueError('Save the user before uploading an avatar.')
    if not file_storage or not getattr(file_storage, 'filename', None):
        return None

    ext = _extension(file_storage.filename)
    if ext not in ALLOWED_AVATAR_EXTENSIONS:
        raise ValueError('Profile image must be a PNG, JPG, WEBP, or GIF.')

    # Optional size check when stream supports seeking
    try:
        file_storage.stream.seek(0, 2)
        size = file_storage.stream.tell()
        file_storage.stream.seek(0)
        if size > MAX_AVATAR_BYTES:
            raise ValueError('Profile image must be 5 MB or smaller.')
    except (OSError, AttributeError):
        pass

    clear_user_avatar_file(user)

    stored_name = f'user-{user.id}.{ext}'
    destination = avatar_uploads_dir() / stored_name
    file_storage.save(destination)
    relative = f'uploads/avatars/{stored_name}'
    user.avatar_path = relative
    return relative


def clear_user_avatar_file(user):
    """Delete the avatar file on disk without clearing the DB column."""
    path = getattr(user, 'avatar_path', None)
    if not path:
        return
    full = Path(current_app.root_path) / 'static' / str(path).replace('\\', '/')
    if full.is_file() and 'uploads/avatars/' in str(path).replace('\\', '/'):
        full.unlink(missing_ok=True)


def clear_user_avatar(user):
    clear_user_avatar_file(user)
    if user is not None:
        user.avatar_path = None
