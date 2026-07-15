from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user

from apps import db
from apps.auth.decorators import management_required
from apps.auth.forms import StaffUserForm
from apps.models.user import User
from apps.services.audit_service import log_action
from apps.users import blueprint


STAFF_ROLES = [
    (User.ROLE_OWNER, 'Owner / Senior Management'),
    (User.ROLE_ADMIN, 'System Administrator'),
    (User.ROLE_FINANCE, 'Finance / Accounts Staff'),
]


@blueprint.route('/')
@management_required
def list_users():
    if not current_user.can_manage_users():
        flash('You do not have permission to manage users.', 'danger')
        return redirect(url_for('pages.dashboard'))

    users = User.query.filter(User.role != User.ROLE_SHAREHOLDER).order_by(User.full_name).all()
    return render_template('users/list.html', users=users, segment='users')


@blueprint.route('/create', methods=['GET', 'POST'])
@management_required
def create_user():
    if not current_user.can_manage_users():
        flash('You do not have permission to manage users.', 'danger')
        return redirect(url_for('pages.dashboard'))

    form = StaffUserForm()
    form.role.choices = STAFF_ROLES
    if form.validate_on_submit():
        if not form.password.data:
            flash('Password is required for new users.', 'danger')
        else:
            email = form.email.data.strip().lower()
            if User.query.filter_by(email=email).first():
                flash('A user with that email already exists.', 'danger')
            else:
                user = User(
                    email=email,
                    full_name=form.full_name.data.strip(),
                    role=form.role.data,
                    is_active=form.is_active.data,
                )
                user.set_password(form.password.data)
                db.session.add(user)
                db.session.commit()
                log_action('create', 'staff_user', user.id, user.email)
                try:
                    from apps.services.notification_service import notify_staff_invite

                    notify_staff_invite(user, form.password.data, created_by=current_user)
                except Exception:
                    pass
                flash('Staff user created. An invite email was queued if SMTP is configured.', 'success')
                return redirect(url_for('users.list_users'))

    return render_template('users/form.html', form=form, title='Add Staff User', segment='users')


@blueprint.route('/<int:user_id>/edit', methods=['GET', 'POST'])
@management_required
def edit_user(user_id):
    if not current_user.can_manage_users():
        flash('You do not have permission to manage users.', 'danger')
        return redirect(url_for('pages.dashboard'))

    user = User.query.filter(User.id == user_id, User.role != User.ROLE_SHAREHOLDER).first_or_404()
    form = StaffUserForm(obj=user)
    form.role.choices = STAFF_ROLES

    if form.validate_on_submit():
        user.full_name = form.full_name.data.strip()
        user.role = form.role.data
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
                )
            user.email = new_email
        if form.password.data:
            user.set_password(form.password.data)
            details = f'{user.email} (password reset)'
        else:
            details = user.email
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
    )
