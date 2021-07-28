from code_api.knowledge_base import KnowledgeBase

from .update_checker import UpdateCheckerWorker
from .update_module import UpdateModuleWorker
from .run_container import RunContainerWorker
from .base import Job


def get_job(name) -> Job:
    return KnowledgeBase.get('jobs', name) if KnowledgeBase.has('jobs', name) else None


__all__ = [
    'get_job',
    'UpdateCheckerWorker',
    'UpdateModuleWorker',
    'RunContainerWorker'
]