import subprocess

from flask import Blueprint

from code_api.actions.stack import stack_get_fpath
from code_api.utils import response_ok, response_error

down = Blueprint('stack_down', __name__)
__all__ = ['down']


@down.route('/stack/down/<string:stack_name>')
def _stack_down(stack_name: str):
    # get pointer to stack
    stack_fpath = stack_get_fpath(stack_name)
    # perform action on stack
    cmd = [
        "docker-compose", "--file", stack_fpath, "down"
    ]
    try:
        log = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True, text=True)
        return response_ok({"log": log})
    except subprocess.CalledProcessError as e:
        return response_error(str(e.output))
    except BaseException as e:
        return response_error(str(e))
