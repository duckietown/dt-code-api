from flask import Blueprint

from code_api.utils import response_not_implemented

status = Blueprint('status', __name__)


@status.route('/status')
def _status():
    return response_not_implemented('status')
