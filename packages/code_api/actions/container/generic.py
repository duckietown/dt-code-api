import docker.errors
from flask import Blueprint

from code_api.utils import get_client, response_ok, response_error

SUPPORTED_ACTIONS = [
    'start', 'restart', 'stop', 'kill', 'pause', 'unpause'
]

generic = Blueprint('container_generic', __name__)
__all__ = ['generic']


@generic.route('/container/<string:action>/<string:container_name>')
def _generic(action, container_name):
    # validate action
    if action not in SUPPORTED_ACTIONS:
        return response_error(f"The action '{action}' is not supported.")
    # get docker client
    client = get_client()
    # restart container
    try:
        container = client.containers.get(container_name)
        handler = getattr(container, action)
        handler()
    except docker.errors.NotFound:
        return response_error(f'Container `{container_name}` not found')
    except (docker.errors.APIError, KeyError):
        pass
    # return status
    return response_ok({})
