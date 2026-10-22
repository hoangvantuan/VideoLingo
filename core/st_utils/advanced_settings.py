"""#12 (custom) — the "Nâng cao" expander of the sidebar: every key that an operator may change and that had no
widget yet, grouped like config.example.yaml. See the key table in CUSTOM.md.

Only config.yaml is written (through config_fields, so an older config.yaml gets the missing keys); the
processing code reads the keys as before. A key that is not in config.yaml shows the config.example.yaml value.
Labels are plain text, not translation keys, so no locale file has to change.
"""

import streamlit as st

from core.st_utils import config_fields


def _number(label, key, min_value, max_value, step, help, fallback):
    """A number field; int or float like `step`. A hand-edited value outside the range is kept until changed."""
    kind = type(step)
    stored = kind(config_fields.current(key, fallback))
    shown = min(max_value, max(min_value, stored))
    value = st.number_input(label, min_value=min_value, max_value=max_value, value=shown, step=step,
                            help=help, key=f"advanced_{key}")
    if kind is float:
        value = round(value, 2)
    if value != shown:
        config_fields.save(key, value)


def _choice(label, key, options, help, fallback, format_func=str):
    """A selectbox; a hand-edited value that is not an option stays selectable."""
    stored = config_fields.current(key, fallback)
    options = list(options) if stored in options else [stored, *options]
    value = st.selectbox(label, options, index=options.index(stored), help=help, format_func=format_func,
                         key=f"advanced_{key}")
    if value != stored:
        config_fields.save(key, value)


def _toggle(label, key, help, fallback):
    stored = bool(config_fields.current(key, fallback))
    value = st.toggle(label, value=stored, help=help, key=f"advanced_{key}")
    if value != stored:
        config_fields.save(key, value)


def _text(label, key, help, fallback=""):
    stored = str(config_fields.current(key, fallback) or "")
    value = st.text_input(label, value=stored, help=help, key=f"advanced_{key}").strip()
    if value != stored:
        config_fields.save(key, value)


def general():
    st.markdown("**Chung / hiệu năng**")
    _number("Số luồng LLM (max_workers)", "max_workers", 1, 64, 1, fallback=4,
            help="Số request LLM song song; đặt 1 nếu dùng LLM chạy local")
    _number("Số request TTS song song (tts_max_workers)", "tts_max_workers", 0, 64, 1, fallback=0,
            help="Giới hạn số request TTS song song; 0 = bằng max_workers")
    _toggle("Tăng tốc GPU cho FFmpeg (h264_nvenc)", "ffmpeg_gpu", fallback=False,
            help="Mã hóa video bằng h264_nvenc; chỉ bật khi GPU NVIDIA hỗ trợ")
    _choice("Độ phân giải tải YouTube", "ytb_resolution", ["360", "1080", "best"], fallback="1080",
            help="Độ phân giải mặc định khi tải video YouTube")


def asr():
    """Only the keys of the local backend that is selected; the cloud runtimes have none."""
    if config_fields.current("whisper.runtime", "local") != "local":
        return
    backend = config_fields.current("whisper.backend", "qwen")
    st.markdown("**Nhận dạng giọng nói (ASR)**")
    if backend == "qwen":
        _choice("Cỡ model Qwen3-ASR (whisper.qwen_model)", "whisper.qwen_model", ["1.7b", "0.6b"], fallback="1.7b",
                help="1.7b chính xác hơn, 0.6b nhanh hơn và tốn ít bộ nhớ hơn")
        _choice("Engine Qwen3-ASR (whisper.qwen_engine)", "whisper.qwen_engine", ["auto", "mlx", "transformers"],
                fallback="auto", help="auto = MLX trên Apple Silicon, qwen-asr/transformers ở máy khác")
    elif backend == "whisperx":
        _text("Model WhisperX (whisper.model)", "whisper.model", fallback="large-v3",
              help="large-v3; tên chứa \"turbo\" được đổi thành large-v3. Với zh, WhisperX luôn dùng Belle/large-v3")


