"""Two edits in a row of the Vertex TTS fields and of the "Âm lượng gốc" slider are both saved (custom F9/F10).

Browser QA lost every second edit. A widget without `key=` gets an id built from its `value=`, and these values
follow config.yaml, so a save gives the widget a new id. The browser keeps the old id until the rerun that follows
the save reaches it: the volume slider had no rerun, and each Vertex run without a Google credential waits about
3 s for google.auth. An edit sent with the old id meanwhile is ignored. AppTest always waits for the rerun, so the
tests also check the id that the browser holds: it must stay the same across a save.
"""

import textwrap

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from core.tts_backend import vertex_tts
from core.utils import config_utils
from core.utils.config_utils import load_key_or
from core.utils.google_credentials import GoogleCredentialError

VOICES = [{"name": "vi-VN-Chirp3-HD-Aoede", "ssmlGender": "FEMALE"},
          {"name": "vi-VN-Chirp3-HD-Charon", "ssmlGender": "MALE"},
          {"name": "vi-VN-Wavenet-A", "ssmlGender": "FEMALE"}]


def _vertex():
    from core.st_utils import vertex_tts_settings

    vertex_tts_settings.render()


def _volume():
    from core.st_utils import original_volume_setting

    original_volume_setting.render()


@pytest.fixture
def config(tmp_path, monkeypatch):
    path = tmp_path / "config.yaml"
    monkeypatch.setattr(config_utils, "CONFIG_PATH", str(path))
    st.cache_data.clear()
    path.write_text(textwrap.dedent("""
        tts_method: 'vertex_tts'
        original_volume: 0.2
        vertex_tts:
          voice: 'vi-VN-Chirp3-HD-Aoede'
          language: 'en-US'
          speed: 1.0
          max_workers: 3
    """), encoding="utf-8")
    yield
    st.cache_data.clear()


@pytest.fixture
def no_credential(monkeypatch):
    def missing(language):
        raise GoogleCredentialError("No Google credential found")

    monkeypatch.setattr(vertex_tts, "list_voices", missing)


def widget(at, kind, label):
    return next(item for item in getattr(at, kind) if item.label == label)


def edit_twice(app, kind, label, key, values, set_value):
    at = AppTest.from_function(app).run()
    for value in values:
        before = widget(at, kind, label).id
        at = set_value(widget(at, kind, label), value).run()
        assert not at.exception
        assert load_key_or(key, None) == value
        assert widget(at, kind, label).id == before, "a save must not change the id that the browser holds"


@pytest.mark.parametrize("kind, label, key, values", [
    ("text_input", "Vertex voice", "vertex_tts.voice", ["vi-VN-Chirp3-HD-Charon", "vi-VN-Wavenet-A"]),
    ("text_input", "Vertex speech language (BCP-47)", "vertex_tts.language", ["vi-VN", "en-GB"]),
    ("slider", "Vertex speech speed", "vertex_tts.speed", [1.1, 0.9]),
    ("number_input", "Vertex parallel requests (max_workers)", "vertex_tts.max_workers", [5, 6]),
])
def test_two_vertex_edits_in_a_row_are_both_saved(config, no_credential, kind, label, key, values):
    edit_twice(_vertex, kind, label, key, values, lambda item, value: item.set_value(value))


def test_two_vertex_voice_picks_in_a_row_are_both_saved(config, monkeypatch):
    monkeypatch.setattr(vertex_tts, "list_voices", lambda language: VOICES)
    edit_twice(_vertex, "selectbox", "Vertex voice", "vertex_tts.voice",
               ["vi-VN-Chirp3-HD-Charon", "vi-VN-Chirp3-HD-Aoede"], lambda item, value: item.select(value))


def test_the_voice_list_follows_the_chirp_filter(config, monkeypatch):
    monkeypatch.setattr(vertex_tts, "list_voices", lambda language: VOICES)
    at = AppTest.from_function(_vertex).run()
    at = widget(at, "checkbox", "Chirp 3 HD voices only").uncheck().run()
    at = widget(at, "selectbox", "Vertex voice").select("vi-VN-Wavenet-A").run()
    at = widget(at, "checkbox", "Chirp 3 HD voices only").check().run()
    assert not at.exception
    assert load_key_or("vertex_tts.voice", None) == "vi-VN-Wavenet-A"
    assert widget(at, "selectbox", "Vertex voice").value == "vi-VN-Wavenet-A"  # kept at the top of the list


def test_two_volume_edits_in_a_row_are_both_saved(config):
    edit_twice(_volume, "slider", "Âm lượng gốc (Thuyết minh)", "original_volume", [0.25, 0.3, 0.35],
               lambda item, value: item.set_value(value))
