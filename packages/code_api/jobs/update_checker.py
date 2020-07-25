import re
import time
import traceback
from threading import Thread

from dt_class_utils import DTProcess
from dt_module_utils import set_module_unhealthy, set_module_healthy

from code_api.utils import \
    get_client, \
    get_endpoint_architecture, \
    get_duckietown_distro, \
    dt_label, \
    parse_time
from code_api.knowledge_base import KnowledgeBase, DTModule
from code_api.constants import ModuleStatus, CHECK_UPDATES_EVERY_MIN

from .base import Job

SOLID_STATUS = [ModuleStatus.UPDATED, ModuleStatus.BEHIND, ModuleStatus.AHEAD]
FROZEN_STATUS = [ModuleStatus.UPDATING]


class UpdateCheckerJob(Job):

    def __init__(self):
        super().__init__('UpdateCheckerJob')
        self._check_interval_time_sec = CHECK_UPDATES_EVERY_MIN * 60
        self._last_time_checked = 0
        # open Docker client
        self._docker = get_client()
        arch = get_endpoint_architecture()
        self._image_pattern = re.compile(f'^duckietown/(.+):{get_duckietown_distro()}-{arch}$')
        # ---
        self._logger.info('Updates checker set to check for updates every '
                          '%d minutes' % CHECK_UPDATES_EVERY_MIN)

    def is_time(self) -> bool:
        return (time.time() - self._last_time_checked) > self._check_interval_time_sec

    def step(self):
        self._logger.info('Rechecking the status of modules...')
        self._last_time_checked = time.time()

        # fetch list of images at the Docker endpoint
        images = list(self._docker.images.list())
        self._logger.debug('Found %d total images' % len(images))

        # we only update official duckietown images
        compatible_tags = set()
        for image in images:
            if len(image.tags) <= 0:
                continue
            if image.labels.get(dt_label('image.authoritative'), '0') != '1':
                continue
            found = False
            module_name = None
            module_tag = None
            # check all the tags
            for tag in image.tags:
                match = self._image_pattern.match(tag)
                if not match:
                    continue
                # this is a valid duckietown tag
                module_name = match.group(1)
                module_tag = tag
                compatible_tags.add(tag)
                KnowledgeBase.set('tags', module_name, tag)
                # check if there is already a tracked module with the same name
                if KnowledgeBase.has('modules', module_name):
                    module = KnowledgeBase.get('modules', module_name)
                    if module.image.id == image.id:
                        self._logger.debug('Module "%s" is still there' % module_name)
                        # the image is already in the KB, change its status to UNKNOWN
                        if module.status not in SOLID_STATUS + FROZEN_STATUS:
                            module.status = ModuleStatus.UNKNOWN
                        found = True
                        break
            # add a new module to the KB if this is a new image
            if not found and module_tag is not None:
                KnowledgeBase.set('modules', module_name, DTModule(image, module_tag))
                self._logger.info(' - Tracking new module "%s"' % module_name)

        # clean KB by removing tracked modules that are not there anymore
        to_be_removed = set()
        for name, module in KnowledgeBase.get('modules'):
            tag = KnowledgeBase.get('tags', name)
            if tag not in compatible_tags and module.status not in FROZEN_STATUS:
                self._logger.info(' - Untracking module "%s"' % tag)
                to_be_removed.add(name)
        for name in to_be_removed:
            KnowledgeBase.remove('modules', name)

        self._logger.info('Tracking %d total modules' % len(list(KnowledgeBase.get('modules'))))

        # check which modules need update
        for name, module in KnowledgeBase.get('modules'):
            # we leave modules that are updating alone
            if module.status in FROZEN_STATUS:
                continue

            # fetch remote image labels
            remote_labels = module.remote_labels()
            if remote_labels is None:
                self._logger.debug('Could not get remote labels for module "%s"' % name)
                # image is not available online
                if module.status not in SOLID_STATUS + FROZEN_STATUS:
                    module.status = ModuleStatus.NOT_FOUND
                continue

            # fetch local and remote build time
            image_labels = module.labels()
            time_lbl = dt_label('time')
            image_time_str = image_labels.get(time_lbl, 'ND')
            image_time = parse_time(image_time_str)
            remote_time_str = remote_labels.get(time_lbl, 'ND')
            remote_time = parse_time(remote_time_str)

            # error, up-to-date or to update
            if remote_time is None:
                self._logger.debug('Could not get remote build time for module "%s"' % name)
                # remote build time could not be fetched, error
                if module.status not in SOLID_STATUS + FROZEN_STATUS:
                    module.status = ModuleStatus.ERROR
                continue

            # fetch versions
            head_version_lbl = dt_label('code.version.head')
            closest_version_lbl = dt_label('code.version.closest')
            remote_version = remote_labels.get(head_version_lbl, 'ND')
            remote_version_closest = remote_labels.get(closest_version_lbl, 'ND')

            # update version in module
            module.remote_version = remote_version
            module.closest_remote_version = remote_version_closest

            # compare local and remote build time
            if image_time is None or image_time > remote_time:
                # module is ahead of remote
                module.status = ModuleStatus.AHEAD
            elif image_time == remote_time:
                # module is up-to-date
                module.status = ModuleStatus.UPDATED
            elif image_time < remote_time:
                tab = ' ' * 3
                self._logger.info(
                    f'Found new version for module "{name}":\n'
                    f'{tab}- Versions:\n'
                    f'{tab}{tab}- Local  (closest/head): '
                    f'{module.closest_version} \t/ {module.version}\n'
                    f'{tab}{tab}- Remote (closest/head): '
                    f'{remote_version_closest} \t/ {remote_version}\n'
                    f'{tab}- Build time:\n'
                    f'{tab}{tab}- Local: {image_time_str}\n'
                    f'{tab}{tab}- Remote: {remote_time_str}\n'
                )
                # the remote copy is newer than the local
                module.status = ModuleStatus.BEHIND



class UpdateCheckerWorker(Thread):

    def __init__(self):
        self._alive = True
        self._job = UpdateCheckerJob()
        self._sleeping_time_sec = CHECK_UPDATES_EVERY_MIN * 60
        self._last_time_checked = 0
        self._heartbeat_hz = 0.5
        super(UpdateCheckerWorker, self).__init__(target=self._work)
        # register shutdown callback
        DTProcess.get_instance().register_shutdown_callback(self._shutdown)

    def _shutdown(self):
        self._alive = False

    def _work(self):
        while self._alive:
            if self._job.is_time():
                try:
                    self._job.step()
                    set_module_healthy()
                except BaseException:
                    set_module_unhealthy()
                    traceback.print_exc()
            # ---
            time.sleep(1.0 / self._heartbeat_hz)
