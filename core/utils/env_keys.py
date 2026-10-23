"""Custom (#21): keys in .env. See "Key trong .env" in CUSTOM.md.

config.yaml holds a reference `${VAR}` (or `${VAR:-default}`) in place of a key; the value lives in the .env
beside config.yaml or in the process environment, which wins (.env is loaded with override=False).
Reading replaces each reference; writing keeps the reference and sends a changed value to .env.
"""

import copy
import os
import re
import threading

from core.utils.config_errors import ConfigError

REFERENCE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-(.*))?\}", re.DOTALL)

_lock = threading.Lock()
_loaded = set()


class MissingEnvVarError(ConfigError, RuntimeError):
    """config.yaml references a variable that neither .env nor the environment sets."""


def env_path():
    """The .env beside config.yaml (the repo root when config.yaml is the default relative path)."""
    from core.utils import config_utils
    return os.path.join(os.path.dirname(os.path.abspath(config_utils.CONFIG_PATH)), ".env")


def load_env():
    """Load .env once per path; a variable already in the environment is kept."""
    path = env_path()
    with _lock:
        if path in _loaded:
            return
        _loaded.add(path)
    from dotenv import load_dotenv
    load_dotenv(path, override=False)


def reference(value):
    """(VAR, default or None) when the whole value is a reference, else None."""
    if not isinstance(value, str):
        return None
    match = REFERENCE.fullmatch(value.strip())
    return (match.group(1), match.group(2)) if match else None


def variable(value):
    """Name of the variable that `value` references, else None."""
    ref = reference(value)
    return ref[0] if ref else None


def raw(key, default=None):
    """config.yaml value of `key` as written, references unreplaced; `default` when the key is missing."""
    from core.utils import config_utils
    try:
        return config_utils.load_key(key, resolve=False)
    except KeyError:
        return default


def _value_of(var, default):
    if var in os.environ:
        return os.environ[var]
    if default is not None:
        return default
    raise MissingEnvVarError(
        f"Environment variable {var} is not set: add {var}=... to .env ({env_path()}) or to the environment")


def resolve(value):
    """`value` with every reference replaced, also inside sections and lists."""
    if isinstance(value, dict):
        for key in value:
            value[key] = resolve(value[key])
        return value
    if isinstance(value, list):
        for index, item in enumerate(value):
            value[index] = resolve(item)
        return value
    ref = reference(value)
    return _value_of(*ref) if ref else value


def unset_as_empty(load):
    """`load` that reads "" where a referenced variable is unset (to show settings, never to run a step)."""
    def wrapped(*args, **kwargs):
        try:
            return load(*args, **kwargs)
        except MissingEnvVarError:
            return ""
    return wrapped


def set_env(var, value):
    """Write VAR to .env (created with mode 600) and to this process's environment."""
    from dotenv import set_key
    path = env_path()
    with _lock:
        if not os.path.exists(path):
            os.close(os.open(path, os.O_CREAT | os.O_WRONLY, 0o600))
        set_key(path, var, value, quote_mode="always")
        os.chmod(path, 0o600)
        os.environ[var] = value


def _keep(old, new):
    ref = reference(old)
    if ref:
        if reference(new):  # the reference itself is being changed
            return new
        var, default = ref
        value = "" if new is None else str(new)
        if value != os.environ.get(var, default):
            set_env(var, value)
        return old
    if isinstance(old, dict) and isinstance(new, dict):
        for key in new:
            if key in old:
                new[key] = _keep(old[key], new[key])
    elif isinstance(old, list) and isinstance(new, list):
        for index in range(min(len(old), len(new))):
            new[index] = _keep(old[index], new[index])
    return new


def keep_references(old, new):
    """The value to write over the raw config value `old`: every reference of `old` stays in config.yaml,
    and a value that differs from what the reference reads is written to .env under its variable."""
    load_env()
    return _keep(old, copy.deepcopy(new))
