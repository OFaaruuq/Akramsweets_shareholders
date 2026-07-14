# -*- encoding: utf-8 -*-

from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from importlib import import_module

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'warning'


@login_manager.user_loader
def load_user(user_id):
    from apps.models.user import User
    return User.query.get(int(user_id))


def register_extensions(app):
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)


def register_blueprints(app):
    for module_name in (
        'auth',
        'shareholders',
        'contacts',
        'periods',
        'app_settings',
        'reports',
        'portal',
        'users',
        'pages',
    ):
        package = import_module(f'apps.{module_name}')
        app.register_blueprint(package.blueprint)


def configure_database(app):
    from apps import models  # noqa: F401 — register all models with SQLAlchemy metadata
    from apps.db_utils import ensure_schema
    from apps.seed import seed_if_empty

    ensure_schema(app, db, seed_if_empty)

    with app.app_context():
        try:
            from apps.services.brand_service import ensure_default_brand_settings
            from apps.services.certificate_settings_service import ensure_default_certificate_settings
            from apps.models.settings import SystemSetting

            ensure_default_brand_settings()
            ensure_default_certificate_settings()
            # Sync SMTP from .env into settings when UI fields are empty
            if app.config.get('MAIL_SERVER') and not SystemSetting.get('mail_server'):
                SystemSetting.set('mail_server', app.config['MAIL_SERVER'])
            if app.config.get('MAIL_PORT') and not SystemSetting.get('mail_port'):
                SystemSetting.set('mail_port', str(app.config['MAIL_PORT']))
            if app.config.get('MAIL_USERNAME') and not SystemSetting.get('mail_username'):
                SystemSetting.set('mail_username', app.config['MAIL_USERNAME'])
            if app.config.get('MAIL_PASSWORD') and not SystemSetting.get('mail_password'):
                SystemSetting.set('mail_password', app.config['MAIL_PASSWORD'])
            if app.config.get('MAIL_FROM') and not SystemSetting.get('mail_from'):
                SystemSetting.set('mail_from', app.config['MAIL_FROM'])
        except Exception:
            pass

    @app.teardown_request
    def shutdown_session(exception=None):
        db.session.remove()


def create_app(config):
    app = Flask(__name__)
    app.config.from_object(config)
    register_extensions(app)
    register_blueprints(app)
    configure_database(app)

    @app.context_processor
    def inject_brand():
        try:
            from apps.services.brand_service import get_brand_settings

            return {'brand': get_brand_settings()}
        except Exception:
            return {'brand': None}

    @app.context_processor
    def inject_mail_status():
        try:
            from apps.services.mail_status_service import get_mail_delivery_status

            return {'mail_status': get_mail_delivery_status()}
        except Exception:
            return {'mail_status': None}

    @app.context_processor
    def inject_topbar():
        try:
            from flask import request
            from apps.services.topbar_service import get_shareholder_countries, get_topbar_notifications

            selected_code = None
            try:
                selected_code = request.args.get('country')
            except RuntimeError:
                selected_code = None
            country_data = get_shareholder_countries(selected_code=selected_code)
            notifications = get_topbar_notifications()
            return {
                'topbar_countries': country_data['countries'],
                'topbar_selected_country': country_data['selected'],
                'topbar_notifications': notifications['items'],
                'topbar_notification_count': notifications['count'],
            }
        except Exception:
            return {
                'topbar_countries': [],
                'topbar_selected_country': {'code': 'so', 'name': 'Somalia', 'flag': 'so.svg', 'count': 0},
                'topbar_notifications': [],
                'topbar_notification_count': 0,
            }

    return app
