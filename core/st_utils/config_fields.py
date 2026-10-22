"""Custom (#11): read and write the settings the fork added, for the sidebar widgets of F7-F10 and later.

A config.yaml written before a key existed does not have it: `current` then shows the value of
config.example.yaml, and `save` adds the key together with any missing parent section.
"""

import os

from core.utils import config_utils
from core.utils.config_utils import load_key_or, update_key


def _example(key):
    """Value of `key` in config.example.yaml beside config.yaml; KeyError when it is not there."""
    path = os.path.join(os.path.dirname(config_utils.CONFIG_PATH), "config.example.yaml")
    if not os.path.exists(path):
        raise KeyError(key)
    with open(path, encoding="utf-8") as file:
        value = config_utils.yaml.load(file)
    for part in key.split("."):
        if not isinstance(value, dict) or part not in value:
            raise KeyError(key)
        value = value[part]
    return value


def current(key, fallback=None):
    """config.yaml value, else the config.example.yaml default, else `fallback`."""
    try:
        default = _example(key)
    except KeyError:
        default = fallback
    return load_key_or(key, default)


def save(key, value):
    """Write `key`, adding it and any missing (or empty) parent section to an older config.yaml."""
    parent, _, _ = key.rpartition(".")
    if parent and not isinstance(load_key_or(parent, None), dict):
        save(parent, {})
    update_key(key, value, add_missing=True)
