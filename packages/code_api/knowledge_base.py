import dataclasses
import os
import re
import traceback
from re import Pattern
from typing import Dict, Iterator, Tuple, Any, Union, List, Optional

import yaml
from docker.models.images import Image as DockerImage
from docker.models.containers import Container as DockerContainer

from .constants import ModuleStatus, AUTOBOOT_STACKS_DIR, DOCKER_REGISTRY
from .utils import fetch_image_from_index, dt_label, get_client


class NotSet:
    pass


@dataclasses.dataclass
class DockerService:
    name: str
    configuration: dict


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

    DOCKER_COMPOSE_IMAGE_REGEX = r'\$\{[^}]*\}'

    def __init__(self, image, tag):
        if not isinstance(image, DockerImage):
            raise ValueError('Image parameter must be of type docker.models.images.Image, '
                             'got %s instead.' % str(type(image)))
        # ---
        self._image = image
        self._tag = tag
        # ---
        self._head_version = None
        self._closest_version = None
        self._remote_version = None
        self._closest_remote_version = None
        self._progress = None
        self._step = None
        self._status = None
        # ---
        self.reset()

    def reset(self):
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

    @property
    def image_creation_time(self) -> str:
        return self._image.attrs.get("Created", "ND")

    @property
    def remote_image_creation_time(self) -> str:
        # get image name in image and tag separately
        image, tag = self.repository_and_tag()
        if image is None or tag is None:
            return "ND"
        # ---
        try:
            metadata = fetch_image_from_index(image, tag)
            return metadata["image"].get("Created", "ND")
        except KeyError:
            traceback.print_last()
        except BaseException:
            pass
        # ---
        return "ND"

    def repository_and_tag(self) -> Union[Tuple[str, str], Tuple[None, None]]:
        try:
            image, tag = self._tag.split(':')
            return image, tag
        except BaseException:
            pass
        return None, None

    def labels(self) -> Dict[str, str]:
        return self._image.labels

    def remote_labels(self) -> Optional[Dict[str, str]]:
        labels = None
        metadata = None
        # get image name in image and tag separately
        image, tag = self.repository_and_tag()
        if image is None or tag is None:
            return None
        # ---
        try:
            metadata = fetch_image_from_index(image, tag)
        except BaseException:
            pass
        # ---
        if metadata is not None and isinstance(metadata, dict):
            labels = metadata.get('labels', None)
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

    def default_services(self) -> List[DockerService]:
        robot_type: str = os.environ.get('ROBOT_TYPE', '__NOTSET__')
        robot_stack_fpath: str = os.path.join(AUTOBOOT_STACKS_DIR, f"{robot_type}.yaml")
        module_image = f"{DOCKER_REGISTRY}/{self._tag}"
        # make sure the stack file is available
        if not os.path.isfile(robot_stack_fpath):
            print(f"WARNING: Autoboot stack file '{robot_stack_fpath}' not found.")
            return []
        # load stack file
        with open(robot_stack_fpath, "rt") as fin:
            stack = yaml.safe_load(fin)
        # get services from stack
        services = []
        pattern: Pattern = re.compile(self.DOCKER_COMPOSE_IMAGE_REGEX)
        for srv_name, srv_config in stack.get("services", {}).items():
            # sanitize image
            image: str = srv_config["image"]
            for e in pattern.finditer(image):
                orig: str = e.group(0)
                key, default = orig[2:-1].split(":-", maxsplit=1)
                # use given docker registry
                if key == "REGISTRY":
                    default = DOCKER_REGISTRY
                # replace variables in image name
                image = image.replace(orig, default)
            # check if there is a match
            if module_image == image:
                # add service to list
                services.append(DockerService(
                    name=srv_name,
                    configuration=srv_config
                ))
        return services


KnowledgeBase = _KnowledgeBase()

__all__ = [
    'KnowledgeBase',
    'DTModule'
]
