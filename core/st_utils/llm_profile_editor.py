"""Custom (#11, F7/F8) — add, edit and delete LLM profiles and set the shared vertex: section in the sidebar.

Shown under the Profile đang dùng picker in LLM Configuration, behind a toggle (an expander cannot be
nested there). Only config.yaml is written; the resolver (core/utils/llm_profile.py) is unchanged.
Labels are plain text, not translation keys, so no locale file has to change.
"""

import streamlit as st

from core.st_utils import config_fields
from core.utils.config_utils import load_key_or
from core.utils.llm_profile import CUSTOM_PROFILE, PROVIDERS

NEW = ""  # editor target for a profile not yet in llm_profiles
GENERIC_PROVIDER = "openai"  # any OpenAI-compatible endpoint; needs base_url like every provider without a default
SUPPORTED_PROVIDERS = [*PROVIDERS, GENERIC_PROVIDER]
NEEDS_BASE_URL = {GENERIC_PROVIDER}
REASONING_EFFORTS = ["", "minimal", "low", "medium", "high"]
JSON_MODES = {None: "Mặc định (theo Provider / api.llm_support_json)", True: "Bật", False: "Tắt"}
TEXT_FIELDS = {  # entry key -> label; empty values are left out of the entry
    "model": "Model",
    "base_url": "Base URL",
    "api_key_env": "Biến môi trường chứa key",
}
TARGET_KEY = "llm_profile_editor_target"
PENDING_KEY = "llm_profile_editor_pending"  # target to select on the next run, set before the selectbox exists
NOTICE_KEY = "llm_profile_editor_notice"
DELETE_KEY = "llm_profile_editor_delete"  # profile whose deletion waits for "Xác nhận xóa"


def problems(name, entry, profiles, original):
    """Messages for a profile that the resolver would reject or that would clash with another profile."""
    found = []
    if not name:
        found.append("Tên profile không được để trống.")
    elif name != original and name in profiles:
        found.append(f"Tên profile '{name}' đã có trong llm_profiles.")
    if entry["provider"] not in SUPPORTED_PROVIDERS:
        found.append(f"Provider '{entry['provider']}' không hỗ trợ; chọn một trong: {', '.join(SUPPORTED_PROVIDERS)}.")
    if not entry.get("model"):
        found.append("Model không được để trống.")
    if entry["provider"] in NEEDS_BASE_URL and not entry.get("base_url"):
        found.append(f"Provider '{entry['provider']}' cần Base URL.")
    return found


def _max_workers(text):
    """(value or None, problem or None) for the max_workers field; empty = the general max_workers."""
    text = text.strip()
    if not text:
        return None, None
    try:
        value = int(text)
    except ValueError:
        value = 0
    return (value, None) if value >= 1 else (None, "max_workers phải là số nguyên ≥ 1 (để trống = dùng max_workers chung).")


def _write(profiles, name, entry, original):
    """Store `entry` under `name`, in place so the comments and order of config.yaml stay."""
    if original and original in profiles:
        if name != original:
            position = list(profiles).index(original)
            del profiles[original]
            if hasattr(profiles, "insert"):
                profiles.insert(position, name, entry)
            else:
                profiles[name] = entry
        elif isinstance(profiles[original], dict):
            stored = profiles[original]
            for key in [key for key in stored if key not in entry]:
                del stored[key]
            stored.update(entry)
        else:
            profiles[original] = entry  # declared without fields (`name:` alone)
    else:
        profiles[name] = entry
    config_fields.save("llm_profiles", profiles)
    if original and name != original and load_key_or("api.profile", CUSTOM_PROFILE) == original:
        config_fields.save("api.profile", name)


def _delete(profiles, name):
    del profiles[name]
    config_fields.save("llm_profiles", profiles)
    if load_key_or("api.profile", CUSTOM_PROFILE) == name:
        config_fields.save("api.profile", CUSTOM_PROFILE)  # the deleted profile was in use: back to Profile custom


