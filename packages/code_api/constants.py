import os
from enum import IntEnum


CHECK_UPDATES_EVERY_MIN = int(os.environ.get('CHECK_UPDATES_EVERY_MIN', 10))
RELEASES_ONLY = os.environ.get('RELEASES_ONLY', 'yes').lower() in ['1', 'yes', 'true']

CANONICAL_ARCH = {
    'arm': 'arm32v7',
    'arm32v7': 'arm32v7',
    'armv7l': 'arm32v7',
    'armhf': 'arm32v7',
    'x64': 'amd64',
    'x86_64': 'amd64',
    'amd64': 'amd64',
    'Intel 64': 'amd64',
    'arm64': 'arm64v8',
    'arm64v8': 'arm64v8',
    'armv8': 'arm64v8',
    'aarch64': 'arm64v8'
}

DOCKER_LABEL_DOMAIN = "org.duckietown.label"

DOCKER_HUB_API_URL = {
    'token':
        'https://auth.docker.io/token?scope=repository:{image}:pull&service=registry.docker.io',
    'digest':
        'https://registry-1.docker.io/v2/{image}/manifests/{tag}',
    'inspect':
        'https://registry-1.docker.io/v2/{image}/blobs/{digest}'
}


class ModuleStatus(IntEnum):
    UNKNOWN = -1
    UP_TO_DATE = 0
    OUT_OF_DATE = 1
    NOT_FOUND = 2
    UPDATING = 10
    ERROR = 20
