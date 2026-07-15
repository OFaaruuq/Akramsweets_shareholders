from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from apps.auth import blueprint
from apps.auth.forms import LoginForm, OTPForm, ResendOTPForm
from apps.models.user import User
from apps.services.audit_service import log_action
from apps.services.otp_service import (
    begin_otp_challenge,
    clear_otp_session,
    mask_email,
    otp_enabled,
    otp_length,
    pending_otp_user,
    pop_remember_flag,
    resend_otp as send_new_otp,
    verify_otp_code,
)


@blueprint.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for(current_user.home_endpoint()))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.strip().lower()).first()
        if user and user.is_active and user.check_password(form.password.data):
            if not otp_enabled():
                login_user(user, remember=form.remember.data)
                log_action('login', 'user', user.id, f'{user.email} signed in', user=user)
                next_page = request.args.get('next')
                return redirect(next_page or url_for(user.home_endpoint()))

            ok, reason = begin_otp_challenge(user, remember=form.remember.data)
            if not ok:
                if reason == 'smtp_not_configured':
                    flash(
                        'Login verification email could not be sent. '
                        'Configure SMTP in .env or Settings → System.',
                        'danger',
                    )
                else:
                    flash(
                        'Could not send the verification code to your email. Please try again.',
                        'danger',
                    )
                return render_template('pages/auth-login.html', form=form, segment='auth-login')

            log_action('otp_sent', 'user', user.id, f'OTP emailed to {mask_email(user.email)}', user=user)
            flash(f'A verification code was sent to {mask_email(user.email)}.', 'success')
            next_page = request.args.get('next')
            if next_page:
                return redirect(url_for('auth.verify_otp', next=next_page))
            return redirect(url_for('auth.verify_otp'))

        flash('Invalid email or password.', 'danger')

    return render_template('pages/auth-login.html', form=form, segment='auth-login')


@blueprint.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    if current_user.is_authenticated:
        return redirect(url_for(current_user.home_endpoint()))

    user = pending_otp_user()
    if not user:
        flash('Please sign in with your email and password first.', 'warning')
        return redirect(url_for('auth.login'))

    form = OTPForm()
    resend_form = ResendOTPForm()
    if form.validate_on_submit():
        verified_user, status = verify_otp_code(form.code.data)
        if status == 'ok' and verified_user:
            remember = pop_remember_flag()
            login_user(verified_user, remember=remember)
            log_action(
                'login',
                'user',
                verified_user.id,
                f'{verified_user.email} signed in (OTP verified)',
                user=verified_user,
            )
            flash('Signed in successfully.', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for(verified_user.home_endpoint()))

        messages = {
            'invalid': 'Invalid verification code. Please try again.',
            'expired': 'That code has expired. Sign in again to get a new one.',
            'too_many_attempts': 'Too many incorrect attempts. Sign in again.',
            'no_pending_challenge': 'Your verification session expired. Please sign in again.',
            'no_otp': 'No verification code found. Please sign in again.',
        }
        flash(messages.get(status, 'Verification failed. Please try again.'), 'danger')
        if status in ('expired', 'too_many_attempts', 'no_pending_challenge', 'no_otp'):
            clear_otp_session()
            return redirect(url_for('auth.login'))

    return render_template(
        'pages/auth-verify-otp.html',
        form=form,
        resend_form=resend_form,
        masked_email=mask_email(user.email),
        otp_length=otp_length(),
        segment='auth-verify-otp',
    )


@blueprint.route('/resend-otp', methods=['POST'])
def resend_otp():
    if current_user.is_authenticated:
        return redirect(url_for(current_user.home_endpoint()))

    form = ResendOTPForm()
    if not form.validate_on_submit():
        flash('Could not resend the code. Please try again.', 'danger')
        return redirect(url_for('auth.verify_otp'))

    if not pending_otp_user():
        flash('Please sign in with your email and password first.', 'warning')
        return redirect(url_for('auth.login'))

    ok, reason = send_new_otp()
    if ok:
        user = pending_otp_user()
        if user:
            log_action(
                'otp_resend',
                'user',
                user.id,
                f'OTP resent to {mask_email(user.email)}',
                user=user,
            )
        flash('A new verification code has been sent to your email.', 'success')
    elif reason == 'smtp_not_configured':
        flash('SMTP is not configured — cannot resend the verification code.', 'danger')
    else:
        flash('Could not resend the verification code. Please try again.', 'danger')
    return redirect(url_for('auth.verify_otp'))


@blueprint.route('/logout')
@login_required
def logout():
    log_action('logout', 'user', current_user.id)
    clear_otp_session()
    logout_user()
    return redirect(url_for('auth.login'))


@blueprint.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    """Self-service profile photo + password for every logged-in user."""
    from apps import db
    from apps.auth.forms import ChangePasswordForm, ProfileAvatarForm
    from apps.services.avatar_service import clear_user_avatar, save_user_avatar

    avatar_form = ProfileAvatarForm(prefix='avatar')
    password_form = ChangePasswordForm(prefix='password')
    action = request.form.get('form_action') if request.method == 'POST' else None

    if action == 'avatar' and avatar_form.validate_on_submit():
        try:
            if avatar_form.remove_avatar.data:
                clear_user_avatar(current_user)
                db.session.commit()
                log_action('avatar_remove', 'user', current_user.id, current_user.email)
                flash('Profile photo removed. Default image restored.', 'success')
            elif avatar_form.avatar.data and getattr(avatar_form.avatar.data, 'filename', None):
                save_user_avatar(current_user, avatar_form.avatar.data)
                db.session.commit()
                log_action('avatar_update', 'user', current_user.id, current_user.email)
                flash('Profile photo updated.', 'success')
            else:
                flash('Choose an image to upload, or check remove.', 'warning')
        except ValueError as exc:
            flash(str(exc), 'danger')
        return redirect(url_for('auth.account'))

    if action == 'password' and password_form.validate_on_submit():
        if not current_user.check_password(password_form.current_password.data):
            flash('Current password is incorrect.', 'danger')
        else:
            current_user.set_password(password_form.new_password.data)
            db.session.commit()
            log_action('password_change', 'user', current_user.id, current_user.email)
            try:
                from apps.services.notification_service import notify_password_changed

                notify_password_changed(current_user)
            except Exception:
                pass
            flash('Password updated successfully.', 'success')
            return redirect(url_for('auth.account'))

    return render_template(
        'account/profile.html',
        avatar_form=avatar_form,
        password_form=password_form,
        segment='account-profile',
    )
