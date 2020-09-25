import traceback

from flask import Blueprint, request

from code_api.jobs import get_job
from code_api.utils import response_ok
from code_api.knowledge_base import KnowledgeBase
from code_api.constants import ModuleStatus


status = Blueprint('modules_status', __name__)
__all__ = ['status']


@status.route('/modules/status')
def _status():
    # recheck can be forced
    if request.args.get('force', '0').lower() in ['1', 'yes', 'true']:
        job = get_job('UpdateCheckerJob')
        if job:
            try:
                job.step()
            except BaseException:
                traceback.print_exc()
    # return current status
    data = {}
    for tag, module in KnowledgeBase.get('modules'):
        data[tag] = {
            'status': module.status.name,
            'status_txt': module.step,
            'version': {
                'local': {
                    'head': module.version,
                    'closest': module.closest_version
                },
                'remote': {
                    'head': module.remote_version,
                    'closest': module.closest_remote_version
                }
            },
            **({'progress': module.progress} if module.status == ModuleStatus.UPDATING else {})
        }
    return response_ok(data)
