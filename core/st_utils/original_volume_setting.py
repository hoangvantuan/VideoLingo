"""F10 (custom) — "Âm lượng gốc" slider of the Thuyết minh mode of the Dubbing Settings, see CUSTOM.md.

The label is plain text, not a translation key, so no locale file has to change.
"""

import streamlit as st

from core.utils.config_utils import load_key_or, update_key


def render():
    current = float(load_key_or("original_volume", 0) or 0)
    volume = round(st.slider(
        "Âm lượng gốc (Thuyết minh)", min_value=0.0, max_value=1.0, value=current, step=0.05,
        help="Mức âm thanh gốc của video giữ lại dưới giọng lồng tiếng (0.25 = 25%). "
             "0 = tắt Thuyết minh: trộn như cũ (track nền Demucs nếu có, không thì chỉ giọng lồng tiếng).",
    ), 2)  # the float step can return 0.30000000000000004
    if volume != current:
        update_key("original_volume", volume, add_missing=True)
