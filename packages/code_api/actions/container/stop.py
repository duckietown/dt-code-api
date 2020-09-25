import docker.errors
from flask import Blueprint

from code_api.utils import get_client, response_ok, response_error

stop = Blueprint('container_stop', __name__)
__all__ = ['stop']


@stop.route('/container/stop/<string:container_name>')
def _stop(container_name):
    # get docker client
    client = get_client()
    # stop container
    try:
        container = client.containers.get(container_name)
        container.stop()
    except docker.errors.NotFound:
        return response_error(f'Container `{container_name}` not found')
    except (docker.errors.APIError, KeyError):
        pass
    # return status
    return response_ok({})
