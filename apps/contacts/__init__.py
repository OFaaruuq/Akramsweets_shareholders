from flask import Blueprint

blueprint = Blueprint('contacts', __name__, url_prefix='/contacts')

from apps.contacts import routes  # noqa: E402,F401
