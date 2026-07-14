from flask import Blueprint

blueprint = Blueprint('auth', __name__, url_prefix='/auth')

from apps.auth import routes  # noqa: E402,F401
