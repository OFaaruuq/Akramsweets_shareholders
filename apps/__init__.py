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
    from apps import db

    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None


def register_extensions(app):
    db.init_app(app)
    from apps.db_utils import migrations_dir

    # Absolute path so flask/scripts work from any cwd (e.g. scripts/).
    migrate.init_app(app, db, directory=str(migrations_dir()))
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
            from apps.services.mudarabah_service import ensure_default_mudarabah_settings
            from apps.services.share_value_service import ensure_default_share_settings
            from apps.services.capital_withdrawal_service import ensure_default_withdrawal_settings

            ensure_default_mudarabah_settings()
            ensure_default_share_settings()
            ensure_default_withdrawal_settings()
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
            app.logger.exception('Startup settings sync failed (brand/certificate/SMTP defaults)')

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
    def inject_display_settings():
        try:
            from apps.services.display_settings_service import get_display_settings

            display = get_display_settings()
            return {
                'display': display,
                'currency_symbol': display['currency_symbol'],
                'company_name': display['company_name'],
                'share_value': display.get('share_value'),
                'share_value_label': display.get('share_value_label'),
            }
        except Exception:
            return {
                'display': None,
                'currency_symbol': '$',
                'company_name': 'Company',
                'share_value': None,
                'share_value_label': None,
            }

    @app.context_processor
    def inject_mudarabah_settings():
        try:
            from apps.services.mudarabah_service import get_mudarabah_settings
            from apps.services.capital_withdrawal_service import get_capital_return_deadline_months_label

            return {
                'mudarabah': get_mudarabah_settings(),
                'capital_return': get_capital_return_deadline_months_label(),
            }
        except Exception:
            return {
                'mudarabah': {
                    'shareholder_percent': 50,
                    'partner_percent': 50,
                    'shareholder_percent_label': '50',
                    'partner_percent_label': '50',
                    'partner_name': 'Managing Partner',
                    'pool_caption': "Shareholders' Pool (50%)",
                    'partner_caption': 'Managing Partner Share (50%)',
                    'label': '50% shareholders / 50% managing partner',
                },
                'capital_return': {
                    'days': 183,
                    'months': 6,
                    'label': 'up to 6 months (183 days)',
                    'short_label': '6 months',
                },
            }

    @app.context_processor
    def inject_app_images():
        try:
            from apps.services.media_service import get_application_images

            images = get_application_images()
            return {
                'app_images': images,
                'login_background_url': images.get('login_background_url'),
                'email_header_url': images.get('email_header_url'),
                'dashboard_banner_url': images.get('dashboard_banner_url'),
            }
        except Exception:
            return {
                'app_images': None,
                'login_background_url': None,
                'email_header_url': None,
                'dashboard_banner_url': None,
            }

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
