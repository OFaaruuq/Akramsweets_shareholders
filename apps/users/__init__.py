from flask import Blueprint

blueprint = Blueprint('users', __name__, url_prefix='/users')

from apps.users import routes  # noqa: E402,F401