STYLE_KINDS = {"source": "phụ đề gốc", "translation": "phụ đề dịch"}
COLOR_HELP = "&HBBGGRR, &HAABBGGRR (AA = độ trong suốt) hoặc #RRGGBB"


def _style(kind, key, label, field):
    """One value of subtitle.style.<kind> that the Subtitle Style popover does not edit."""
    from core.utils.subtitle_style import get_subtitle_style, save_subtitle_style, to_ass_color

    style = get_subtitle_style(kind)
    label = f"{label} – {STYLE_KINDS[kind]}"
    if field == "color":
        entered = st.text_input(label, value=style[key], help=COLOR_HELP, key=f"advanced_style_{kind}_{key}").strip()
        value = to_ass_color(entered)
        if value is None:
            st.warning(f"{label}: '{entered}' không phải màu hợp lệ ({COLOR_HELP}), chưa lưu.")
            return
    else:
        value = st.number_input(label, min_value=0, max_value=200, value=int(style[key]), step=1,
                                key=f"advanced_style_{kind}_{key}")
    if value != style[key]:
        save_subtitle_style({kind: {**style, key: value}})


def subtitle():
    st.markdown("**Phụ đề**")
    _number("Độ dài tối đa một dòng (subtitle.max_length)", "subtitle.max_length", 10, 200, 1, fallback=75,
            help="Số ký tự tối đa của mỗi dòng phụ đề")
    _number("Hệ số độ dài bản dịch (subtitle.target_multiplier)", "subtitle.target_multiplier", 0.5, 3.0, 0.1,
            fallback=1.2, help="Phụ đề dịch dài hơn phụ đề gốc chút ít; ảnh hưởng độ dài tham chiếu khi chia phụ đề")
    for kind in STYLE_KINDS:
        _style(kind, "outline_color", "Màu viền", "color")
        _style(kind, "outline_width", "Độ dày viền", "number")
    _style("translation", "back_color", "Màu nền", "color")
    _style("translation", "margin_v", "Lề dưới", "number")


def translation():
    st.markdown("**Dịch**")
    _number("Độ dài tóm tắt (summary_length)", "summary_length", 500, 50000, 500, fallback=8000,
            help="Độ dài phần tóm tắt nội dung gửi kèm khi dịch; giảm còn khoảng 2000 nếu dùng LLM local")
    _number("Số từ tối đa khi cắt thô (max_split_length)", "max_split_length", 10, 40, 1, fallback=20,
            help="Dưới 18 cắt quá vụn, ảnh hưởng bản dịch; trên 22 quá dài, khó căn khi chia phụ đề")
    _toggle("Dịch hai bước, có rà soát (reflect_translate)", "reflect_translate", fallback=True,
            help="Dịch sát nghĩa rồi rà soát lại cho tự nhiên; tắt = chỉ dịch sát nghĩa một lượt")


def dubbing_timing():
    st.markdown("**Lồng tiếng – tốc độ và thời lượng**")
    # min ≤ accept ≤ max: each bound is the configured neighbour
    speeds = {name: float(config_fields.current(f"speed_factor.{name}", fallback))
              for name, fallback in (("min", 1.0), ("accept", 1.2), ("max", 1.4))}
    _number("Tốc độ tối thiểu (speed_factor.min)", "speed_factor.min", 0.5, max(0.5, speeds["accept"]), 0.05,
            fallback=1.0, help="Hệ số tốc độ đọc thấp nhất của audio lồng tiếng")
    _number("Tốc độ tối đa chấp nhận (speed_factor.accept)", "speed_factor.accept", speeds["min"],
            max(speeds["min"], speeds["max"]), 0.05, fallback=1.2,
            help="Tốc độ cao nhất vẫn nghe tự nhiên; vượt mức này thì mượn khoảng lặng")
    _number("Tốc độ tối đa (speed_factor.max)", "speed_factor.max", min(3.0, speeds["accept"]), 3.0, 0.05,
            fallback=1.4, help="Hệ số tốc độ đọc cao nhất của audio lồng tiếng")
    _number("Thời lượng phụ đề tối thiểu (min_subtitle_duration)", "min_subtitle_duration", 0.0, 10.0, 0.1,
            fallback=2.5, help="Giây; phụ đề ngắn hơn được kéo dài bắt buộc")
    _number("Ngưỡng không chia phụ đề (min_trim_duration)", "min_trim_duration", 0.0, 10.0, 0.1, fallback=3.5,
            help="Giây; phụ đề ngắn hơn giá trị này không bị chia")
    _number("Thời gian lấn sang phụ đề sau (tolerance)", "tolerance", 0.0, 10.0, 0.1, fallback=1.5,
            help="Giây được phép kéo dài sang phụ đề kế tiếp")


