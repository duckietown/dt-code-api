import subprocess

from flask import Blueprint

from code_api.actions.stack import stack_exists, stack_get_fpath
from code_api.utils import response_ok, response_error

SUPPORTED_ACTIONS = [
    'start', 'restart', 'stop', 'kill', 'pause', 'unpause'
]

generic = Blueprint('stack_generic', __name__)
__all__ = ['generic']


@generic.route('/stack/<string:action>/<string:stack_name>')
def _generic(action, stack_name):
    # validate action
    if action not in SUPPORTED_ACTIONS:
        return response_error(f"The action '{action}' is not supported")
    # make sure the stack exists
    if not stack_exists(stack_name):
        return response_error(f"Stack '{stack_name}' not found")
    # get pointer to stack
    stack_fpath = stack_get_fpath(stack_name)
    # perform action on stack
    cmd = [
        "docker-compose", "--file", stack_fpath, action
    ]
    try:
        log = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True, text=True)
        return response_ok({"log": log})
    except subprocess.CalledProcessError as e:
        return response_error(str(e.output))
    except BaseException as e:
        return response_error(str(e))
