"""Every F7-F10 key set from the whole sidebar on a config.yaml older than those keys (custom fork, #11)."""

import shutil
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from core.tts_backend import vertex_tts
from core.utils import config_utils
from core.utils.config_utils import load_key, load_key_or
from core.utils.original_audio import original_volume

EXAMPLE = Path(__file__).resolve().parents[1] / "config.example.yaml"
NEW_KEYS = ["llm_profiles", "vertex", "vertex_tts", "original_volume"]


def _sidebar():
    from core.st_utils.sidebar_setting import page_setting

    page_setting()


@pytest.fixture
def old_config(tmp_path, monkeypatch):
    """config.example.yaml (placeholders only) without the F7-F10 keys, with the example beside it as in the repo."""
    shutil.copy(EXAMPLE, tmp_path / "config.example.yaml")
    with open(EXAMPLE, encoding="utf-8") as file:
        data = config_utils.yaml.load(file)
    for key in NEW_KEYS:
        del data[key]
    del data["api"]["profile"]
    data["tts_method"] = "vertex_tts"
    with open(tmp_path / "config.yaml", "w", encoding="utf-8") as file:
        config_utils.yaml.dump(data, file)
    monkeypatch.setattr(config_utils, "CONFIG_PATH", str(tmp_path / "config.yaml"))
    monkeypatch.setattr(vertex_tts, "list_voices", lambda language: [
        {"name": "vi-VN-Chirp3-HD-Aoede", "ssmlGender": "FEMALE"},
        {"name": "vi-VN-Chirp3-HD-Charon", "ssmlGender": "MALE"}])
    st.cache_data.clear()
    yield
    st.cache_data.clear()


def widget(at, kind, label):
    return next(item for item in getattr(at, kind) if item.label == label)


def test_the_new_keys_are_set_from_the_sidebar_and_used_by_the_next_run(old_config):
    at = AppTest.from_function(_sidebar).run(timeout=30)
    assert not at.exception

    at = widget(at, "toggle", "Quản lý LLM profile & Vertex AI").set_value(True).run(timeout=30)
    widget(at, "text_input", "Tên profile").input("gemini-lite")
    widget(at, "selectbox", "Provider").select("vertex")
    widget(at, "text_input", "Model").input("google/gemini-3.5-flash-lite")
    at = widget(at, "button", "💾 Lưu profile").click().run(timeout=30)
    at = widget(at, "text_input", "Vertex project").input("my-project").run(timeout=30)
    at = widget(at, "selectbox", "Profile đang dùng").select("gemini-lite").run(timeout=30)
    at = widget(at, "selectbox", "Vertex voice").select("vi-VN-Chirp3-HD-Charon").run(timeout=30)
    at = widget(at, "number_input", "Vertex parallel requests (max_workers)").set_value(2).run(timeout=30)
    at = widget(at, "slider", "Âm lượng gốc (Thuyết minh)").set_value(0.4).run(timeout=30)
    assert not at.exception

    assert load_key("api.profile") == "gemini-lite"
    assert dict(load_key("llm_profiles.gemini-lite")) == {"provider": "vertex", "model": "google/gemini-3.5-flash-lite"}
    assert load_key("vertex.project") == "my-project"
    assert load_key("vertex_tts.voice") == "vi-VN-Chirp3-HD-Charon"
    assert load_key("vertex_tts.max_workers") == 2
    assert original_volume(load_key) == 0.4

    # the next run reads them through the unchanged resolvers
    from core.utils import google_credentials
    from core.utils.llm_profile import active_profile, llm_max_workers

    profile = active_profile()
    assert (profile.provider, profile.model) == ("vertex", "google/gemini-3.5-flash-lite")
    assert "/projects/my-project/" in profile.base_url
    assert google_credentials.project() == "my-project"
    assert vertex_tts.request_payload("x")["voice"]["name"] == "vi-VN-Chirp3-HD-Charon"
    assert llm_max_workers() == load_key("max_workers")
    assert load_key_or("whisper.runtime", None) == "local"


def test_the_soniox_asr_key_is_masked_and_saved(old_config):
    from streamlit.proto.TextInput_pb2 import TextInput

    config_utils.update_key("whisper.runtime", "soniox")
    at = AppTest.from_function(_sidebar).run(timeout=30)
    key = widget(at, "text_input", "Soniox API")
    assert key.proto.type == TextInput.PASSWORD
    at = key.input("placeholder-key").run(timeout=30)
    assert not at.exception
    assert load_key("whisper.soniox_api_key") == "placeholder-key"
