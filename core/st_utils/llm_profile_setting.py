"""F7 (custom) — picker for the Profile đang dùng in the LLM Configuration of the sidebar, see CUSTOM.md.

This picker only chooses a profile and writes its name to api.profile; profiles are added, edited
and removed by llm_profile_editor (the toggle under it) or in config.yaml. Labels are plain text, not translation keys, so no locale file changes.
"""

import streamlit as st

from core.utils.config_utils import load_key_or, update_key
from core.utils.llm_profile import CUSTOM_PROFILE, describe

CUSTOM_LABEL = "Profile custom (mục api: gốc)"


def render():
    """Draw the picker; True when the custom profile is active, so the upstream api inputs apply."""
    profiles = load_key_or("llm_profiles", None) or {}
    current = load_key_or("api.profile", CUSTOM_PROFILE) or CUSTOM_PROFILE
    options = [CUSTOM_PROFILE, *profiles]
    if current not in options:
        options.append(current)  # stale name stays selectable until the operator picks another
    if len(options) == 1:
        return True  # no llm_profiles: the sidebar stays as upstream

    chosen = st.selectbox(
        "Profile đang dùng",
        options=options,
        index=options.index(current),
        format_func=lambda name: CUSTOM_LABEL if name == CUSTOM_PROFILE else name,
        help="Thêm, sửa, xóa profile bằng nút 'Quản lý LLM profile & Vertex AI' bên dưới.",
    )
    if chosen != current:
        update_key("api.profile", chosen, add_missing=True)
        st.rerun()

    summary = describe(chosen)  # as written in config.yaml; the resolver reports anything missing
    if summary is None:
        st.error(f"api.profile '{chosen}' không có trong llm_profiles, hãy chọn profile khác.")
        return False
    provider, model = summary
    st.caption(f"Provider: `{provider}` · Model: `{model}`")
    if chosen == CUSTOM_PROFILE:
        return True

    if st.button("📡 Check API", key="api_profile", use_container_width=True):
        # imported here: sidebar_setting imports this module, and only these two helpers are shared
        from core.st_utils.sidebar_setting import check_api, show_api_check

        with st.spinner("Check API..."):
            is_valid, error = check_api()
        show_api_check(is_valid, error)
    return False
