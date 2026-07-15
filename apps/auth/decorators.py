from functools import wraps

from flask import flash, redirect, url_for
from flask_login import current_user, login_required


def _redirect_home():
    return redirect(url_for(current_user.home_endpoint()))


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role not in roles and not current_user.is_management():
                flash('You do not have permission to access that page.', 'danger')
                return _redirect_home()
            return view(*args, **kwargs)

        return wrapped

    return decorator


def management_required(view):
    return role_required('owner', 'admin')(view)


def owner_required(view):
    """Super Admin (Owner) only — highest privilege gate."""

    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_superadmin():
            flash('Only the system owner (Super Admin) can access that page.', 'danger')
            return _redirect_home()
        return view(*args, **kwargs)

    return wrapped


def finance_or_management_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.can_enter_financials():
            flash('You do not have permission to access that page.', 'danger')
            return _redirect_home()
        return view(*args, **kwargs)

    return wrapped


def staff_required(view):
    """Block shareholder portal users from staff-only pages."""

    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.is_shareholder():
            flash('You do not have permission to access that page.', 'warning')
            return redirect(url_for('pages.dashboard'))
        return view(*args, **kwargs)

    return wrapped


def shareholder_portal_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_shareholder():
            flash('You do not have permission to access that page.', 'danger')
            return _redirect_home()
        return view(*args, **kwargs)

    return wrapped
