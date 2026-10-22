"""Sidebar settings of the Soniox TTS method (custom fork, see CUSTOM.md).

Labels are plain text, not translation keys, so no locale file has to change.
"""

import streamlit as st

from core.st_utils.tts_settings import save_settings
from core.tts_backend import soniox_tts
from core.utils.config_utils import load_key_or


@st.cache_data(ttl=3600, show_spinner=False)
def _voices(api_key, model):
    return soniox_tts.list_voices(api_key, model)


def _voice_label(voice):
    parts = [voice.get("name") or voice["id"], voice.get("gender") or "", voice.get("age") or "",
             voice.get("accent") or ""]
    description = (voice.get("description") or "").strip()
    if description:
        parts.append(description[:70] + ("…" if len(description) > 70 else ""))
    return " · ".join(part for part in parts if part)


def render():
    model = load_key_or("soniox_tts.model", soniox_tts.MODEL) or soniox_tts.MODEL
    current = str(load_key_or("soniox_tts.voice", soniox_tts.VOICE) or soniox_tts.VOICE)
    values = {}

    voices = []
    try:
        voices = _voices(soniox_tts.configured_api_key(), model)
    except Exception as error:
        st.warning(f"Could not load Soniox voices: {error}")
    if voices:
        by_id = {voice["id"]: voice for voice in voices}
        accents = sorted({voice.get("accent") or "other" for voice in voices},
                         key=lambda name: (name != soniox_tts.CLONED, name))
        default_accent = (by_id.get(current) or {}).get("accent") or "all"
        accent = st.selectbox("Soniox voice accent", ["all"] + accents, key="soniox_tts_accent",
                              index=(["all"] + accents).index(default_accent)
                              if default_accent in accents else 0)
        genders = sorted({voice.get("gender") or "other" for voice in voices})
        gender = st.selectbox("Soniox voice gender", ["all"] + genders, key="soniox_tts_gender")
        ids = [voice["id"] for voice in voices
               if (accent == "all" or (voice.get("accent") or "other") == accent)
               and (gender == "all" or (voice.get("gender") or "other") == gender)]
        if current in by_id and current not in ids:
            ids.insert(0, current)
        voice = st.selectbox("Soniox voice", ids,
                             index=ids.index(current) if current in ids else 0,
                             format_func=lambda voice_id: _voice_label(by_id[voice_id]))
    else:
        voice = st.text_input("Soniox voice", value=current, help="Built-in voice name or cloned voice ID")
    if voice and voice != current:
        values["soniox_tts.voice"] = voice

    language = load_key_or("soniox_tts.language", soniox_tts.LANGUAGE) or soniox_tts.LANGUAGE
    entered = st.text_input("Soniox speech language (ISO code)", value=language,
                            help="Language of the dubbing text, e.g. vi, en, ja")
    if entered.strip() and entered.strip() != language:
        values["soniox_tts.language"] = entered.strip()

    speed = float(load_key_or("soniox_tts.speed", 1.0) or 1.0)
    chosen = st.slider("Soniox speech speed", 0.7, 1.3, value=min(1.3, max(0.7, speed)), step=0.05)
    if abs(chosen - speed) > 1e-9:
        values["soniox_tts.speed"] = round(chosen, 2)

    if values:
        save_settings(values)
        st.rerun()
