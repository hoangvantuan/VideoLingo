"""Sidebar editor of llm_profiles and the shared vertex: section, driven through Streamlit's AppTest (custom fork, #11)."""

import textwrap

import pytest
from streamlit.testing.v1 import AppTest

from core.utils import config_utils
from core.utils.config_utils import load_key, load_key_or


def _app():
    from core.st_utils import llm_profile_editor

    llm_profile_editor.render()


@pytest.fixture
def config(tmp_path, monkeypatch):
    path = tmp_path / "config.yaml"
    monkeypatch.setattr(config_utils, "CONFIG_PATH", str(path))

    def write(text):
        path.write_text(textwrap.dedent(text), encoding="utf-8")

    write(OLD_CONFIG)
    return write


# a config.yaml written before F7-F10: no api.profile, llm_profiles, vertex:
OLD_CONFIG = """
    api:
      key: 'custom-key'
      base_url: 'https://api.example.com'
      model: 'custom-model'
      llm_support_json: false
    max_workers: 4
"""

WITH_PROFILES = """
    api:
      profile: 'local'
      key: 'custom-key'
      base_url: 'https://api.example.com'
      model: 'custom-model'
      llm_support_json: false
    max_workers: 4
    llm_profiles:
      # the operator's own comment
      openrouter-free:
        provider: openrouter
        model: 'deepseek/deepseek-chat-v3.1:free'
        api_key_env: 'OPENROUTER_API_KEY'
      local:
        provider: openai
        model: 'qwen3'
        base_url: 'http://localhost:8000/v1'
"""


def opened():
    at = AppTest.from_function(_app).run()
    assert not at.exception
    return at.toggle[0].set_value(True).run()


def field(at, label):
    return next(widget for widget in [*at.text_input, *at.selectbox] if widget.label == label)


def button(at, label):
    return next(widget for widget in at.button if widget.label == label)


def fill(at, **values):
    for label, value in values.items():
        widget = field(at, label)
        (widget.select if hasattr(widget, "select") else widget.input)(value)
    return at


def test_editor_is_hidden_until_opened(config):
    at = AppTest.from_function(_app).run()
    assert not at.exception
    assert len(at.text_input) == 0


def test_a_vertex_profile_is_added_to_a_config_without_llm_profiles(config):
    at = opened()
    fill(at, **{"Tên profile": "gemini-lite", "Provider": "vertex", "Model": "google/gemini-3.5-flash-lite"})
    at = button(at, "💾 Lưu profile").click().run()
    assert not at.exception
    assert load_key("llm_profiles") == {"gemini-lite": {"provider": "vertex", "model": "google/gemini-3.5-flash-lite"}}


def test_json_mode_left_on_default_is_not_written_so_the_provider_default_applies(config):
    at = opened()
    fill(at, **{"Tên profile": "gemini-lite", "Provider": "vertex", "Model": "google/gemini-3.5-flash-lite"})
    at = button(at, "💾 Lưu profile").click().run()
    assert "llm_support_json" not in load_key("llm_profiles.gemini-lite")
    at = field(at, "Sửa profile").select("gemini-lite").run()
    at = field(at, "JSON mode").select(False).run()
    at = button(at, "💾 Lưu profile").click().run()
    assert load_key("llm_profiles.gemini-lite.llm_support_json") is False


def test_editing_a_profile_keeps_the_others_and_the_comments(config):
    config(WITH_PROFILES)
    at = opened()
    at = field(at, "Sửa profile").select("openrouter-free").run()
    assert field(at, "Model").value == "deepseek/deepseek-chat-v3.1:free"
    fill(at, **{"Model": "other/model:free", "Số luồng (max_workers)": "2", "Biến môi trường chứa key": ""})
    at = button(at, "💾 Lưu profile").click().run()
    assert not at.exception
    assert dict(load_key("llm_profiles.openrouter-free")) == {
        "provider": "openrouter", "model": "other/model:free", "max_workers": 2}
    assert load_key("llm_profiles.local.model") == "qwen3"
    assert "# the operator's own comment" in open(config_utils.CONFIG_PATH, encoding="utf-8").read()


