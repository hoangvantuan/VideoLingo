"""Translate-stage thread count follows the active LLM profile (custom fork, F7)."""

import textwrap

import pytest

from core.utils import config_utils
from core.utils.llm_profile import llm_max_workers

CONFIG = """
    api:
      profile: '{profile}'
      key: 'custom-key'
      base_url: 'https://api.example.com'
      model: 'custom-model'
      llm_support_json: true
    max_workers: 4
    llm_profiles:
      openrouter-free:
        provider: openrouter
        model: 'vendor/free-model:free'
        api_key: 'config-key'
        max_workers: 1
      no-override:
        provider: openrouter
        model: 'vendor/other'
        api_key: 'config-key'
      gemini:
        provider: vertex
        model: 'google/gemini-3.5-flash-lite'
        max_workers: 2
"""


@pytest.fixture
def setup(tmp_path, monkeypatch):
    config = tmp_path / "config.yaml"
    monkeypatch.setattr(config_utils, "CONFIG_PATH", str(config))

    def write(profile):
        config.write_text(textwrap.dedent(CONFIG.format(profile=profile)), encoding="utf-8")

    return write


def test_profile_max_workers_overrides_the_general_value(setup):
    setup("openrouter-free")
    assert llm_max_workers() == 1


def test_profile_without_max_workers_uses_the_general_value(setup):
    setup("no-override")
    assert llm_max_workers() == 4


def test_custom_profile_uses_the_general_value(setup):
    setup("")
    assert llm_max_workers() == 4


def test_vertex_profile_thread_count_needs_no_google_credential(setup, monkeypatch):
    from core.utils import google_credentials

    def no_credential():
        raise AssertionError("the Google credential must not be loaded for a thread count")

    google_credentials.reset()
    monkeypatch.setattr(google_credentials, "_load_default", no_credential)
    setup("gemini")
    assert llm_max_workers() == 2
