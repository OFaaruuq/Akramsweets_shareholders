from flask import Blueprint

blueprint = Blueprint('app_settings', __name__, url_prefix='/settings')

from apps.app_settings import routes  # noqa: E402,F401
