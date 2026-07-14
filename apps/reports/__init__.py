from flask import Blueprint

blueprint = Blueprint('reports', __name__, url_prefix='/reports')

from apps.reports import routes  # noqa: E402,F401
