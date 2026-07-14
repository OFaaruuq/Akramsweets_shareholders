from flask import Blueprint

blueprint = Blueprint('shareholders', __name__, url_prefix='/shareholders')

from apps.shareholders import routes  # noqa: E402,F401
