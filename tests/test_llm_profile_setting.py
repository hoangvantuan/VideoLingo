"""Sidebar picker for the Profile đang dùng, driven through Streamlit's AppTest (custom fork, F7)."""

import textwrap

import pytest
from streamlit.testing.v1 import AppTest

from core.utils import config_utils
from core.utils.config_utils import load_key


def _app():
    import streamlit as st
    from core.st_utils import llm_profile_setting

    st.session_state["show_custom_inputs"] = llm_profile_setting.render()


@pytest.fixture
def config(tmp_path, monkeypatch):
    path = tmp_path / "config.yaml"
    monkeypatch.setattr(config_utils, "CONFIG_PATH", str(path))

    def write(text):
        path.write_text(textwrap.dedent(text), encoding="utf-8")

    return write


def run():
    return AppTest.from_function(_app).run()


WITH_PROFILES = """
    api:
      profile: ''
      key: 'custom-key'
      base_url: 'https://api.example.com'
      model: 'custom-model'
      llm_support_json: true
    llm_profiles:
      openrouter-free:
        provider: openrouter
        model: 'deepseek/deepseek-chat-v3.1:free'
      local:
        provider: openai
        model: 'qwen3'
        base_url: 'http://localhost:8000/v1'
"""


def test_without_llm_profiles_the_sidebar_is_unchanged(config):
    config("""
        api:
          key: 'custom-key'
          base_url: 'https://api.example.com'
          model: 'custom-model'
          llm_support_json: true
    """)
    at = run()
    assert not at.exception
    assert len(at.selectbox) == 0
    assert len(at.caption) == 0
    assert at.session_state["show_custom_inputs"] is True


def test_lists_the_custom_profile_first_then_the_named_profiles(config):
    config(WITH_PROFILES)
    at = run()
    box = at.selectbox[0]
    assert box.options[0].startswith("Profile custom")
    assert box.options[1:] == ["openrouter-free", "local"]
    assert box.value == ""


def test_custom_profile_shows_its_provider_and_model_and_keeps_the_upstream_inputs(config):
    config(WITH_PROFILES)
    at = run()
    assert "custom" in at.caption[0].value and "custom-model" in at.caption[0].value
    assert at.session_state["show_custom_inputs"] is True


def test_choosing_a_profile_writes_api_profile_and_hides_the_upstream_inputs(config):
    config(WITH_PROFILES)
    at = run()
    at = at.selectbox[0].select("openrouter-free").run()
    assert not at.exception
    assert load_key("api.profile") == "openrouter-free"
    assert at.session_state["show_custom_inputs"] is False
    caption = at.caption[0].value
    assert "openrouter" in caption and "deepseek/deepseek-chat-v3.1:free" in caption


def test_choosing_the_custom_profile_writes_an_empty_api_profile(config):
    config(WITH_PROFILES.replace("profile: ''", "profile: 'local'"))
    at = run()
    assert at.selectbox[0].value == "local"
    at = at.selectbox[0].select("").run()
    assert load_key("api.profile") == ""
    assert at.session_state["show_custom_inputs"] is True


def test_api_profile_missing_from_an_old_config_is_added_on_change(config):
    config(WITH_PROFILES.replace("      profile: ''\n", ""))
    at = run()
    assert at.selectbox[0].value == ""
    at.selectbox[0].select("local").run()
    assert load_key("api.profile") == "local"


def test_unknown_api_profile_is_shown_with_an_error_so_it_can_be_changed(config):
    config(WITH_PROFILES.replace("profile: ''", "profile: 'gone'"))
    at = run()
    assert not at.exception
    assert at.selectbox[0].value == "gone"
    assert "gone" in at.error[0].value
    assert at.session_state["show_custom_inputs"] is False
    at = at.selectbox[0].select("local").run()
    assert load_key("api.profile") == "local"
    assert "gone" not in at.selectbox[0].options


def test_stale_api_profile_without_llm_profiles_can_still_go_back_to_custom(config):
    config("""
        api:
          profile: 'gone'
          key: 'custom-key'
          base_url: 'https://api.example.com'
          model: 'custom-model'
          llm_support_json: true
    """)
    at = run()
    assert at.selectbox[0].value == "gone"
    at = at.selectbox[0].select("").run()
    assert load_key("api.profile") == ""
    assert len(at.selectbox) == 0


def _sidebar():
    from core.st_utils.sidebar_setting import page_setting

    page_setting()


@pytest.fixture
def example_config(tmp_path, monkeypatch):
    """config.example.yaml (placeholders only) as the config the whole sidebar reads."""
    import shutil
    from pathlib import Path

    path = tmp_path / "config.yaml"
    shutil.copy(Path(__file__).resolve().parents[1] / "config.example.yaml", path)
    monkeypatch.setattr(config_utils, "CONFIG_PATH", str(path))


def _api_inputs_shown(at):
    return any(box.value == load_key("api.base_url") for box in at.text_input)


def test_sidebar_shows_the_upstream_api_inputs_only_for_the_custom_profile(example_config):
    at = AppTest.from_function(_sidebar).run(timeout=30)
    assert not at.exception
    picker = next(box for box in at.selectbox if box.label == "LLM profile")
    assert picker.value == ""
    assert _api_inputs_shown(at)

    at = picker.select("openrouter-free").run(timeout=30)
    assert not at.exception
    assert load_key("api.profile") == "openrouter-free"
    assert not _api_inputs_shown(at)
