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
    language = load_key_or("vertex_tts.language", vertex_tts.LANGUAGE) or vertex_tts.LANGUAGE
    configured = str(load_key_or("vertex_tts.voice", "") or "")
    values = {}

    voices = []
    try:
        voices = _voices(language)
    except GoogleCredentialError as error:
        st.info(f"Vertex AI needs a Google credential: set GOOGLE_APPLICATION_CREDENTIALS to the "
                f"service-account key JSON and restart VideoLingo ({error})")
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
                             format_func=lambda name: _voice_label(by_name.get(name, {"name": name})))
    else:
        voice = st.text_input("Vertex voice", value=current, help="Cloud TTS voice name, e.g. vi-VN-Chirp3-HD-Charon")
    if voice and voice != current:
        values["vertex_tts.voice"] = voice

    entered = st.text_input("Vertex speech language (BCP-47)", value=language,
                            help="Voices are listed for this language, e.g. vi-VN")
    if entered.strip() and entered.strip() != language:
        values["vertex_tts.language"] = entered.strip()

    speed = float(load_key_or("vertex_tts.speed", 1.0) or 1.0)
    shown = min(MAX_SPEED, max(MIN_SPEED, speed))
    chosen = st.slider("Vertex speech speed", MIN_SPEED, MAX_SPEED, value=shown, step=0.05,
                       help="A hand-edited speed outside this range is kept until the slider is moved")
    if abs(chosen - shown) > 1e-9:
        values["vertex_tts.speed"] = round(chosen, 2)

    if values:
        save_settings(values)
        st.rerun()
