import subprocess
import traceback
from threading import Thread

import docker.errors
import time

from code_api import logger
from code_api.constants import ModuleStatus, DT_MODULE_TYPE, \
    AUTOBOOT_STACK_PROJECT_NAME
from code_api.knowledge_base import DTModule
from code_api.utils import get_client, indent_str, \
    get_default_docker_stack_fpath
from dt_class_utils import DTProcess
from .base import Job


class UpdateModuleJob(Job):

    def __init__(self, module: DTModule):
        self._module = module
        super().__init__('UpdateModuleJob[%s]' % self._module.name)

    def is_time(self):
        return True

    def step(self):
        module_name = self._module.name
        # noinspection PyBroadException
        try:
            substep = 'Initializing'
            client = get_client()
            yield True, substep, 0

            # step 1 [+5%]: get list of containers based on the image we want to update
            substep = 'Fetching list of containers'
            logger.debug('Module {}: Fetching list of containers using it.'.format(module_name))
            containers = self._module.containers()
            logger.debug('Containers:\n\t- {}'.format(
                '(none)' if len(containers) <= 0 else '\n\t- '.join([c.name for c in containers])
            ))
            yield True, substep, 5

            # step 2 [+80%]: update image
            substep = 'Pulling image'
            logger.debug('Module {}: Pulling new image.'.format(module_name))
            repository, tag = self._module.repository_and_tag()
            total_layers = set()
            completed_layers = set()
            try:
                for step in client.api.pull(repository, tag, stream=True, decode=True):
                    if 'error' in step:
                        return
                    if 'status' not in step or 'id' not in step:
                        continue
                    total_layers.add(step['id'])
                    if step['status'] in ['Pull complete', 'Already exists']:
                        completed_layers.add(step['id'])
                    # compute progress
                    if len(total_layers) > 0:
                        progress = 5 + int(80 * len(completed_layers) / len(total_layers))
                        yield True, substep, progress
            except (docker.errors.APIError, Exception):
                msg = 'An error occurred while pulling a new version of the module ' + module_name
                logger.error(
                    '{}.\nThe error reads:\n\n{}'.format(
                        msg, indent_str(traceback.format_exc())
                    )
                )
                yield False, msg, -1
                return
            yield True, substep, 85

            # step 3 [+0-15%]: do not rename/remove/recreate THIS container
            if module_name == DT_MODULE_TYPE:
                logger.info('Module {}: Updated, but its containers are left untouched.'.format(
                    module_name
                ))
                yield True, 'Finished', 100
                return

            # step 4 [+15%]: find services in default stack using this image
            substep = 'Recreating services'
            services = self._module.default_services()
            for i, service in enumerate(services):
                # get stack file path
                stack_fpath = get_default_docker_stack_fpath()
                # re-apply stack (this service only)
                cmd = [
                    "docker-compose",
                    "--file", stack_fpath,
                    "--project-name", AUTOBOOT_STACK_PROJECT_NAME,
                    "up",
                    "--detach",
                    service.name
                ]
                logger.debug(f"$ {cmd}")
                # noinspection PyBroadException
                try:
                    subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
                except BaseException:
                    traceback.print_last()
                # ---
                progress = 85 + int(15 * ((i + 1) / len(services)))
                yield True, substep, progress
            # ---
            yield True, substep, 100
        except BaseException:
            logger.error(
                'An error occurred while trying to update the module {}.\n'
                'This should not have happened. Please, open an issue on '
                'https://github.com/duckietown/{}/issues.\n\n'
                'The error reads:\n{}'.format(
                    module_name, DT_MODULE_TYPE, indent_str(traceback.format_exc())
                )
            )
            yield False, 'Generic error', -1
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
                # noinspection PyBroadException
                try:
                    # tell everybody we are UPDATING
                    self._module.status = ModuleStatus.UPDATING
                    # monitor progress
                    last_progress = 0
                    for ok, substep, progress in self._job.step():
                        if not self._alive:
                            return
                        self._module.progress = progress
                        self._module.step = substep
                        if not ok:
                            break
                        logger.debug('Updating module {}: Progress {:d}% ({})'.format(
                            self._module.name, progress, substep
                        ))
                        last_progress = progress

                    # check if 100 was yielded
                    if last_progress == 100:
                        # tell everybody we are done
                        self._module.status = ModuleStatus.UPDATED
                    else:
                        # something weird happened, transition to ERROR state
                        self._module.status = ModuleStatus.ERROR
                        # reset status after 10 seconds
                        UpdateModuleWorkerResetter(self._module).start()
                    # ---
                    self._module.progress = 0
                except BaseException:
                    msg = 'An error occurred while updating the module ' + self._module.name
                    # something weird happened, transition to ERROR state
                    self._module.status = ModuleStatus.ERROR
                    self._module.step = msg
                    # reset status after 10 seconds
                    UpdateModuleWorkerResetter(self._module).start()
                    # ---
                    logger.warning(
                        '{}.\nThe error reads:\n\n{}'.format(
                            msg, indent_str(traceback.format_exc())
                        )
                    )
                # we are done here
                return
            # ---
            time.sleep(1.0 / self._heartbeat_hz)


class UpdateModuleWorkerResetter(Thread):

    def __init__(self, module):
        self._alive = True
        self._heartbeat_hz = 0.3
        self._module = module
        self._action_time = time.time() + 10
        super(UpdateModuleWorkerResetter, self).__init__(target=self._work)
        # register shutdown callback
        DTProcess.get_instance().register_shutdown_callback(self._shutdown)

    def _shutdown(self):
        self._alive = False

    def _work(self):
        while self._alive:
            if time.time() > self._action_time:
                # it is action time, reset module status
                self._module.reset()
                return
            time.sleep(1.0 / self._heartbeat_hz)
