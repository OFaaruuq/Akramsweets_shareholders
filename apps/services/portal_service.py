from apps import db
from apps.models.user import User
from apps.services.audit_service import log_action


def portal_email_available(email, shareholder_id=None):
    """Return True if email can be used for this shareholder's portal login."""
    email = (email or '').strip().lower()
    if not email:
        return False
    existing = User.query.filter_by(email=email).first()
    if not existing:
        return True
    return existing.shareholder_id == shareholder_id


def create_shareholder_portal_user(shareholder, email, full_name, password, actor_id):
    email = email.strip().lower()
    existing = User.query.filter_by(email=email).first()
    if existing and existing.shareholder_id != shareholder.id:
        raise ValueError('That email is already used by another account.')

    if shareholder.user_account:
        user = shareholder.user_account
        user.email = email
        user.full_name = full_name.strip()
        user.role = User.ROLE_SHAREHOLDER
        user.shareholder_id = shareholder.id
        user.is_active = True
        action = 'update'
        created = False
    else:
        user = User(
            email=email,
            full_name=full_name.strip(),
            role=User.ROLE_SHAREHOLDER,
            shareholder_id=shareholder.id,
            is_active=True,
        )
        db.session.add(user)
        action = 'create'
        created = True

    user.set_password(password)
    db.session.commit()
    log_action(action, 'shareholder_portal_user', user.id, f'{shareholder.name} portal access')
    try:
        from apps.services.notification_service import notify_portal_credentials

        notify_portal_credentials(user, shareholder, password, created=created)
    except Exception:
        pass
    return user


def sync_portal_profile(shareholder, *, sync_email=False):
    """Keep portal display name (and optionally login email) aligned with the shareholder record."""
    user = shareholder.user_account
    if not user:
        return None

    changed = False
    if user.full_name != shareholder.name:
        user.full_name = shareholder.name
        changed = True

    if sync_email:
        email = (shareholder.email or '').strip().lower()
        if email and user.email != email:
            conflict = User.query.filter(User.email == email, User.id != user.id).first()
            if conflict:
                raise ValueError(
                    f'Cannot sync portal email to {email}: already used by another account.'
                )
            user.email = email
            changed = True

    if changed:
        db.session.commit()
        log_action('sync', 'shareholder_portal_user', user.id, f'{shareholder.name} profile sync')
    return user


def deactivate_shareholder_portal_user(shareholder, actor_id):
    user = shareholder.user_account
    if not user:
        return None

    user.is_active = False
    db.session.commit()
    log_action('deactivate', 'shareholder_portal_user', user.id, shareholder.name)
    return user


def reactivate_shareholder_portal_user(shareholder, actor_id):
    user = shareholder.user_account
    if not user:
        return None
    user.is_active = True
    db.session.commit()
    log_action('reactivate', 'shareholder_portal_user', user.id, shareholder.name)
    return user
