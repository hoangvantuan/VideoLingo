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


def test_sidebar_reads_and_writes_race_the_pipeline_without_errors(config):
    """BUG-0: sidebar reruns call current()/save() while the pipeline thread uses load_key/update_key."""
    import threading

    errors = []

    def hammer(action):
        try:
            for _ in range(150):
                action()
        except Exception as error:  # noqa: BLE001 - any parser error is the bug
            errors.append(error)

    actions = [
        lambda: config_fields.current("vertex.location_llm"),
        lambda: config_fields.current("vertex_tts.max_workers"),
        lambda: config_fields.save("vertex_tts.max_workers", 3),
        lambda: load_key("max_workers"),
        lambda: config_utils.update_key("max_workers", 4),
    ]
    threads = [threading.Thread(target=hammer, args=(action,)) for action in actions * 2]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert load_key("max_workers") == 4


def test_config_example_is_parsed_once_until_it_changes(config, monkeypatch):
    calls = []
    real_load = config_fields._parser.load
    monkeypatch.setattr(config_fields._parser, "load", lambda stream: calls.append(1) or real_load(stream))
    config_fields._example_cache.clear()
    for _ in range(5):
        assert config_fields.current("vertex.location_llm") == "global"
    assert len(calls) == 1
    example = config.parent / "config.example.yaml"
    example.write_text("vertex:\n  location_llm: 'europe-west4'\n", encoding="utf-8")
    import os
    stat = example.stat()
    os.utime(example, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
    assert config_fields.current("vertex.location_llm") == "europe-west4"
