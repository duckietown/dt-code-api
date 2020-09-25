from flask import Blueprint, request

from code_api.jobs import UpdateModuleWorker
from code_api.utils import response_ok, response_need_force
from code_api.knowledge_base import KnowledgeBase
from code_api.constants import ModuleStatus


update = Blueprint('modules_update', __name__)
__all__ = ['update']


NEED_FORCE_MSG = lambda lst: \
    f"The local version of module{'s' if len(lst) > 1 else ''} `{'`, `'.join(lst)}` " \
    "is ahead of the remote version. " \
    "This is normal when the local version is a development version. " \
    "These updates need to be forced. Use the argument `force=1` to force the update."


@update.route('/modules/update/all')
def _update_all():
    # get arguments
    forced = request.args.get('force', '0').lower() in ['1', 'yes', 'true']
    updating = set()
    # check force
    if not forced:
        need_force = []
        for name, module in KnowledgeBase.get('modules'):
            if module.status == ModuleStatus.AHEAD:
                need_force.append(name)
        if len(need_force) > 0:
            return response_need_force(NEED_FORCE_MSG(need_force))
    # update all modules
    for name, module in KnowledgeBase.get('modules'):
        # nothing to do if already updating
        if module.status in [ModuleStatus.UPDATING]:
            continue
        if module.status not in [ModuleStatus.BEHIND, ModuleStatus.AHEAD]:
            continue
        # spawn an update worker
        worker = UpdateModuleWorker(module)
        worker.start()
        updating.add(name)
    return response_ok({'updating': list(updating)})