def test_renaming_the_active_profile_follows_it_in_api_profile(config):
    config(WITH_PROFILES)
    at = opened()
    at = field(at, "Sửa profile").select("local").run()
    fill(at, **{"Tên profile": "ollama"})
    at = button(at, "💾 Lưu profile").click().run()
    assert list(load_key("llm_profiles")) == ["openrouter-free", "ollama"]
    assert load_key("api.profile") == "ollama"
    assert field(at, "Sửa profile").value == "ollama"


def test_deleting_the_active_profile_goes_back_to_the_custom_profile(config):
    config(WITH_PROFILES)
    at = opened()
    at = field(at, "Sửa profile").select("local").run()
    at = button(at, "🗑 Xóa profile").click().run()
    assert not at.exception
    assert list(load_key("llm_profiles")) == ["openrouter-free"]
    assert load_key("api.profile") == ""


def test_deleting_another_profile_keeps_the_active_one(config):
    config(WITH_PROFILES)
    at = opened()
    at = field(at, "Sửa profile").select("openrouter-free").run()
    at = button(at, "🗑 Xóa profile").click().run()
    assert list(load_key("llm_profiles")) == ["local"]
    assert load_key("api.profile") == "local"


@pytest.mark.parametrize("values, message", [
    ({"Tên profile": "", "Model": "m"}, "Tên profile"),
    ({"Tên profile": "local", "Model": "m"}, "đã có"),
    ({"Tên profile": "x", "Model": ""}, "Model"),
    ({"Tên profile": "x", "Model": "m", "Provider": "openai"}, "Base URL"),
    ({"Tên profile": "x", "Model": "m", "Số luồng (max_workers)": "0"}, "max_workers"),
    ({"Tên profile": "x", "Model": "m", "Số luồng (max_workers)": "two"}, "max_workers"),
])
def test_invalid_profiles_are_reported_and_not_written(config, values, message):
    config(WITH_PROFILES)
    before = open(config_utils.CONFIG_PATH, encoding="utf-8").read()
    at = fill(opened(), **values)
    at = button(at, "💾 Lưu profile").click().run()
    assert not at.exception
    assert any(message in error.value for error in at.error)
    assert open(config_utils.CONFIG_PATH, encoding="utf-8").read() == before


def test_an_unsupported_provider_is_reported(config):
    config(WITH_PROFILES.replace("provider: openai", "provider: foo"))
    at = opened()
    at = field(at, "Sửa profile").select("local").run()
    at = button(at, "💾 Lưu profile").click().run()
    assert any("foo" in error.value and "không hỗ trợ" in error.value for error in at.error)
    assert load_key("llm_profiles.local.provider") == "foo"


def test_the_fallback_key_is_a_password_field_and_never_shown_as_text(config):
    config(WITH_PROFILES.replace("api_key_env: 'OPENROUTER_API_KEY'", "api_key: 'sk-secret-123'"))
    at = opened()
    at = field(at, "Sửa profile").select("openrouter-free").run()
    key = field(at, "API key (dự phòng)")
    assert key.value == "sk-secret-123"
    assert key.proto.type == key.proto.PASSWORD
    shown = [element.value for element in [*at.caption, *at.error, *at.markdown, *at.info, *at.success]]
    assert not any("sk-secret-123" in str(text) for text in shown)


def test_vertex_project_and_location_are_written_to_a_config_without_a_vertex_section(config):
    at = opened()
    assert field(at, "Vertex location (Khâu Dịch)").value == "global"  # default of config.example.yaml
    fill(at, **{"Vertex project": "my-project"}).run()
    at = fill(at, **{"Vertex location (Khâu Dịch)": "us-central1"}).run()
    assert not at.exception
    assert load_key("vertex.project") == "my-project"
    assert load_key("vertex.location_llm") == "us-central1"
    assert load_key_or("api.model", None) == "custom-model"


def test_a_profile_declared_without_fields_can_be_completed(config):
    config(WITH_PROFILES.replace("""      local:
        provider: openai
        model: 'qwen3'
        base_url: 'http://localhost:8000/v1'
""", "      local:\n"))
    at = opened()
    at = field(at, "Sửa profile").select("local").run()
    fill(at, **{"Model": "qwen3", "Base URL": "http://localhost:8000/v1"})
    at = button(at, "💾 Lưu profile").click().run()
    assert not at.exception
    assert dict(load_key("llm_profiles.local")) == {
        "provider": "openrouter", "model": "qwen3", "base_url": "http://localhost:8000/v1"}
