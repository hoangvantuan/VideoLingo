"""Vertex AI voice settings, driven through Streamlit's AppTest with a fake voice list (custom fork, F9)."""

import textwrap

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from core.tts_backend import vertex_tts
from core.utils import config_utils
from core.utils.config_utils import load_key_or
from core.utils.google_credentials import GoogleCredentialError


def _app():
    from core.st_utils import vertex_tts_settings

    vertex_tts_settings.render()


@pytest.fixture
def config(tmp_path, monkeypatch):
    path = tmp_path / "config.yaml"
    monkeypatch.setattr(config_utils, "CONFIG_PATH", str(path))
    st.cache_data.clear()
    path.write_text(textwrap.dedent("""
        tts_method: 'vertex_tts'
        vertex_tts:
          voice: ''
          language: 'vi-VN'
          speed: 1.0
    """), encoding="utf-8")
    yield
    st.cache_data.clear()


def run():
    return AppTest.from_function(_app).run()


def test_empty_voice_saves_the_preselected_default_so_the_dub_uses_it(config, monkeypatch):
    voices = [{"name": "vi-VN-Chirp3-HD-Charon", "ssmlGender": "MALE"},
              {"name": "vi-VN-Wavenet-A", "ssmlGender": "FEMALE"}]  # no vi-VN-Chirp3-HD-Aoede
    monkeypatch.setattr(vertex_tts, "list_voices", lambda language: voices)
    at = run()
    assert not at.exception
    assert at.selectbox[0].value == "vi-VN-Chirp3-HD-Charon"
    assert load_key_or("vertex_tts.voice", "") == "vi-VN-Chirp3-HD-Charon"
    assert vertex_tts.request_payload("x")["voice"]["name"] == "vi-VN-Chirp3-HD-Charon"


def test_missing_project_is_reported_as_such(config, monkeypatch):
    def no_project(language):
        raise GoogleCredentialError('Set vertex.project in config.yaml; see "Setup Google Cloud" in CUSTOM.md')

    monkeypatch.setattr(vertex_tts, "list_voices", no_project)
    at = run()
    assert not at.exception
    assert at.info[0].value.startswith("Set vertex.project in config.yaml")
    assert at.text_input[0].value == vertex_tts.VOICE
