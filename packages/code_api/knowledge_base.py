from typing import Dict, Iterator, Tuple, Any, Union, List
from docker.models.images import Image as DockerImage
from docker.models.containers import Container as DockerContainer

from .constants import ModuleStatus
from .utils import inspect_remote_image, dt_label, get_client


class NotSet:
    pass


class _KnowledgeBase(dict):

    def get(self, group: str, key: str = None, default: Any = NotSet) -> \
            Union[Iterator[Tuple[str, Any]], Any]:
        if key is not None:
            key = '/%s/%s' % (group, key)
            if key not in self:
                if default != NotSet:
                    return default
            return self[key]
        # spin up an iterator on the group
        return self.group(group)

    def group(self, group: str) -> Iterator[Tuple[str, Any]]:
        # this avoids issue with long iterations and multi-thread access
        keys = list(self.keys())
        # spin up an iterator on the group
        for key in keys:
            gkey = '/%s/' % group
            if key.startswith(gkey):
                yield key[len(gkey):], self[key]

    def set(self, group: str, key: str, value: Any):
        key = '/%s/%s' % (group, key)
        self[key] = value

    def has(self, group: str, key: str) -> bool:
        key = '/%s/%s' % (group, key)
        return key in self

    def remove(self, group: str, key: str):
        key = '/%s/%s' % (group, key)
        if key in self:
            del self[key]


class DTModule(object):

    def __init__(self, image, tag):
        if not isinstance(image, DockerImage):
            raise ValueError('Image parameter must be of type docker.models.images.Image, '
                             'got %s instead.' % str(type(image)))
        # ---
        self._image = image
        self._tag = tag
        self._head_version = self._image.labels.get(dt_label('code.version.head'), 'ND')
        self._closest_version = self._image.labels.get(dt_label('code.version.closest'), 'ND')
        self._remote_version = 'ND'
        self._closest_remote_version = 'ND'
        self._progress = None
        self._step = None
        self._status = ModuleStatus.UNKNOWN

    @property
    def name(self):
        module_name, _ = self.repository_and_tag()
        return module_name.split('/')[1]

    @property
    def image(self) -> DockerImage:
        return self._image

    @property
    def tag(self) -> str:
        return self._tag

    @property
    def status(self) -> ModuleStatus:
        return self._status

    @status.setter
    def status(self, status):
        if not isinstance(status, ModuleStatus):
            raise ValueError("Value of 'status' must be of type code_api.constants.ModuleStatus, "
                             "got %s instead" % str(type(status)))
        self._status = status

    @property
    def version(self) -> str:
        return self._head_version

    @property
    def closest_version(self) -> str:
        return self._closest_version

    @property
    def remote_version(self) -> str:
        return self._remote_version

    @remote_version.setter
    def remote_version(self, new_version):
        self._remote_version = new_version

    @property
    def closest_remote_version(self) -> str:
        return self._closest_remote_version

    @closest_remote_version.setter
    def closest_remote_version(self, new_version):
        self._closest_remote_version = new_version

    @property
    def step(self) -> str:
        return self._step

    @step.setter
    def step(self, step: str):
        self._step = step

    @property
    def progress(self) -> int:
        return self._progress

    @progress.setter
    def progress(self, progress: int):
        self._progress = progress

    def repository_and_tag(self) -> Union[Tuple[str, str], Tuple[None, None]]:
        try:
            image, tag = self._tag.split(':')
            return image, tag
        except BaseException:
            pass
        return None, None

    def labels(self) -> Dict[str, str]:
        return self._image.labels

    def remote_labels(self) -> Union[Dict[str, str], None]:
        labels = None
        metadata = None
        # get image name in image and tag separately
        image, tag = self.repository_and_tag()
        if image is None or tag is None:
            return None
        # ---
        try:
            metadata = inspect_remote_image(image, tag)
        except BaseException:
            pass
        # ---
        if metadata is not None and isinstance(metadata, dict):
            remote_config = metadata['config'] if 'config' in metadata else {}
            labels = remote_config['Labels'] if 'Labels' in remote_config else None
        return labels

    def containers(self, status='all') -> List[DockerContainer]:
        valid_status = ['all', 'restarting', 'running', 'paused', 'exited']
        if status not in valid_status:
            raise ValueError("Invalid status '{}'. Valid choices are {}".format(
                status, ', '.join(valid_status)
            ))
        # ---
        client = get_client()
        return client.containers.list(
            all=True,
            filters={
                'ancestor': self._tag,
                **({'status': status} if status != 'all' else {})
            }
        )


KnowledgeBase = _KnowledgeBase()

__all__ = [
    'KnowledgeBase',
    'DTModule'
]
