"""Custom (F7/F8): errors of the operator's configuration (see CUSTOM.md).

They are deterministic, so `except_handler` lets them through at once instead of retrying.
"""


class ConfigError(Exception):
    """Fixed only by changing config.yaml, the environment or the cloud setup; retrying cannot help."""
