from flask import Blueprint, request

from code_api.jobs import UpdateModuleWorker
from code_api.utils import response_ok, response_error, response_need_force
from code_api.knowledge_base import KnowledgeBase
from code_api.constants import ModuleStatus


update = Blueprint('module_update', __name__)
__all__ = ['update']


NEED_FORCE_MSG = lambda mod: \
    f"The local version of module `{mod}` is ahead of the remote version. " \
    "This is normal when the local version is a development version. " \
    "These updates need to be forced. Use the argument `force=1` to force the update."


@update.route('/module/update/<path:module_name>')
def _update_single(module_name):
    # get arguments
    forced = request.args.get('force', '0').lower() in ['1', 'yes', 'true']
    # update single module
    module = KnowledgeBase.get('modules', module_name, None)
    if module is None:
        return response_error(f"Module '{module_name}' not found.")
    # nothing to do if already updating
    if module.status in [ModuleStatus.UPDATING]:
        return response_ok({})
    # only modules that need update can be updated (seems fair)
    if module.status not in [ModuleStatus.BEHIND, ModuleStatus.AHEAD]:
        return response_error(f"Module '{module_name}' does not seem to have an update available.")
    # modules that are ahead need to be forced
    if module.status == ModuleStatus.AHEAD and not forced:
        return response_need_force(NEED_FORCE_MSG(module_name))
    # spawn an update worker
    worker = UpdateModuleWorker(module)
    worker.start()
    return response_ok({})
