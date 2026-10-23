"""scripts/upgrade_config.py lays the operator's config.yaml over the tracked template (custom, #22). Temporary files only."""

import importlib.util
import stat
import textwrap
from pathlib import Path

import pytest

from core.utils import config_utils

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "upgrade_config.py"
SECRET = "operator-value-0123456789"

TEMPLATE = """
    # template header
    target_language: 'English'  # the language of the subtitles
    api:
      key: '${LLM_API_KEY:-}'
      model: 'gpt-4o'
      # the timeout in seconds
      timeout: 60
    original_volume: 0  # new in the template
    vertex_tts:
      speed: 1.0
"""

OPERATOR = f"""
    target_language: '{SECRET}'
    api:
      key: '${{LLM_API_KEY}}'
      model: 'gpt-4o'
      timeout: 120
      my_extra: 'mine'
    my_section:
      flag: true
"""


@pytest.fixture
def script():
    spec = importlib.util.spec_from_file_location("upgrade_config", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def files(tmp_path):
    template = tmp_path / "template.yaml"
    template.write_text(textwrap.dedent(TEMPLATE), encoding="utf-8")
    config = tmp_path / "config.yaml"
    config.write_text(textwrap.dedent(OPERATOR), encoding="utf-8")
    return template, config


def run(script, template, config, *extra):
    return script.main(["--template", str(template), "--config", str(config), *extra])


def load(path):
    with open(path, encoding="utf-8") as file:
        return config_utils.yaml.load(file)


def test_the_result_has_the_template_structure_and_comments_with_the_operator_values(script, files):
    template, config = files
    assert run(script, template, config) == 0
    text = config.read_text(encoding="utf-8")
    data = load(config)
    assert data["target_language"] == SECRET
    assert data["api"]["key"] == "${LLM_API_KEY}"  # the raw reference, never resolved
    assert data["api"]["timeout"] == 120
    assert data["original_volume"] == 0 and data["vertex_tts"]["speed"] == 1.0
    for comment in ("# template header", "# the language of the subtitles", "# the timeout in seconds",
                    "# new in the template"):
        assert comment in text
    assert f"target_language: '{SECRET}'" in text  # quotes kept
    assert list(data) == ["target_language", "api", "original_volume", "vertex_tts", "my_section"]


def test_key_paths_are_reported_and_no_value_is_printed(script, files, capsys):
    template, config = files
    run(script, template, config)
    out = capsys.readouterr().out
    assert "added from the template: original_volume" in out
    assert "added from the template: vertex_tts" in out
    assert "kept, not in the template: api.my_extra" in out
    assert "kept, not in the template: my_section" in out
    assert SECRET not in out and "mine" not in out and "LLM_API_KEY" not in out


def test_the_original_is_backed_up_first(script, files):
    template, config = files
    original = config.read_bytes()
    run(script, template, config)
    backup = config.parent / script.BACKUP
    assert backup.read_bytes() == original
    assert stat.S_IMODE(backup.stat().st_mode) == 0o600  # it may still hold a key not yet moved to .env


def test_an_earlier_backup_is_never_overwritten(script, files):
    template, config = files
    original = config.read_text(encoding="utf-8")
    (config.parent / script.BACKUP).write_text("earlier", encoding="utf-8")
    assert run(script, template, config) == 1
    assert config.read_text(encoding="utf-8") == original
    assert (config.parent / script.BACKUP).read_text(encoding="utf-8") == "earlier"


def test_dry_run_lists_the_paths_and_writes_nothing(script, files, capsys):
    template, config = files
    original = config.read_text(encoding="utf-8")
    assert run(script, template, config, "--dry-run") == 0
    assert "added from the template: original_volume" in capsys.readouterr().out
    assert config.read_text(encoding="utf-8") == original
    assert not (config.parent / script.BACKUP).exists()


def test_an_upgraded_config_is_left_alone(script, files, capsys):
    template, config = files
    run(script, template, config)
    (config.parent / script.BACKUP).unlink()
    upgraded = config.read_text(encoding="utf-8")
    capsys.readouterr()
    assert run(script, template, config) == 0
    out = capsys.readouterr().out
    assert "added from the template" not in out and "Nothing to upgrade." in out
    assert config.read_text(encoding="utf-8") == upgraded
    assert not (config.parent / script.BACKUP).exists()


def test_invalid_yaml_names_the_line_without_quoting_it(script, files, capsys):
    template, config = files
    config.write_text(f"api:\n  key: '{SECRET}'\n  model: [\n", encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        run(script, template, config)
    assert SECRET not in str(error.value) and "line" in str(error.value)
    assert SECRET not in capsys.readouterr().out


def test_a_rewrite_with_no_key_change_says_so(script, files, capsys):
    template, config = files
    config.write_text(textwrap.dedent(TEMPLATE).replace("timeout: 60", "timeout:   60"), encoding="utf-8")
    assert run(script, template, config, "--dry-run") == 0
    assert "No key path changes; only formatting or comments differ." in capsys.readouterr().out
