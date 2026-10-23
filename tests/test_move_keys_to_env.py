"""scripts/move_keys_to_env.py moves the keys of config.yaml to .env (custom, #21). Only temporary files are used."""

import importlib.util
import os
import re
import stat
import textwrap
from pathlib import Path

import pytest
from dotenv import dotenv_values

from core.utils import config_utils

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "move_keys_to_env.py"
SECRETS = {"llm": "sk-llm-0123456789", "soniox": "sx-soniox-0123456789", "fish": "fa-fish-0123456789",
           "f5": "f5-302-0123456789", "profile": "or-profile-0123456789"}
VARS = ("LLM_API_KEY", "SONIOX_API_KEY", "FISH_AUDIO_API_KEY", "API_302_KEY", "OPENROUTER_API_KEY",
        "ELEVENLABS_API_KEY", "LOCAL_API_KEY")

CONFIG = f"""
    # operator comment
    api:
      key: '{SECRETS["llm"]}'  # the LLM key
      base_url: 'https://llm.example.com'
    llm_profiles:
      openrouter-free:
        provider: openrouter
        api_key_env: 'OPENROUTER_API_KEY'
        api_key: '{SECRETS["profile"]}'
      local:
        provider: openai
        api_key: '${{LOCAL_API_KEY}}'
    whisper:
      soniox_api_key: '{SECRETS["soniox"]}'
      elevenlabs_api_key: 'your_elevenlabs_api_key'
      mai_api_key: ''
    fish_audio:
      api_key: '{SECRETS["fish"]}'
    f5tts:
      302_api: '{SECRETS["f5"]}'
    max_tokens: 4096
"""


@pytest.fixture
def script():
    spec = importlib.util.spec_from_file_location("move_keys_to_env", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def config(tmp_path, monkeypatch):
    for var in VARS:  # set then delete: teardown also removes what the script put into os.environ
        monkeypatch.setenv(var, "")
        monkeypatch.delenv(var)
    monkeypatch.setattr(config_utils, "CONFIG_PATH", config_utils.CONFIG_PATH)
    path = tmp_path / "config.yaml"
    path.write_text(textwrap.dedent(CONFIG), encoding="utf-8")
    return path


def run(script, config, capsys, *args):
    assert script.main(["--config", str(config), *args]) == 0
    out = capsys.readouterr()
    for secret in SECRETS.values():
        assert secret not in out.out + out.err
    return out.out


def test_every_key_moves_to_dotenv_and_config_keeps_references(script, config, capsys):
    original = config.read_text(encoding="utf-8")
    run(script, config, capsys)
    text = config.read_text(encoding="utf-8")
    assert not any(secret in text for secret in SECRETS.values())
    assert re.search(r"key: '\$\{LLM_API_KEY\}' +# the LLM key", text) and "# operator comment" in text
    assert "${SONIOX_API_KEY}" in text and "${FISH_AUDIO_API_KEY}" in text and "${API_302_KEY}" in text
    assert "${OPENROUTER_API_KEY}" in text and "api_key_env: 'OPENROUTER_API_KEY'" in text
    assert "your_elevenlabs_api_key" in text and "mai_api_key: ''" in text and "max_tokens: 4096" in text
    env = config.parent / ".env"
    assert dotenv_values(env) == {"LLM_API_KEY": SECRETS["llm"], "OPENROUTER_API_KEY": SECRETS["profile"],
                                  "SONIOX_API_KEY": SECRETS["soniox"], "FISH_AUDIO_API_KEY": SECRETS["fish"],
                                  "API_302_KEY": SECRETS["f5"]}
    assert stat.S_IMODE(os.stat(env).st_mode) == 0o600
    backup = config.parent / "config.backup.yaml"
    assert backup.read_text(encoding="utf-8") == original
    assert stat.S_IMODE(os.stat(backup).st_mode) == 0o600
    config_utils.CONFIG_PATH = str(config)
    assert config_utils.load_key("whisper.soniox_api_key") == SECRETS["soniox"]


def test_dry_run_prints_key_and_variable_names_and_writes_nothing(script, config, capsys):
    original = config.read_text(encoding="utf-8")
    out = run(script, config, capsys, "--dry-run")
    assert "api.key" in out and "LLM_API_KEY" in out and "f5tts.302_api" in out
    assert config.read_text(encoding="utf-8") == original
    assert not (config.parent / ".env").exists() and not (config.parent / "config.backup.yaml").exists()


def test_a_variable_with_another_value_is_not_overwritten_and_reported(script, config, capsys):
    (config.parent / ".env").write_text("SONIOX_API_KEY='sx-other'\n", encoding="utf-8")
    out = run(script, config, capsys)
    assert dotenv_values(config.parent / ".env")["SONIOX_API_KEY"] == "sx-other"
    assert "whisper.soniox_api_key" in out and "SONIOX_API_KEY" in out
    assert SECRETS["soniox"] in config.read_text(encoding="utf-8")  # left in place for the operator to settle
    assert "${LLM_API_KEY}" in config.read_text(encoding="utf-8")


def test_a_variable_with_the_same_value_is_reused(script, config, capsys, monkeypatch):
    monkeypatch.setenv("FISH_AUDIO_API_KEY", SECRETS["fish"])
    run(script, config, capsys)
    assert "${FISH_AUDIO_API_KEY}" in config.read_text(encoding="utf-8")
    assert "FISH_AUDIO_API_KEY" not in dotenv_values(config.parent / ".env")


def test_nothing_to_move_leaves_the_files_alone(script, config, capsys):
    run(script, config, capsys)
    (config.parent / "config.backup.yaml").unlink()
    run(script, config, capsys)
    assert not (config.parent / "config.backup.yaml").exists()


def test_the_example_config_references_every_key_and_dotenv_example_lists_them(script):
    root = SCRIPT.parents[1]
    with open(root / "config.example.yaml", encoding="utf-8") as file:
        data = config_utils.yaml.load(file)
    references = []

    def walk(mapping, prefix=""):
        for name, value in mapping.items():
            path = f"{prefix}{name}"
            if isinstance(value, dict):
                walk(value, path + ".")
            elif path in script.STANDARD_VARS:
                references.append((path, value))

    walk(data)
    assert {path for path, _ in references} == set(script.STANDARD_VARS)
    for path, value in references:
        assert value == f"${{{script.STANDARD_VARS[path]}:-}}", path
    listed = dotenv_values(root / ".env.example")
    assert set(script.STANDARD_VARS.values()) | {"GOOGLE_APPLICATION_CREDENTIALS"} <= set(listed)
    assert not any(listed.values())
