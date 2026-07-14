# -*- encoding: utf-8 -*-


from flask import Blueprint

blueprint = Blueprint(
    'pages',
    __name__,
    url_prefix=''
)

from apps.pages import routes  # noqa: E402,F401
