import time
import traceback
from threading import Thread

from dt_class_utils import DTProcess
from dt_module_utils import set_module_unhealthy

from .base import Job
from code_api.knowledge_base import DTModule
from code_api.utils import get_client
from code_api.constants import ModuleStatus


class UpdateModuleJob(Job):

    def __init__(self, module: DTModule):
        self._module = module
        super().__init__('UpdateModuleJob[%s]' % self._module.name)

    def is_time(self):
        return True

    def step(self):
        try:
            client = get_client()
            repository, tag = self._module.repository_and_tag()
            total_layers = set()
            completed_layers = set()
            for step in client.api.pull(repository, tag, stream=True, decode=True):
                if 'status' not in step or 'id' not in step:
                    continue
                total_layers.add(step['id'])
                if step['status'] in ['Pull complete', 'Already exists']:
                    completed_layers.add(step['id'])
                # compute progress
                if len(total_layers) > 0:
                    yield int(100 * len(completed_layers) / len(total_layers))
            yield 100
        except KeyboardInterrupt:
            return


class UpdateModuleWorker(Thread):

    def __init__(self, module):
        self._alive = True
        self._heartbeat_hz = 0.3
        self._module = module
        self._job = UpdateModuleJob(self._module)
        super(UpdateModuleWorker, self).__init__(target=self._work)
        # register shutdown callback
        DTProcess.get_instance().register_shutdown_callback(self._shutdown)

    def _shutdown(self):
        self._alive = False

    def _work(self):
        while self._alive:
            if self._job.is_time():
                try:
                    # tell everybody we are UPDATING
                    self._module.status = ModuleStatus.UPDATING
                    # monitor progress
                    for progress in self._job.step():
                        if not self._alive:
                            return
                        self._module.progress = progress
                    # tell everybody we are done
                    self._module.status = ModuleStatus.UPDATED
                except BaseException:
                    set_module_unhealthy()
                    traceback.print_exc()
            # ---
            time.sleep(1.0 / self._heartbeat_hz)