import docker.errors
from flask import Blueprint

from code_api.constants import ContainerStatus
from code_api.utils import response_ok, get_client


status = Blueprint('container_status', __name__)
__all__ = ['status']


@status.route('/container/status/<string:container_name>')
def _status(container_name):
    # get docker client
    client = get_client()
    # get container status
    try:
        container = client.containers.get(container_name)
        container_status = ContainerStatus.from_string(container.status)
    except docker.errors.NotFound:
        container_status = ContainerStatus.NOTFOUND
    except (docker.errors.APIError, KeyError):
        container_status = ContainerStatus.UNKNOWN
    # return status
    return response_ok({'status': str(container_status.name)})
