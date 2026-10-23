"""Custom (#21): move the keys of config.yaml to .env, leaving ${VAR} references in config.yaml.

Run it yourself from the repo root:

    python scripts/move_keys_to_env.py --dry-run   # only prints key -> variable
    python scripts/move_keys_to_env.py

A key is a non-empty value whose name has key/token/secret as a word (api_key, key, access_token), or a known
key without such a name (f5tts.302_api). Names that hold a variable name (api_key_env), references and
YOUR_... placeholders are left alone. config.yaml is copied to config.backup.yaml first; .env gets mode 600.
A variable that .env or the environment already sets is never overwritten: with the same value it is
reused, with another value the key stays in config.yaml and is reported. No value is ever printed.
"""

import argparse
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import dotenv_values  # noqa: E402
from ruamel.yaml import YAML  # noqa: E402
from ruamel.yaml.scalarstring import SingleQuotedScalarString  # noqa: E402

from core.utils import config_utils, env_keys  # noqa: E402

# Variable names of the known keys; the same names as .env.example and the tracked config.yaml.
STANDARD_VARS = {
    "api.key": "LLM_API_KEY",
    "whisper.elevenlabs_api_key": "ELEVENLABS_API_KEY",
    "whisper.soniox_api_key": "SONIOX_API_KEY",
    "whisper.mai_api_key": "AZURE_SPEECH_KEY",
    "whisper.mai_openrouter_api_key": "OPENROUTER_API_KEY",
    "openai_tts.api_key": "OPENAI_TTS_API_KEY",
    "f5tts.302_api": "API_302_KEY",
    "sf_fish_tts.api_key": "SILICONFLOW_API_KEY",
    "sf_cosyvoice2.api_key": "SILICONFLOW_API_KEY",
    "fish_audio.api_key": "FISH_AUDIO_API_KEY",
    "soniox_tts.api_key": "SONIOX_API_KEY",
}
SECRET_NAME = re.compile(r"(^|_)(key|token|secret)(_|$)", re.IGNORECASE)


def _var_name(text):
    return re.sub(r"[^A-Z0-9]+", "_", str(text).upper()).strip("_")


def variable_for(path, mapping):
    """Variable name for the key at dotted `path`, held by `mapping`."""
    if path in STANDARD_VARS:
        return STANDARD_VARS[path]
    parts = path.split(".")
    if len(parts) == 3 and parts[0] == "llm_profiles" and parts[2] == "api_key":
        return str(mapping.get("api_key_env") or "") or f"{_var_name(parts[1])}_API_KEY"
    return _var_name("_".join(parts))


def _is_key(path, name, value):
    if path not in STANDARD_VARS and (not SECRET_NAME.search(str(name)) or str(name).lower().endswith("_env")):
        return False
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return False
    text = str(value).strip()
    return bool(text) and env_keys.reference(text) is None and not text.upper().startswith("YOUR_")


def find_keys(data, prefix=""):
    """(mapping, name, dotted path, value) of every key to move."""
    for name, value in data.items():
        path = f"{prefix}{name}"
        if isinstance(value, dict):
            yield from find_keys(value, path + ".")
        elif _is_key(path, name, value):
            yield data, name, path, str(value).strip()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Move the keys of config.yaml to .env (see CUSTOM.md, Key trong .env).")
    parser.add_argument("--config", default="config.yaml", help="config.yaml to migrate (default: ./config.yaml)")
    parser.add_argument("--dry-run", action="store_true", help="only print key -> variable, write nothing")
    args = parser.parse_args(argv)

    config_utils.CONFIG_PATH = args.config
    env = env_keys.env_path()
    yaml = YAML()
    yaml.preserve_quotes = True
    with open(args.config, encoding="utf-8") as file:
        data = yaml.load(file)

    existing = {**(dotenv_values(env) if os.path.exists(env) else {}), **os.environ}
    planned, moves, conflicts = {}, [], []
    for mapping, name, path, value in find_keys(data):
        var = variable_for(path, mapping)
        known = planned.get(var, existing.get(var))
        if known is not None and known != value:
            conflicts.append((path, var))
            continue
        moves.append((mapping, name, path, var, value, known is None))
        planned[var] = value

    for _, _, path, var, _, new in moves:
        print(f"{path} -> {var}" + ("" if new else " (already set with the same value)"))
    for path, var in conflicts:
        print(f"SKIPPED {path}: {var} is already set with another value; settle it by hand")
    if not moves:
        print("Nothing to move.")
        return 0
    if args.dry_run:
        print("Dry run: nothing written.")
        return 0

    backup = os.path.join(os.path.dirname(os.path.abspath(args.config)), "config.backup.yaml")
    shutil.copyfile(args.config, backup)
    os.chmod(backup, 0o600)
    written = set()
    for mapping, name, _, var, value, new in moves:
        if new and var not in written:
            env_keys.set_env(var, value)
            written.add(var)
        mapping[name] = SingleQuotedScalarString(f"${{{var}}}")
    with open(args.config, "w", encoding="utf-8") as file:
        yaml.dump(data, file)
    print(f"Moved {len(moves)} key(s) to {env}; backup in {backup}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
