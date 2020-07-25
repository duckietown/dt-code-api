from flask import Blueprint

from code_api.jobs import UpdateModuleWorker
from code_api.utils import response_ok, response_error
from code_api.knowledge_base import KnowledgeBase
from code_api.constants import ModuleStatus


update = Blueprint('update', __name__)


@update.route('/update/<path:module_name>')
def _update_single(module_name):
    # update single module
    module = KnowledgeBase.get('modules', module_name, None)
    if module is None:
        return response_error("Module '%s' not found." % module_name)
    # only modules that need update can be updated (seems fair)
    if module.status != ModuleStatus.OUT_OF_DATE:
        return response_error(
            "Module '%s' does not seem to have an update available." % module_name)
    # spawn an update worker
    worker = UpdateModuleWorker(module)
    # TODO: re-enable
    # worker.start()
    return response_ok({})


@update.route('/update/all')
def _update_all():
    updating = set()
    # update all modules
    for name, module in KnowledgeBase.get('modules'):
        if module.status != ModuleStatus.OUT_OF_DATE:
            continue
        # spawn an update worker
        worker = UpdateModuleWorker(module)
        # TODO: re-enable
        # worker.start()
        updating.add(name)
    return response_ok({'updating': list(updating)})

