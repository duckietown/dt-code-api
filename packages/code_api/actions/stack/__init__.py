import os

import yaml

from code_api.constants import STACKS_TMP_DIR


def stack_get_dir(name: str) -> str:
    return os.path.join(STACKS_TMP_DIR, name)


def stack_get_fpath(name: str) -> str:
    return os.path.join(stack_get_dir(name), "docker-compose.yaml")


def stack_exists(name: str) -> bool:
    stack_fpath = stack_get_fpath(name)
    return os.path.exists(stack_fpath) and os.path.isfile(stack_fpath)


def stack_create(name: str, content: dict):
    # create stack dir
    stack_dir = stack_get_dir(name)
    os.makedirs(stack_dir, exist_ok=True)
    # dump stack to docker-compose.yaml file
    stack_fpath = stack_get_fpath(name)
    with open(stack_fpath, "wt") as fout:
        yaml.dump(content, fout)


__all__ = [
    "stack_get_dir",
    "stack_get_fpath",
    "stack_exists",
    "stack_create"
]