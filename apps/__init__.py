# -*- encoding: utf-8 -*-

from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from importlib import import_module

db = SQLAlchemy()
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
    login_manager.init_app(app)
    csrf.init_app(app)


def register_blueprints(app):
    for module_name in ('auth', 'shareholders', 'periods', 'app_settings', 'reports', 'portal', 'users', 'pages'):
        package = import_module(f'apps.{module_name}')
        app.register_blueprint(package.blueprint)


def configure_database(app):
    from apps.db_utils import ensure_schema
    from apps.seed import seed_if_empty

    ensure_schema(app, db, seed_if_empty)

    with app.app_context():
        try:
            from apps.services.brand_service import ensure_default_brand_settings

            ensure_default_brand_settings()
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
    def inject_topbar():
        try:
            from apps.services.topbar_service import get_shareholder_countries, get_topbar_notifications

            country_data = get_shareholder_countries()
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
