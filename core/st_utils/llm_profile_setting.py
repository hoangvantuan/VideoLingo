"""F7 (custom) — picker for the Profile đang dùng in the LLM Configuration of the sidebar, see CUSTOM.md.

Profiles are added, edited and removed in config.yaml; the sidebar only chooses one and writes
its name to api.profile. Labels are plain text, not translation keys, so no locale file changes.
"""

import streamlit as st

from core.utils.config_utils import load_key, load_key_or, update_key
from core.utils.llm_profile import CUSTOM_PROFILE

CUSTOM_LABEL = "Profile custom (mục api: gốc)"


def _summary(name, profiles):
    """(provider, model) as written in config.yaml; the resolver reports anything missing."""
    if name == CUSTOM_PROFILE:
        return "custom", load_key("api.model")
    entry = profiles.get(name) or {}
    return entry.get("provider") or "?", entry.get("model") or "?"


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
        "LLM profile",
        options=options,
        index=options.index(current),
        format_func=lambda name: CUSTOM_LABEL if name == CUSTOM_PROFILE else name,
        help="Thêm, sửa, xóa profile trong mục llm_profiles của config.yaml.",
    )
    if chosen != current:
        update_key("api.profile", chosen, add_missing=True)
        st.rerun()

    if chosen not in profiles and chosen != CUSTOM_PROFILE:
        st.error(f"api.profile '{chosen}' không có trong llm_profiles, hãy chọn profile khác.")
        return False
    provider, model = _summary(chosen, profiles)
    st.caption(f"Provider: `{provider}` · Model: `{model}`")
    if chosen == CUSTOM_PROFILE:
        return True

    if st.button("📡 Check API", key="api_profile", use_container_width=True):
        from core.st_utils.sidebar_setting import check_api, show_api_check

        with st.spinner("Check API..."):
            is_valid, error = check_api()
        show_api_check(is_valid, error)
    return False
