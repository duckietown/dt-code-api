import json
import uuid
import time
import traceback
from threading import Thread, Semaphore
import docker.errors

from dt_class_utils import DTProcess

from code_api import logger
from code_api.constants import STATIC_MODULE_CFG, DT_MODULE_TYPE, ContainerStatus
from code_api.knowledge_base import DTModule
from code_api.utils import get_client, dt_label, indent_str, \
    docker_compose_to_docker_sdk_config, dt_launcher

from .base import Job

GOOD_CONTAINER_STATES = [
    ContainerStatus.UNKNOWN,
    ContainerStatus.CREATED,
    ContainerStatus.RUNNING,
    ContainerStatus.PAUSED,
    ContainerStatus.RESTARTING
]


class RunContainerJob(Job):

    def __init__(self, module: DTModule, configuration: str = 'default', launcher: str = 'default',
                 container_name: str = None, custom_configuration: dict = None):
        # ---
        self._module = module
        self._configuration_name = configuration
        self._launcher = launcher
        self._container_name = container_name
        self._custom_configuration = custom_configuration or dict()
        self._configuration = {}
        self._container = None
        self._lock = Semaphore(1)
        self._container_status = ContainerStatus.UNKNOWN
        # ---
        super().__init__(f'RunContainerJob[{self._module.name}][{str(uuid.uuid4())[:8]}]')

    @property
    def status(self):
        return self._container_status

    def is_time(self):
        return self._container is None

    def step(self):
        client = get_client()
        # lock
        self._lock.acquire()
        if not self.is_time():
            # update status
            try:
                self._container.reload()
                self._container_status = ContainerStatus.from_string(self._container.status)
            except (docker.errors.NotFound, KeyError):
                self._container_status = ContainerStatus.REMOVED
            # release lock
            self._lock.release()
            return True, None
        # make sure the container name is not taken
        if self._container_name:
            try:
                container = client.containers.get(self._container_name)
                # start container if stopped
                if container.status in ['exited', 'dead', 'created']:
                    container.start()
                    return True, None
                # resume container if paused
                if container.status in ['paused']:
                    container.unpause()
                    return True, None
                # if we are here, it means that we found another container with the same name
                return False, f'Container `{self._container_name}` already exists.'
            except (docker.errors.NotFound, docker.errors.APIError):
                pass
        # get module labels
        labels = self._module.labels()
        # get module image
        repository, tag = self._module.repository_and_tag()
        image_name = '{}:{}'.format(repository, tag)
        # get configuration from image
        configuration = labels.get(
            dt_label(f'image.configuration.{self._configuration_name}'), None)
        if configuration is None:
            # release lock
            self._lock.release()
            return False, f'Module `{self._module.name}` has no ' \
                          f'configuration `{self._configuration_name}`'
        # combine module configuration, custom configuration, and static container configuration
        module_configuration = json.loads(configuration)
        container_cfg = {
            **docker_compose_to_docker_sdk_config(module_configuration),
            **docker_compose_to_docker_sdk_config(self._custom_configuration),
            **STATIC_MODULE_CFG,
            'labels': {
                dt_label('container.owner'): DT_MODULE_TYPE
            },
            'image': image_name,
            'name': self._container_name,
            'command': dt_launcher(self._launcher)
        }
        container_name_str = f' {self._container_name}' if self._container_name else ''
        # print some stats
        logger.info(
            "Running container{} for module {} with configuration:\n\n{}\n".format(
                container_name_str, self._module.name,
                indent_str(json.dumps(container_cfg, sort_keys=True, indent=4))
            )
        )
        # run new container
        try:
            self._container = client.containers.run(
                **container_cfg
            )
        except (docker.errors.ContainerError, docker.errors.ImageNotFound,
                docker.errors.APIError):
            msg = f'An error occurred while running the container{container_name_str}.\n' \
                  f'The error reads:\n{indent_str(traceback.format_exc())}\n'
            logger.error(msg)
            # release lock
            self._lock.release()
            return False, msg
        # release lock
        self._lock.release()
        # ---
        return True, None


class RunContainerWorker(Thread):

    def __init__(self, module: DTModule, configuration: str = 'default', launcher: str = 'default',
                 container_name: str = None, custom_configuration: dict = None):
        self._alive = True
        self._module = module
        self._heartbeat_hz = 0.2
        # create job
        self._job = RunContainerJob(self._module, configuration, launcher, container_name,
                                    custom_configuration)
        super(RunContainerWorker, self).__init__(target=self._work)
        # register shutdown callback
        DTProcess.get_instance().register_shutdown_callback(self._shutdown)

    @property
    def job(self):
        return self._job

    def _shutdown(self):
        self._alive = False

    def _work(self):
        while self._alive:
            success, message = self._job.step()
            # on error
            if not success:
                msg = f'An error occurred while performing the job {self._job.name}.'
                if message is not None:
                    msg += f'\nThe error reads:\n{indent_str(message)}\n'
                logger.error(msg)
                # terminate this worker
                self._shutdown()
                continue
            # on container stopped
            if self._job.status not in GOOD_CONTAINER_STATES:
                # terminate this worker
                self._shutdown()
                continue
            # ---
            time.sleep(1.0 / self._heartbeat_hz)
        logger.debug(f'Worker {self._job.name}[Worker] terminated.')
