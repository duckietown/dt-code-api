import os
import json
import docker
import requests
from flask import jsonify
from datetime import datetime

from docker.models.containers import Container as DockerContainer
from docker.models.images import Image as DockerImage

from .constants import CANONICAL_ARCH, DOCKER_LABEL_DOMAIN, DOCKER_HUB_API_URL


def response_ok(data, *args, **kwargs):
    return jsonify({
        'status': 'ok',
        'message': None,
        'data': data
    })


def response_error(message, *args, **kwargs):
    return jsonify({
        'status': 'error',
        'message': message,
        'data': None
    })


def response_need_force(message, *args, **kwargs):
    return jsonify({
        'status': 'need-force',
        'message': message,
        'data': None
    })


def response_not_implemented(action, *args, **kwargs):
    return jsonify({
        'status': 'not-implemented',
        'message': 'Action {:s} not implemented!'.format(action),
        'data': None
    })


def response_not_supported(action=None, *args, **kwargs):
    msg = 'Action {:s} not supported!'.format(action) if action else 'Not supported!'
    return response_error(msg)


def response_not_found(action=None, *args, **kwargs):
    msg = 'Action {:s} not found!'.format(action) if action else 'Not found!'
    return response_error(msg)


def get_client():
    return docker.DockerClient(base_url='unix:///var/run/docker.sock')


def get_endpoint_architecture():
    client = get_client()
    epoint_arch = client.info()['Architecture']
    if epoint_arch not in CANONICAL_ARCH:
        print(f'FATAL: Architecture {epoint_arch} not supported!')
        return None
    return CANONICAL_ARCH[epoint_arch]


def get_duckietown_distro():
    return os.environ.get('DT_DISTRO', 'UNKNOWN').split('-')[0]


def dt_label(key, value=None):
    label = f"{DOCKER_LABEL_DOMAIN}.{key.lstrip('.')}"
    if value is not None:
        label = f"{label}={value}"
    return label


def inspect_remote_image(image, tag):
    res = requests.get(DOCKER_HUB_API_URL['token'].format(image=image), timeout=10).json()
    token = res['token']
    # ---
    res = requests.get(
        DOCKER_HUB_API_URL['digest'].format(image=image, tag=tag),
        headers={
            "Accept": "application/vnd.docker.distribution.manifest.v2+json",
            "Authorization": "Bearer {0}".format(token)
        },
        timeout=10
    ).text
    digest = json.loads(res)['config']['digest']
    # ---
    res = requests.get(
        DOCKER_HUB_API_URL['inspect'].format(image=image, tag=tag, digest=digest),
        headers={
            "Authorization": "Bearer {0}".format(token)
        },
        timeout=10
    ).json()
    return res


def parse_time(time_iso):
    time = None
    try:
        time = datetime.strptime(time_iso, "%Y-%m-%dT%H:%M:%S.%f")
    except ValueError:
        pass
    return time


def get_container_config(container: DockerContainer, new_image: DockerImage):
    # update container's data
    container.reload()
    # get container's image
    image = container.image
    # get image default ENV
    old_default_env = set(image.attrs['Config']['Env'])
    # get current container's ENV
    old_env = set(container.attrs['Config']['Env'])
    # get new image ENV
    new_default_env = set(new_image.attrs['Config']['Env'])
    # compute new container ENV
    new_env = list(old_env.difference(old_default_env).difference(new_default_env))
    # compile new configuration
    cfg = container.attrs
    return {
        'command': cfg['Config']['Cmd'],
        'devices': [
            '{}:{}:{}'.format(dev['PathOnHost'], dev['PathInContainer'], dev['CgroupPermissions'])
            for dev in _navigate_dict(cfg, ['HostConfig', 'Devices'], [])
        ],
        'environment': new_env,
        'labels': _navigate_dict(cfg, ['Config', 'Labels'], {}),
        'network_mode': cfg['HostConfig']['NetworkMode'],
        'ports': {
            port: int(binding_info['HostPort'])
            for port, binding_info
            in _navigate_dict(cfg, ['HostConfig', 'PortBindings'], {}).items()
        },
        'privileged': cfg['HostConfig']['Privileged'],
        'restart_policy': cfg['HostConfig']['RestartPolicy'],
        'runtime': cfg['HostConfig']['Runtime'],
        'volumes': {
            (volume['Name'] if volume['Type'] == 'volume' else volume['Source']):
                {
                    'bind': volume['Destination'],
                    'mode': 'rw' if volume['RW'] else volume['Mode']
                }
            for volume in _navigate_dict(cfg, ['HostConfig', 'Mounts'], [])
        }
    }


def _navigate_dict(struct, path, default):
    cur = struct
    for step in path:
        if step not in cur:
            return default
        cur = cur[step]
    return cur if isinstance(cur, type(default)) else default


def indent_str(strobj):
    return '\n\t'.join([''] + strobj.split('\n'))
