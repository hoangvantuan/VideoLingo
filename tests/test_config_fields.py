"""Shared read/write helpers of the sidebar settings added by the fork (custom, #11)."""

import textwrap

import pytest

from core.st_utils import config_fields
from core.utils import config_utils
from core.utils.config_utils import load_key


@pytest.fixture
def config(tmp_path, monkeypatch):
    path = tmp_path / "config.yaml"
    path.write_text(textwrap.dedent("""
        # operator comment
        max_workers: 4
        vertex:
    """), encoding="utf-8")
    (tmp_path / "config.example.yaml").write_text(textwrap.dedent("""
        vertex:
          project: ''
          location_llm: 'global'
        vertex_tts:
          max_workers: 4
    """), encoding="utf-8")
    monkeypatch.setattr(config_utils, "CONFIG_PATH", str(path))
    return path


def test_a_missing_key_reads_its_value_from_config_example(config):
    assert config_fields.current("vertex.location_llm") == "global"
    assert config_fields.current("vertex_tts.max_workers") == 4


def test_a_key_in_neither_file_reads_the_given_fallback(config):
    assert config_fields.current("vertex.unknown", "x") == "x"


def test_saving_creates_the_missing_sections_and_keeps_the_rest(config):
    config_fields.save("vertex_tts.max_workers", 2)
    config_fields.save("vertex.project", "my-project")
    assert load_key("vertex_tts.max_workers") == 2
    assert load_key("vertex.project") == "my-project"
    assert load_key("max_workers") == 4
    assert "# operator comment" in config.read_text(encoding="utf-8")


def test_saved_values_win_over_config_example(config):
    config_fields.save("vertex.location_llm", "us-central1")
    assert config_fields.current("vertex.location_llm") == "us-central1"
