from flask import Blueprint

blueprint = Blueprint('periods', __name__, url_prefix='/periods')

from apps.periods import routes  # noqa: E402,F401
