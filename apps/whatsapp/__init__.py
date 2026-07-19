from flask import Blueprint

blueprint = Blueprint('whatsapp', __name__, url_prefix='/whatsapp')

from apps.whatsapp import routes  # noqa: E402, F401
