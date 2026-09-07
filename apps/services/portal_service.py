from apps import db
from apps.models.user import User
from apps.services.audit_service import log_action

LAST_SUPERADMIN_ERROR = (
    'Cannot remove Super Admin access from this Company Owner: they are the last Super Admin. '
    'Create another Super Admin first, or mark another shareholder as Company Owner.'
)


def _portal_role_for_shareholder(shareholder):
    if shareholder.is_owner and shareholder.is_active:
        return User.ROLE_OWNER
    return User.ROLE_SHAREHOLDER


def can_revoke_company_owner_superadmin(shareholder):
    """Whether unchecking Company Owner (or deactivating that login) is safe."""
    user = shareholder.user_account
    if not user or user.role != User.ROLE_OWNER:
        return True, None
    if User.active_superadmin_count(exclude_id=user.id) < 1:
        return False, LAST_SUPERADMIN_ERROR
    return True, None


def sync_company_owner_superadmin(shareholder, *, actor=None, commit=False):
    """
    Company Owner shareholders with a login are Super Admins and see the full system.

    Promotes or demotes the linked user. Does not create a login — that still happens
    when portal access is created on the shareholder form.
    """
    user = shareholder.user_account
    if not user:
        return None

    desired = _portal_role_for_shareholder(shareholder)
    changed = False

    if desired == User.ROLE_OWNER:
        if user.role != User.ROLE_OWNER:
            user.role = User.ROLE_OWNER
            changed = True
        if not user.is_active:
            user.is_active = True
            changed = True
        if user.shareholder_id != shareholder.id:
            user.shareholder_id = shareholder.id
            changed = True
        action = 'promote'
        details = f'Company owner shareholder granted Super Admin: {user.email}'
    elif user.shareholder_id == shareholder.id and user.role == User.ROLE_OWNER:
        ok, error = can_revoke_company_owner_superadmin(shareholder)
        if not ok:
            raise ValueError(error)
        user.role = User.ROLE_SHAREHOLDER
        changed = True
        action = 'demote'
        details = f'Company owner flag removed; Super Admin revoked: {user.email}'
    else:
        action = None
        details = None

    if changed:
        db.session.flush()
        if commit:
            db.session.commit()
            log_action(action, 'staff_user', user.id, details, user=actor)
    return user


def sync_all_company_owner_superadmins(*, actor=None):
    """Promote existing Company Owner logins (and demote those who no longer qualify)."""
    from apps.models.shareholder import Shareholder

    shareholders = Shareholder.query.all()
    changed = False
    for sh in shareholders:
        if sh.is_owner and sh.is_active and sh.user_account:
            before = sh.user_account.role
            sync_company_owner_superadmin(sh, actor=actor, commit=False)
            if sh.user_account.role != before:
                changed = True
    for sh in shareholders:
        if (not sh.is_owner or not sh.is_active) and sh.user_account:
            before = sh.user_account.role
            try:
                sync_company_owner_superadmin(sh, actor=actor, commit=False)
            except ValueError:
                # Keep the last Super Admin even if the register flag was cleared.
                continue
            if sh.user_account.role != before:
                changed = True
    if changed:
        db.session.commit()
    return changed


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

    role = _portal_role_for_shareholder(shareholder)
    if shareholder.user_account:
        user = shareholder.user_account
        user.email = email
        user.full_name = full_name.strip()
        user.role = role
        user.shareholder_id = shareholder.id
        user.is_active = True
        action = 'update'
        created = False
    else:
        user = User(
            email=email,
            full_name=full_name.strip(),
            role=role,
            shareholder_id=shareholder.id,
            is_active=True,
        )
        db.session.add(user)
        action = 'create'
        created = True

    user.set_password(password)
    db.session.commit()
    access_label = (
        f'{shareholder.name} portal access (Super Admin)'
        if user.role == User.ROLE_OWNER
        else f'{shareholder.name} portal access'
    )
    log_action(action, 'shareholder_portal_user', user.id, access_label)
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

    if shareholder.is_owner and shareholder.is_active:
        raise ValueError(
            'This login is the Company Owner Super Admin account. '
            'Uncheck Company owner on the shareholder record first, or manage the account under Staff Users.'
        )
    if user.role == User.ROLE_OWNER:
        ok, error = can_revoke_company_owner_superadmin(shareholder)
        if not ok:
            raise ValueError(error)

    user.is_active = False
    db.session.commit()
    log_action('deactivate', 'shareholder_portal_user', user.id, shareholder.name)
    return user


def reactivate_shareholder_portal_user(shareholder, actor_id):
    user = shareholder.user_account
    if not user:
        return None
    user.is_active = True
    if shareholder.is_owner and shareholder.is_active:
        user.role = User.ROLE_OWNER
    db.session.commit()
    log_action('reactivate', 'shareholder_portal_user', user.id, shareholder.name)
    return user
