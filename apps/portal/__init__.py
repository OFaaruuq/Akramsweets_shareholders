from flask import Blueprint

blueprint = Blueprint('portal', __name__, url_prefix='/portal')

from apps.portal import routes  # noqa: E402,F401
