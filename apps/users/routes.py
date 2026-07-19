from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user

from apps import db
from apps.auth.decorators import management_required
from apps.auth.forms import StaffUserForm
from apps.models.user import User
from apps.services.audit_service import log_action
from apps.services.avatar_service import clear_user_avatar, save_user_avatar
from apps.users import blueprint


def _staff_role_choices(actor):
    """Admins cannot assign Super Admin (Owner); only Owner can."""
    choices = [
        (User.ROLE_ADMIN, User.ROLE_LABELS[User.ROLE_ADMIN]),
        (User.ROLE_FINANCE, User.ROLE_LABELS[User.ROLE_FINANCE]),
    ]
    if actor.is_superadmin():
        choices.insert(0, (User.ROLE_OWNER, User.ROLE_LABELS[User.ROLE_OWNER]))
    return choices


def _active_owner_count(exclude_id=None):
    query = User.query.filter_by(role=User.ROLE_OWNER, is_active=True)
    if exclude_id:
        query = query.filter(User.id != exclude_id)
    return query.count()


def _apply_avatar_from_form(user, form):
    """Apply avatar upload/remove from StaffUserForm. Returns flash message or None."""
    if form.remove_avatar.data:
        clear_user_avatar(user)
        return 'Profile photo removed.'
    if form.avatar.data and getattr(form.avatar.data, 'filename', None):
        save_user_avatar(user, form.avatar.data)
        return 'Profile photo updated.'
    return None


@blueprint.route('/')
@management_required
def list_users():
    if not current_user.can_manage_users():
        flash('You do not have permission to manage users.', 'danger')
        return redirect(url_for('pages.dashboard'))

    users = User.query.filter(User.role != User.ROLE_SHAREHOLDER).order_by(User.full_name).all()
    return render_template(
        'users/list.html',
        users=users,
        segment='users',
        is_superadmin=current_user.is_superadmin(),
    )


@blueprint.route('/create', methods=['GET', 'POST'])
@management_required
def create_user():
    if not current_user.can_manage_users():
        flash('You do not have permission to manage users.', 'danger')
        return redirect(url_for('pages.dashboard'))

    form = StaffUserForm()
    form.role.choices = _staff_role_choices(current_user)
    if form.validate_on_submit():
        if not form.password.data:
            flash('Password is required for new users.', 'danger')
        elif form.role.data == User.ROLE_OWNER and not current_user.can_assign_owner_role():
            flash('Only the system owner (Super Admin) can create another Super Admin.', 'danger')
        else:
            email = form.email.data.strip().lower()
            if User.query.filter_by(email=email).first():
                flash('A user with that email already exists.', 'danger')
            else:
                user = User(
                    email=email,
                    full_name=form.full_name.data.strip(),
                    phone=(form.phone.data or '').strip() or None,
                    role=form.role.data,
                    is_active=form.is_active.data,
                )
                user.set_password(form.password.data)
                db.session.add(user)
                db.session.flush()  # need user.id before avatar filename
                try:
                    _apply_avatar_from_form(user, form)
                except ValueError as exc:
                    db.session.rollback()
                    flash(str(exc), 'danger')
                    return render_template(
                        'users/form.html',
                        form=form,
                        title='Add Staff User',
                        segment='users',
                        is_superadmin=current_user.is_superadmin(),
                    )
                db.session.commit()
                log_action('create', 'staff_user', user.id, f'{user.email} ({user.role})')
                try:
                    from apps.services.notification_service import notify_staff_invite

                    notify_staff_invite(user, form.password.data, created_by=current_user)
                except Exception:
                    pass
                flash(
                    'Staff user created. Invite sent by email + WhatsApp when those channels are configured.',
                    'success',
                )
                return redirect(url_for('users.list_users'))

    return render_template(
        'users/form.html',
        form=form,
        title='Add Staff User',
        segment='users',
        is_superadmin=current_user.is_superadmin(),
    )


@blueprint.route('/<int:user_id>/edit', methods=['GET', 'POST'])
@management_required
def edit_user(user_id):
    if not current_user.can_manage_users():
        flash('You do not have permission to manage users.', 'danger')
        return redirect(url_for('pages.dashboard'))

    user = User.query.filter(User.id == user_id, User.role != User.ROLE_SHAREHOLDER).first_or_404()
    if not current_user.can_manage_target_user(user):
        flash('Only the system owner (Super Admin) can manage Super Admin accounts.', 'danger')
        return redirect(url_for('users.list_users'))

    form = StaffUserForm(obj=user)
    form.role.choices = _staff_role_choices(current_user)
    # Keep current owner role visible when editing an owner as superadmin
    if user.role == User.ROLE_OWNER and current_user.is_superadmin():
        if (User.ROLE_OWNER, User.ROLE_LABELS[User.ROLE_OWNER]) not in form.role.choices:
            form.role.choices = _staff_role_choices(current_user)

    if form.validate_on_submit():
        new_role = form.role.data
        if new_role == User.ROLE_OWNER and not current_user.can_assign_owner_role():
            flash('Only the system owner (Super Admin) can assign the Super Admin role.', 'danger')
            return render_template(
                'users/form.html',
                form=form,
                title='Edit Staff User',
                user=user,
                segment='users',
                is_superadmin=current_user.is_superadmin(),
            )

        # Protect the last active Super Admin from demotion / deactivation
        demoting_owner = user.role == User.ROLE_OWNER and new_role != User.ROLE_OWNER
        deactivating_owner = user.role == User.ROLE_OWNER and user.is_active and not form.is_active.data
        if (demoting_owner or deactivating_owner) and _active_owner_count(exclude_id=user.id) < 1:
            flash(
                'Cannot demote or deactivate the last active Super Admin (Owner). '
                'Create another Super Admin first.',
                'danger',
            )
            return render_template(
                'users/form.html',
                form=form,
                title='Edit Staff User',
                user=user,
                segment='users',
                is_superadmin=current_user.is_superadmin(),
            )

        user.full_name = form.full_name.data.strip()
        user.phone = (form.phone.data or '').strip() or None
        user.role = new_role
        user.is_active = form.is_active.data
        new_email = form.email.data.strip().lower()
        if new_email != user.email:
            existing = User.query.filter_by(email=new_email).first()
            if existing and existing.id != user.id:
                flash('That email is already in use.', 'danger')
                return render_template(
                    'users/form.html',
                    form=form,
                    title='Edit Staff User',
                    user=user,
                    segment='users',
                    is_superadmin=current_user.is_superadmin(),
                )
            user.email = new_email
        if form.password.data:
            user.set_password(form.password.data)
            details = f'{user.email} (password reset)'
        else:
            details = user.email
        try:
            avatar_note = _apply_avatar_from_form(user, form)
        except ValueError as exc:
            flash(str(exc), 'danger')
            return render_template(
                'users/form.html',
                form=form,
                title='Edit Staff User',
                user=user,
                segment='users',
                is_superadmin=current_user.is_superadmin(),
            )
        if avatar_note:
            details = f'{details}; {avatar_note}'
        details = f'{details} [{user.role}]'
        db.session.commit()
        log_action('update', 'staff_user', user.id, details)
        flash('Staff user updated.', 'success')
        return redirect(url_for('users.list_users'))

    if request.method == 'GET':
        form.password.data = ''

    return render_template(
        'users/form.html',
        form=form,
        title='Edit Staff User',
        user=user,
        segment='users',
        is_superadmin=current_user.is_superadmin(),
    )
