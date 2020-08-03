import json
import math
import time
import traceback
from threading import Thread
import docker.errors

from dt_class_utils import DTProcess

from code_api import logger
from code_api.constants import ModuleStatus, STATIC_MODULE_CFG, DT_MODULE_TYPE
from code_api.knowledge_base import DTModule
from code_api.utils import get_client, get_container_config, dt_label, indent_str


from .base import Job


class UpdateModuleJob(Job):

    def __init__(self, module: DTModule):
        self._module = module
        super().__init__('UpdateModuleJob[%s]' % self._module.name)

    def is_time(self):
        return True

    def step(self):
        module_name = self._module.name
        try:
            substep = 'Initializing'
            client = get_client()
            yield True, substep, 0

            # step 1 [+5%]: get list of containers based on the image we want to update
            substep = 'Fetching list of containers'
            logger.debug('Module {}: Fetching list of containers using it.'.format(module_name))
            containers = self._module.containers()
            yield True, substep, 5

            # step 2 [+80%]: update image
            substep = 'Pulling image'
            logger.debug('Module {}: Pulling new image.'.format(module_name))
            repository, tag = self._module.repository_and_tag()
            image_name = '{}:{}'.format(repository, tag)
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
                        yield True, substep, 5 + int(80 * len(completed_layers) / len(total_layers))
            except (docker.errors.APIError, Exception):
                msg = 'An error occurred while pulling a new version of the module ' + module_name
                logger.error(
                    '{}.\nThe error reads:\n\n{}'.format(
                        msg, indent_str(traceback.format_exc())
                    )
                )
                yield False, msg, -1
                return
            image = client.images.get(image_name)
            yield True, substep, 85

            # step 2.1 [+0-15%]: do not rename/remove/recreate THIS container
            if module_name == DT_MODULE_TYPE:
                logger.info('Module {}: Updated, but its containers are left untouched.'.format(
                    module_name
                ))
                yield True, 'Finished', 100
                return

            # step 3 [+5%]: stop and rename containers
            substep = 'Renamig old containers'
            logger.info('Module {}: Renaming old containers.'.format(module_name))
            i = 0
            containers_cfg = {}
            for container in containers:
                try:
                    container.reload()
                    old_name = container.name
                    if container.status == 'running':
                        logger.debug('Module {}: Stopping container {}.'.format(
                            module_name, old_name
                        ))
                        container.stop()
                    logger.debug('Module {}: Renaming container {} -> {}.'.format(
                        module_name, old_name, old_name + '-old'
                    ))
                    container.rename(old_name + '-old')
                    containers_cfg[old_name] = \
                        (get_container_config(container, image), container)
                except docker.errors.NotFound:
                    # the container is gone, that is OK
                    pass
                # ---
                yield True, substep, int(math.floor(85 + 5 * (i / len(containers))))
                i += 1
            yield True, substep, 90

            # step 4 [+5%]: recreate containers
            substep = 'Creating new containers'
            logger.info('Module {}: Recreate containers.'.format(module_name))
            i = 0
            to_remove = []
            for container_name, (old_container_cfg, old_container) in containers_cfg.items():
                # combine old container configuration with static container configuration
                container_cfg = {
                    **old_container_cfg,
                    **STATIC_MODULE_CFG
                }
                # add label container.owner
                container_cfg['labels'].update({dt_label('container.owner'): DT_MODULE_TYPE})
                # print some stats
                container_cfg['image'] = image_name
                container_cfg['name'] = container_name
                logger.info(
                    "Recreating container {} for module {};\n"
                    "Old configuration was:\n\n{}\n\n"
                    "New configuration is:\n\n{}\n".format(
                        container_name, module_name,
                        indent_str(json.dumps(old_container_cfg, sort_keys=True, indent=4)),
                        indent_str(json.dumps(container_cfg, sort_keys=True, indent=4))
                    )
                )
                # run new container
                try:
                    client.containers.run(
                        **container_cfg
                    )
                    to_remove.append(old_container)
                except (docker.errors.ContainerError, docker.errors.ImageNotFound,
                        docker.errors.APIError):
                    msg = 'An error occurred while recreating the container ' + container_name
                    logger.error(
                        '{}.\nThe error reads:\n{}'.format(
                            msg, indent_str(traceback.format_exc())
                        )
                    )
                    yield False, msg, -1
                    return
                # ---
                yield True, substep, int(math.floor(90 + 5 * (i / len(containers_cfg))))
                i += 1
            yield True, substep, 95

            # step 5 [5%]: remove old containers
            substep = 'Removing old containers'
            logger.debug('Module {}: Removing old containers.'.format(module_name))
            i = 0
            for container in to_remove:
                try:
                    logger.debug('Module {}: Removing container {}.'.format(
                        module_name, container.name
                    ))
                    container.remove()
                except (docker.errors.ContainerError, docker.errors.ImageNotFound,
                        docker.errors.APIError):
                    logger.warning(
                        'An error occurred while trying to remove the old container {}.'.format(
                            container.name
                        )
                    )
                # ---
                yield True, substep, int(math.floor(95 + 5 * (i / len(to_remove))))
            yield True, 'Finished', 100
            return
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
