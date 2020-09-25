import json
from flask import Blueprint, request

from code_api.jobs import RunContainerWorker
from code_api.utils import response_ok, response_error
from code_api.knowledge_base import KnowledgeBase


run = Blueprint('container_run', __name__)
__all__ = ['run']


@run.route('/container/run/<path:module_name>')
def _run(module_name):
    module_name = module_name.rstrip('/')
    # get arguments
    configuration = request.args.get('configuration', 'default')
    launcher = request.args.get('launcher', 'default')
    name = request.args.get('name', None)
    # get module
    module = KnowledgeBase.get('modules', module_name, None)
    if module is None:
        return response_error(f"Module '{module_name}' not found.")
    # get container configuration
    custom_configuration = {}
    # noinspection PyBroadException
    try:
        custom_configuration = json.loads(request.data)
    except BaseException:
        pass
    # spawn a `run_container` worker
    worker = RunContainerWorker(
        module, configuration, launcher,
        container_name=name,
        custom_configuration=custom_configuration
    )
    worker.start()
    return response_ok({'job': worker.job.name})
