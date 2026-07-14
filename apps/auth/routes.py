from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from apps.auth import blueprint
from apps.auth.forms import LoginForm
from apps.models.user import User
from apps.services.audit_service import log_action


@blueprint.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for(current_user.home_endpoint()))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.strip().lower()).first()
        if user and user.is_active and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            log_action('login', 'user', user.id, f'{user.email} signed in')
            next_page = request.args.get('next')
            return redirect(next_page or url_for(user.home_endpoint()))
        flash('Invalid email or password.', 'danger')

    return render_template('pages/auth-login.html', form=form, segment='auth-login')


@blueprint.route('/logout')
@login_required
def logout():
    log_action('logout', 'user', current_user.id)
    logout_user()
    return redirect(url_for('auth.login'))
