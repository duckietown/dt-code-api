import docker.errors
from flask import Blueprint

from code_api.utils import get_client, response_ok, response_error

restart = Blueprint('container_restart', __name__)
__all__ = ['restart']


@restart.route('/container/restart/<string:container_name>')
def _restart(container_name):
    # get docker client
    client = get_client()
    # restart container
    try:
        container = client.containers.get(container_name)
        container.restart()
    except docker.errors.NotFound:
        return response_error(f'Container `{container_name}` not found')
    except (docker.errors.APIError, KeyError):
        pass
    # return status
    return response_ok({})
