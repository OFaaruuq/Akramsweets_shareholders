from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import BooleanField, PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional, Regexp


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=4, max=128)])
    remember = BooleanField('Remember me')
    submit = SubmitField('Log In')


class OTPForm(FlaskForm):
    code = StringField(
        'Verification code',
        validators=[
            DataRequired(message='Enter the verification code from your email.'),
            Length(min=4, max=8),
            Regexp(r'^\d+$', message='The code must contain digits only.'),
        ],
    )
    submit = SubmitField('Verify & Sign In')


class ResendOTPForm(FlaskForm):
    submit = SubmitField('Resend code')


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current password', validators=[DataRequired(), Length(min=4, max=128)])
    new_password = PasswordField('New password', validators=[DataRequired(), Length(min=6, max=128)])
    confirm_password = PasswordField('Confirm new password', validators=[
        DataRequired(),
        Length(min=6, max=128),
        EqualTo('new_password', message='Passwords must match.'),
    ])
    submit = SubmitField('Update Password')


class ProfileAvatarForm(FlaskForm):
    avatar = FileField(
        'Profile image',
        validators=[
            Optional(),
            FileAllowed(['png', 'jpg', 'jpeg', 'webp', 'gif'], 'Images only!'),
        ],
    )
    remove_avatar = BooleanField('Remove current photo (use default)')
    submit = SubmitField('Update Profile Photo')


class ShareholderPortalAccountForm(FlaskForm):
    email = StringField('Portal login email', validators=[DataRequired(), Email(), Length(max=120)])
    full_name = StringField('Display name', validators=[DataRequired(), Length(max=120)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=128)])
    submit = SubmitField('Save Portal Access')


class StaffUserForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    full_name = StringField('Full name', validators=[DataRequired(), Length(max=120)])
    role = SelectField('Role', choices=[], validators=[DataRequired()])
    password = PasswordField('Password', validators=[Optional(), Length(min=6, max=128)])
    is_active = BooleanField('Active', default=True)
    avatar = FileField(
        'Profile image',
        validators=[
            Optional(),
            FileAllowed(['png', 'jpg', 'jpeg', 'webp', 'gif'], 'Images only!'),
        ],
    )
    remove_avatar = BooleanField('Remove current photo')
    submit = SubmitField('Save User')
