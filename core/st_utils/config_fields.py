"""Custom (#11): read and write the settings the fork added, for the sidebar widgets of F7-F10 and later.

A config.yaml written before a key existed does not have it: `current` then shows the default that the
widget gives in code (the value of the tracked config.yaml, #22), and `save` adds the key together with any
missing parent section.
"""

from core.utils import env_keys
from core.utils.config_utils import load_key_or, update_key


def current(key, fallback=None):
    """config.yaml value, else `fallback`, the default of the widget."""
    return load_key_or(key, fallback)


def save(key, value):
    """Write `key`, adding it and any missing (or empty) parent section to an older config.yaml."""
    parent, _, _ = key.rpartition(".")
    if parent and not isinstance(env_keys.raw(parent), dict):  # raw: a section holding an unset ${VAR} is still a section
        save(parent, {})
    update_key(key, value, add_missing=True)
