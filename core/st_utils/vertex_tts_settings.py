"""Sidebar settings of the Vertex AI (Cloud TTS) method (custom fork, see CUSTOM.md).

Labels are plain text, not translation keys, so no locale file has to change.
"""

import streamlit as st

from core.st_utils.tts_settings import save_settings
from core.tts_backend import vertex_tts
from core.utils.config_utils import load_key_or
from core.utils.google_credentials import GoogleCredentialError

MIN_SPEED, MAX_SPEED = 0.7, 1.3  # safe range: the dub still fits the subtitle timing


@st.cache_data(ttl=3600, show_spinner=False)
def _voices(language):
    return vertex_tts.list_voices(language)


def _voice_label(voice):
    gender = (voice.get("ssmlGender") or "").lower()
    return " · ".join(part for part in (voice["name"], gender) if part)


def render():
    """Every widget has a stable key: an id built from a `value=` that follows config.yaml changes on each save, and
    an edit that the browser sends with the old id is lost (browser QA, see tests/test_consecutive_edits.py)."""
    language = vertex_tts.configured_language()
    configured = str(load_key_or("vertex_tts.voice", "") or "")
    values = {}

    voices = []
    try:
        voices = _voices(language)
    except GoogleCredentialError as error:  # missing credential or project: the message says which
        st.info(f"{error}. The voice name can be typed meanwhile; restart VideoLingo after changing "
                f"GOOGLE_APPLICATION_CREDENTIALS.")
    except Exception as error:
        st.warning(f"Could not load Cloud TTS voices: {error}")
    current = configured or vertex_tts.default_voice(voices)
    if voices:
        by_name = {voice["name"]: voice for voice in voices}
        chirp_only = st.checkbox("Chirp 3 HD voices only", value=current not in by_name
                                 or vertex_tts.CHIRP3_HD in current, key="vertex_tts_chirp_only")
        names = [voice["name"] for voice in voices if not chirp_only or vertex_tts.CHIRP3_HD in voice["name"]]
        if current not in names:
            names.insert(0, current)
        voice = st.selectbox("Vertex voice", names, index=names.index(current),
                             format_func=lambda name: _voice_label(by_name.get(name, {"name": name})), key="vertex_tts_voice")
    else:
        voice = st.text_input("Vertex voice", value=current, help="Cloud TTS voice name, e.g. vi-VN-Chirp3-HD-Charon",
                              key="vertex_tts_voice_name")
    if voice and voice != configured:  # an empty voice saves the preselected one, so the dub uses what is shown
        values["vertex_tts.voice"] = voice

    entered = st.text_input("Vertex speech language (BCP-47)", value=language,
                            help="Voices are listed for this language, e.g. vi-VN", key="vertex_tts_language")
    if entered.strip() and entered.strip() != language:
        values["vertex_tts.language"] = entered.strip()

    speed = vertex_tts.configured_speed()
    shown = min(MAX_SPEED, max(MIN_SPEED, speed))
    chosen = st.slider("Vertex speech speed", MIN_SPEED, MAX_SPEED, value=shown, step=0.05,
                       help="A hand-edited speed outside this range is kept until the slider is moved", key="vertex_tts_speed")
    if abs(chosen - shown) > 1e-9:
        values["vertex_tts.speed"] = round(chosen, 2)

    workers = int(load_key_or("vertex_tts.max_workers", 4) or 4)  # the fallback of _10_gen_audio
    chosen_workers = st.number_input("Vertex parallel requests (max_workers)", min_value=1, value=workers, step=1,
                                     help="Cloud TTS requests sent at once; replaces max_workers and tts_max_workers",
                                     key="vertex_tts_max_workers")
    if int(chosen_workers) != workers:
        values["vertex_tts.max_workers"] = int(chosen_workers)

    if values:
        save_settings(values)
        st.rerun()
