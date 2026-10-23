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
    monkeypatch.setattr(config_utils, "CONFIG_PATH", str(path))
    return path


def test_a_missing_key_reads_the_default_given_in_code(config):
    assert config_fields.current("vertex.location_llm", "global") == "global"
    assert config_fields.current("vertex_tts.max_workers", 4) == 4
    assert config_fields.current("vertex.unknown") is None


def test_saving_creates_the_missing_sections_and_keeps_the_rest(config):
    config_fields.save("vertex_tts.max_workers", 2)
    config_fields.save("vertex.project", "my-project")
    assert load_key("vertex_tts.max_workers") == 2
    assert load_key("vertex.project") == "my-project"
    assert load_key("max_workers") == 4
    assert "# operator comment" in config.read_text(encoding="utf-8")


def test_saved_values_win_over_the_default(config):
    config_fields.save("vertex.location_llm", "us-central1")
    assert config_fields.current("vertex.location_llm", "global") == "us-central1"


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
        lambda: config_fields.current("vertex.location_llm", "global"),
        lambda: config_fields.current("vertex_tts.max_workers", 4),
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