def _profile_form(profiles):
    if PENDING_KEY in st.session_state:
        st.session_state[TARGET_KEY] = st.session_state.pop(PENDING_KEY)
    target = st.selectbox("Sửa profile", [NEW, *profiles], key=TARGET_KEY,
                          format_func=lambda name: "➕ Profile mới" if name == NEW else name)
    stored = profiles.get(target) or {}
    key = f"llm_profile_editor_{target}_"  # per target, so switching never shows another profile's input

    name = st.text_input("Tên profile", value=target, key=key + "name").strip()
    providers = list(SUPPORTED_PROVIDERS)
    provider = stored.get("provider") or providers[0]
    if provider not in providers:
        providers.append(provider)  # shown as written, reported when saved
    entry = {"provider": st.selectbox("Provider", providers, index=providers.index(provider), key=key + "provider",
                                      help=f"{GENERIC_PROVIDER} = endpoint tương thích OpenAI, cần Base URL; "
                                           "vertex = Gemini trên Vertex AI, xác thực bằng credential Google")}
    for field, label in TEXT_FIELDS.items():
        entry[field] = st.text_input(label, value=str(stored.get(field) or ""), key=key + field).strip()
    entry["api_key"] = st.text_input("API key (dự phòng)", value=str(stored.get("api_key") or ""), type="password",
                                     key=key + "api_key",
                                     help="Nên để trống và đặt key vào biến môi trường ở trên").strip()

    json_mode = stored.get("llm_support_json")
    json_mode = bool(json_mode) if json_mode is not None else None
    entry["llm_support_json"] = st.selectbox("JSON mode", list(JSON_MODES), index=list(JSON_MODES).index(json_mode),
                                             format_func=JSON_MODES.get, key=key + "json")
    workers, workers_problem = _max_workers(st.text_input(
        "Số luồng (max_workers)", value=str(stored.get("max_workers") or ""), key=key + "max_workers",
        help="Để trống = dùng max_workers chung"))
    entry["max_workers"] = workers
    efforts = list(REASONING_EFFORTS)
    effort = str(stored.get("reasoning_effort") or "")
    if effort not in efforts:
        efforts.append(effort)
    entry["reasoning_effort"] = st.selectbox("reasoning_effort", efforts, index=efforts.index(effort),
                                             key=key + "effort",
                                             format_func=lambda value: value or "Không gửi")
    entry = {field: value for field, value in entry.items() if value not in ("", None)}

    if st.button("💾 Lưu profile", key=key + "save", use_container_width=True):
        found = problems(name, entry, profiles, target) + ([workers_problem] if workers_problem else [])
        for message in found:
            st.error(message)
        if not found:
            _write(profiles, name, entry, target)
            st.session_state[PENDING_KEY] = name
            st.session_state[NOTICE_KEY] = f"Đã lưu profile '{name}'."
            st.rerun()
    if target == NEW:
        return
    if st.button("🗑 Xóa profile", key=key + "delete", use_container_width=True):
        st.session_state[DELETE_KEY] = target
    if st.session_state.get(DELETE_KEY) != target:  # a confirmation asked for another profile is dropped
        st.session_state.pop(DELETE_KEY, None)
        return
    st.warning(f"Xóa profile '{target}' khỏi llm_profiles?")
    confirm, cancel = st.columns(2)
    if confirm.button("Xác nhận xóa", key=key + "delete_confirm", type="primary", use_container_width=True):
        st.session_state.pop(DELETE_KEY)
        _delete(profiles, target)
        st.session_state[PENDING_KEY] = NEW
        st.session_state[NOTICE_KEY] = f"Đã xóa profile '{target}'."
        st.rerun()
    if cancel.button("Hủy", key=key + "delete_cancel", use_container_width=True):
        st.session_state.pop(DELETE_KEY)
        st.rerun()


def _vertex_inputs():
    st.markdown("**Vertex AI (dùng chung cho Khâu Dịch và Lồng tiếng)**")
    project = str(config_fields.current("vertex.project", "") or "")
    entered = st.text_input("Vertex project", value=project,
                            help="Project ID bị tính phí; để trống = project của credential Google").strip()
    if entered != project:
        config_fields.save("vertex.project", entered)
        st.rerun()
    location = str(config_fields.current("vertex.location_llm", "global") or "global")
    entered = st.text_input("Vertex location (Khâu Dịch)", value=location,
                            help="Vùng của endpoint Gemini, ví dụ global hoặc us-central1").strip()
    if entered and entered != location:
        config_fields.save("vertex.location_llm", entered)
        st.rerun()


def render():
    if not st.toggle("Quản lý LLM profile & Vertex AI", key="llm_profile_editor_open"):
        return
    if NOTICE_KEY in st.session_state:
        st.success(st.session_state.pop(NOTICE_KEY))
    _profile_form(load_key_or("llm_profiles", None) or {})
    _vertex_inputs()