SAMPLE_RATES = [16000, 22050, 24000, 32000, 44100, 48000]
BITRATES = ["64k", "96k", "128k", "192k", "256k", "320k"]


def audio():
    st.markdown("**Âm thanh**")
    _choice("Tần số lấy mẫu audio gốc (audio.raw_sample_rate)", "audio.raw_sample_rate", SAMPLE_RATES,
            fallback=32000, help="Hz của raw.mp3; tách giọng Demucs và mẫu nhân bản giọng theo băng thông này. "
                                 "16000 giới hạn khoảng 7 kHz. raw.mp3 đã có thì không trích lại")
    _choice("Bitrate audio gốc (audio.raw_bitrate)", "audio.raw_bitrate", BITRATES, fallback="128k",
            help="Bitrate của raw.mp3")


def _fish_audio_voices():
    """fish_audio.voices as one "name: ID" line per voice; the ID may be the address of the voice page."""
    from core.tts_backend.fish_audio_tts import voice_id_of

    label = "Danh sách giọng Fish Audio (fish_audio.voices)"
    stored = {str(name): str(voice_id) for name, voice_id in dict(config_fields.current("fish_audio.voices", {}) or {}).items()}
    entered = st.text_area(label, value="\n".join(f"{name}: {voice_id}" for name, voice_id in stored.items()),
                           key="advanced_fish_audio.voices",
                           help="Mỗi dòng một giọng của fish.audio: 'tên: ID' (ID hoặc địa chỉ trang của giọng); "
                                "hiện trong ô Voice của chế độ Fixed voice")
    voices, bad = {}, []
    for line in filter(None, (line.strip() for line in entered.splitlines())):
        name, _, voice_id = line.rpartition(": ")
        if not name.strip() or not voice_id.strip():
            bad.append(line)
        else:
            voices[name.strip()] = voice_id_of(voice_id)
    if bad:
        st.warning(f"{label}: dòng không đúng dạng 'tên: ID', chưa lưu: {'; '.join(bad)}")
    elif voices != stored:
        config_fields.save("fish_audio.voices", voices)


def dubbing_provider():
    """The keys of the selected TTS method that its own settings do not show."""
    method = config_fields.current("tts_method", "")
    if method == "openai_tts":
        st.markdown("**Lồng tiếng – OpenAI TTS**")
        _text("Base URL OpenAI TTS (openai_tts.base_url)", "openai_tts.base_url", fallback="https://api.openlux.ai/v1",
              help="Base URL của endpoint speech tương thích API OpenAI")
        _text("Model OpenAI TTS (openai_tts.model)", "openai_tts.model", fallback="gpt-4o-mini-tts",
              help="Model của endpoint speech")
    elif method == "fish_audio":
        st.markdown("**Lồng tiếng – Fish Audio**")
        _choice("Model Fish Audio (fish_audio.model)", "fish_audio.model", ["s2.1-pro", "s2-pro", "s1"],
                fallback="s2.1-pro", help="Model TTS của fish.audio")
        _fish_audio_voices()
    elif method == "soniox_tts":
        st.markdown("**Lồng tiếng – Soniox TTS**")
        _text("Model Soniox TTS (soniox_tts.model)", "soniox_tts.model", fallback="tts-rt-v2",
              help="Model TTS của Soniox")


def render():
    """The whole "Nâng cao" expander, at the end of the sidebar."""
    with st.expander("Nâng cao", expanded=False):
        general()
        asr()
        subtitle()
        translation()
        dubbing_provider()
        dubbing_timing()
        audio()
