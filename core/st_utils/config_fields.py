"""Custom (#11): read and write the settings the fork added, for the sidebar widgets of F7-F10 and later.

A config.yaml written before a key existed does not have it: `current` then shows the value of
config.example.yaml, and `save` adds the key together with any missing parent section.
"""

import copy
import os
import threading

from ruamel.yaml import YAML

from core.utils import config_utils, env_keys
from core.utils.config_utils import load_key_or, update_key

# A parser of our own: the shared config_utils.yaml is not thread-safe, and the sidebar reruns while the
# pipeline thread reads config.yaml with it (BUG-0). The example file is parsed once per change.
_parser = YAML()
_lock = threading.Lock()
_example_cache = {}


def _example_data(path):
    stamp = os.stat(path).st_mtime_ns
    with _lock:
        cached = _example_cache.get(path)
        if cached is None or cached[0] != stamp:
            with open(path, encoding="utf-8") as file:
                cached = (stamp, _parser.load(file))
            _example_cache[path] = cached
        return cached[1]


def _example(key):
    """Value of `key` in config.example.yaml beside config.yaml; KeyError when it is not there."""
    path = os.path.join(os.path.dirname(config_utils.CONFIG_PATH), "config.example.yaml")
    if not os.path.exists(path):
        raise KeyError(key)
    value = _example_data(path)
    for part in key.split("."):
        if not isinstance(value, dict) or part not in value:
            raise KeyError(key)
        value = value[part]
    return copy.deepcopy(value)


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
    if parent and not isinstance(env_keys.raw(parent), dict):  # raw: a section holding an unset ${VAR} is still a section
        save(parent, {})
    update_key(key, value, add_missing=True)
