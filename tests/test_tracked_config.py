"""#22 (custom): config.yaml is tracked by git, so it holds no real key; keys live in .env."""

import re
from pathlib import Path

from core.utils import config_utils

ROOT = Path(__file__).resolve().parents[1]
SECRET_NAME = re.compile(r"key|token|secret", re.IGNORECASE)
REFERENCE = re.compile(r"\$\{[^}]+\}")


def _secret_paths(mapping, prefix=""):
    """Dotted paths of the leaves whose name looks like a secret; api_key_env only names a variable."""
    for name, value in mapping.items():
        path = f"{prefix}{name}"
        if isinstance(value, dict):
            yield from _secret_paths(value, path + ".")
        elif SECRET_NAME.search(str(name)) and name != "api_key_env":
            yield path, value


def _is_placeholder(value):
    if value is None or value == "":
        return True
    return isinstance(value, str) and (value.startswith("YOUR_") or REFERENCE.fullmatch(value) is not None)


def test_the_tracked_config_holds_no_real_key():
    with open(ROOT / "config.yaml", encoding="utf-8") as file:
        data = config_utils.yaml.load(file)
    paths = list(_secret_paths(data))
    assert paths, "no key field found; the walk is broken"
    # only the names are printed, never a value
    assert [path for path, value in paths if not _is_placeholder(value)] == []


def test_git_tracks_config_yaml_and_ignores_the_files_holding_keys():
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "config.yaml" not in ignored
    assert {".env", "config.backup.yaml"} <= set(ignored)
