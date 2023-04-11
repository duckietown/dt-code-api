import subprocess

from flask import Blueprint, request

from code_api.actions.stack import stack_get_fpath, stack_create
from code_api.utils import response_ok, response_error

up = Blueprint('stack_up', __name__)
__all__ = ['up']


@up.route('/stack/up/<string:stack_name>', methods=['POST'])
def _stack_up(stack_name: str):
    # create (or update) the stack
    stack_create(stack_name, request.json)
    # get pointer to stack
    stack_fpath = stack_get_fpath(stack_name)
    # perform action on stack
    cmd = [
        "docker-compose", "--file", stack_fpath, "up", "--detach"
    ]
    try:
        log = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True, text=True)
        return response_ok({"log": log})
    except subprocess.CalledProcessError as e:
        return response_error(str(e.output))
    except BaseException as e:
        return response_error(str(e))
