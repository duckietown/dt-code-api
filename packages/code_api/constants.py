import os
from enum import IntEnum

API_VERSION = '1.1'

CHECK_UPDATES_EVERY_MIN = max(1, int(os.environ.get('CHECK_UPDATES_EVERY_MIN', 30)))
RELEASES_ONLY = os.environ.get('RELEASES_ONLY', 'yes').lower() in ['1', 'yes', 'true']
DOCKER_REGISTRY = os.environ.get("DOCKER_REGISTRY", "docker.io")
DT_MODULE_TYPE = os.environ.get('DT_MODULE_TYPE', None)
STACKS_TMP_DIR = '/tmp/stacks'
AUTOBOOT_STACKS_DIR = '/data/autoboot'
AUTOBOOT_STACK_PROJECT_NAME = "duckietown"

CANONICAL_ARCH = {
    'arm': 'arm32v7',
    'arm32v7': 'arm32v7',
    'armv7l': 'arm32v7',
    'armhf': 'arm32v7',
    'x64': 'amd64',
    'x86_64': 'amd64',
    'amd64': 'amd64',
    'Intel 64': 'amd64',
    'aarch64': 'arm64v8',
    'arm64': 'arm64v8',
    'arm64v8': 'arm64v8',
    'armv8': 'arm64v8',
}

DOCKER_LABEL_DOMAIN = "org.duckietown.label"
DT_LAUNCHER_PREFIX = "dt-launcher-"
DOCKER_PUBLIC_INDEX_URL = lambda image, tag, registry=DOCKER_REGISTRY: \
    f"https://duckietown-public-storage.s3.amazonaws.com/docker/image/" \
    f"{registry}/{image}/{tag}/latest.json"

STATIC_MODULE_CFG = {
    'auto_remove': False,
    'remove': False,
    'detach': True
}


# NOTE: Please, refrain from changing these names, other modules rely on these names being stable
class ModuleStatus(IntEnum):
    UNKNOWN = -1
    UPDATED = 0
    BEHIND = 1
    AHEAD = 2
    NOT_FOUND = 5
    UPDATING = 10
    ERROR = 20


class ContainerStatus(IntEnum):
    NOTFOUND = -1
    UNKNOWN = 0
    CREATED = 1
    RUNNING = 2
    PAUSED = 3
    RESTARTING = 4
    REMOVING = 5
    EXITED = 6
    DEAD = 7
    REMOVED = 8

    @staticmethod
    def from_string(status):
        return {
            "created": ContainerStatus.CREATED,
            "running": ContainerStatus.RUNNING,
            "paused": ContainerStatus.PAUSED,
            "restarting": ContainerStatus.RESTARTING,
            "removing": ContainerStatus.REMOVING,
            "exited": ContainerStatus.EXITED,
            "dead": ContainerStatus.DEAD
        }[status]
