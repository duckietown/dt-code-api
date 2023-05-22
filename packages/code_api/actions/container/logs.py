import docker.errors
from docker.models.containers import Container
from flask import Blueprint

from code_api.utils import response_ok, get_client, response_error

logs = Blueprint('container_logs', __name__)
__all__ = ['logs']


@logs.route('/container/logs/<string:container_name>')
def _logs(container_name):
    # get docker client
    client = get_client()
    # get container logs
    try:
        container: Container = client.containers.get(container_name)
        container_logs_raw: bytes = container.logs()
    except docker.errors.NotFound:
        return response_error(f"Error: container '{container_name}' not found.")
    except (docker.errors.APIError, KeyError) as e:
        return response_error(f"Error: {str(e)}")
    # decode logs
    try:
        container_logs: str = container_logs_raw.decode("utf-8")
    except Exception as e:
        return response_error(f"Error occurred while decoding the container's logs: {str(e)}")
    # return logs
    return response_ok({'logs': container_logs})
