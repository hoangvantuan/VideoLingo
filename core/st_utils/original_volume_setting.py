"""F10 (custom) — "Original volume" slider of the Dubbing Settings, see CUSTOM.md.

The label is plain text, not a translation key, so no locale file has to change.
"""

import streamlit as st

from core.utils.config_utils import load_key_or, update_key


def render():
    current = float(load_key_or("original_volume", 0) or 0)
    volume = st.slider(
        "Original volume (voice-over)", min_value=0.0, max_value=1.0, value=current, step=0.05,
        help="Level of the video's own audio under the dubbed voice (0.25 = 25%). "
             "0 keeps the previous merge: the Demucs background if there is one, otherwise the dub alone.",
    )
    if volume != current:
        update_key("original_volume", volume, add_missing=True)
