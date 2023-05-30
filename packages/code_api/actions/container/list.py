from typing import List

import docker.errors
from docker.models.containers import Container
from flask import Blueprint

from code_api.utils import response_ok, get_client, response_error


container_list = Blueprint('container_list', __name__)
__all__ = ['list']


@container_list.route('/container/list')
def _list():
    # get docker client
    client = get_client()
    # get list of docker container names
    try:
        list_container = client.containers.list()
        list_container_names = [c.attrs['Name'] for c in list_container]
        # return status
        return response_ok({'list_running_containers': list_container_names})
    except (docker.errors.APIError, KeyError) as e:
        return response_error(f"Error: {str(e)}")
        
