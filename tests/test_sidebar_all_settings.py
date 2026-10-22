"""#12 (custom): every key that an operator has a reason to change is set from the sidebar, on a config.yaml
older than those keys."""

import shutil
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from core.utils import config_utils
from core.utils.config_utils import load_key, load_key_or

EXAMPLE = Path(__file__).resolve().parents[1] / "config.example.yaml"
# keys deleted from the temporary config.yaml, as in a config.yaml written before them
MISSING = {None: ["tts_max_workers", "audio", "speed_factor", "summary_length", "reflect_translate"],
           "subtitle": ["target_multiplier", "style"], "whisper": ["qwen_engine"], "openai_tts": ["model"]}


def _sidebar():
    from core.st_utils.sidebar_setting import page_setting

    page_setting()


@pytest.fixture
def config(tmp_path, monkeypatch):
    """config.example.yaml (placeholders only) without some keys; returns a function that sets top-level keys."""
    shutil.copy(EXAMPLE, tmp_path / "config.example.yaml")
    with open(EXAMPLE, encoding="utf-8") as file:
        data = config_utils.yaml.load(file)
    for section, keys in MISSING.items():
        for key in keys:
            del (data[section] if section else data)[key]
    path = tmp_path / "config.yaml"

    def write(**values):
        data.update(values)
        with open(path, "w", encoding="utf-8") as file:
            config_utils.yaml.dump(data, file)

    write()
    monkeypatch.setattr(config_utils, "CONFIG_PATH", str(path))
    st.cache_data.clear()
    yield write
    st.cache_data.clear()


def widget(at, kind, label):
    return next(item for item in getattr(at, kind) if item.label == label)


def run():
    at = AppTest.from_function(_sidebar).run(timeout=30)
    assert not at.exception
    return at


def test_general_keys(config):
    at = run()
    at = widget(at, "number_input", "Số luồng LLM (max_workers)").set_value(2).run(timeout=30)
    at = widget(at, "number_input", "Số request TTS song song (tts_max_workers)").set_value(1).run(timeout=30)
    at = widget(at, "toggle", "Tăng tốc GPU cho FFmpeg (h264_nvenc)").set_value(True).run(timeout=30)
    at = widget(at, "selectbox", "Độ phân giải tải YouTube").select("best").run(timeout=30)
    assert not at.exception
    assert load_key("max_workers") == 2
    assert load_key("tts_max_workers") == 1
    assert load_key("ffmpeg_gpu") is True
    assert load_key("ytb_resolution") == "best"


def test_qwen_keys_show_only_for_the_local_qwen_backend(config):
    at = run()
    at = widget(at, "selectbox", "Cỡ model Qwen3-ASR (whisper.qwen_model)").select("0.6b").run(timeout=30)
    at = widget(at, "selectbox", "Engine Qwen3-ASR (whisper.qwen_engine)").select("mlx").run(timeout=30)
    assert not at.exception
    assert load_key("whisper.qwen_model") == "0.6b"
    assert load_key("whisper.qwen_engine") == "mlx"
    assert not [box for box in at.text_input if box.label == "Model WhisperX (whisper.model)"]


def test_whisperx_model_shows_only_for_the_whisperx_backend(config):
    whisper = dict(load_key("whisper"), backend="whisperx")
    config(whisper=whisper)
    at = run()
    at = widget(at, "text_input", "Model WhisperX (whisper.model)").input("large-v2").run(timeout=30)
    assert not at.exception
    assert load_key("whisper.model") == "large-v2"
    assert not [box for box in at.selectbox if box.label.startswith("Engine Qwen3-ASR")]
    config(whisper=dict(whisper, runtime="soniox"))
    at = run()
    assert not [box for box in at.text_input if box.label == "Model WhisperX (whisper.model)"]


def test_subtitle_keys(config):
    from core.utils.subtitle_style import get_subtitle_style

    at = run()
    at = widget(at, "number_input", "Độ dài tối đa một dòng (subtitle.max_length)").set_value(60).run(timeout=30)
    at = widget(at, "number_input", "Hệ số độ dài bản dịch (subtitle.target_multiplier)").set_value(1.5).run(timeout=30)
    at = widget(at, "number_input", "Độ dày viền – phụ đề dịch").set_value(2).run(timeout=30)
    at = widget(at, "text_input", "Màu nền – phụ đề dịch").input("#112233").run(timeout=30)
    at = widget(at, "text_input", "Màu viền – phụ đề gốc").input("not a color").run(timeout=30)
    assert [box for box in at.warning if "not a color" in box.value]  # an unusable color is not saved
    at = widget(at, "number_input", "Lề dưới – phụ đề dịch").set_value(40).run(timeout=30)
    assert not at.exception
    assert load_key("subtitle.max_length") == 60
    assert load_key("subtitle.target_multiplier") == 1.5
    translation = get_subtitle_style("translation")
    assert (translation["outline_width"], translation["back_color"], translation["margin_v"]) == (2, "&H332211", 40)
    assert get_subtitle_style("source")["outline_color"] == "&H000000"
    assert load_key("subtitle.style.translation.font_size") == 17  # the other values of the style stay


def test_translation_keys(config):
    at = run()
    at = widget(at, "number_input", "Độ dài tóm tắt (summary_length)").set_value(2000).run(timeout=30)
    at = widget(at, "number_input", "Số từ tối đa khi cắt thô (max_split_length)").set_value(18).run(timeout=30)
    at = widget(at, "toggle", "Dịch hai bước, có rà soát (reflect_translate)").set_value(False).run(timeout=30)
    assert not at.exception
    assert load_key("summary_length") == 2000
    assert load_key("max_split_length") == 18
    assert load_key("reflect_translate") is False


def test_dubbing_timing_keys(config):
    at = run()
    at = widget(at, "number_input", "Tốc độ tối đa chấp nhận (speed_factor.accept)").set_value(1.3).run(timeout=30)
    at = widget(at, "number_input", "Tốc độ tối đa (speed_factor.max)").set_value(1.5).run(timeout=30)
    at = widget(at, "number_input", "Tốc độ tối thiểu (speed_factor.min)").set_value(0.9).run(timeout=30)
    at = widget(at, "number_input", "Thời lượng phụ đề tối thiểu (min_subtitle_duration)").set_value(2.0).run(timeout=30)
    at = widget(at, "number_input", "Ngưỡng không chia phụ đề (min_trim_duration)").set_value(4.0).run(timeout=30)
    at = widget(at, "number_input", "Thời gian lấn sang phụ đề sau (tolerance)").set_value(1.0).run(timeout=30)
    assert not at.exception
    assert dict(load_key("speed_factor")) == {"min": 0.9, "accept": 1.3, "max": 1.5}
    assert (load_key("min_subtitle_duration"), load_key("min_trim_duration"), load_key("tolerance")) == (2.0, 4.0, 1.0)


def test_audio_keys(config):
    at = run()
    at = widget(at, "selectbox", "Tần số lấy mẫu audio gốc (audio.raw_sample_rate)").select(16000).run(timeout=30)
    at = widget(at, "selectbox", "Bitrate audio gốc (audio.raw_bitrate)").select("192k").run(timeout=30)
    assert not at.exception
    assert load_key("audio.raw_sample_rate") == 16000
    assert load_key("audio.raw_bitrate") == "192k"


def test_openai_tts_keys_show_for_openai_tts_only(config):
    config(tts_method="openai_tts")
    at = run()
    at = widget(at, "text_input", "Base URL OpenAI TTS (openai_tts.base_url)").input("https://tts.example.com/v1").run(timeout=30)
    at = widget(at, "text_input", "Model OpenAI TTS (openai_tts.model)").input("tts-1").run(timeout=30)
    assert not at.exception
    assert load_key("openai_tts.base_url") == "https://tts.example.com/v1"
    assert load_key("openai_tts.model") == "tts-1"
    assert not [box for box in at.selectbox if box.label == "Model Fish Audio (fish_audio.model)"]


def test_fish_audio_keys(config):
    config(tts_method="fish_audio")
    at = run()
    at = widget(at, "selectbox", "Model Fish Audio (fish_audio.model)").select("s1").run(timeout=30)
    voices = widget(at, "text_area", "Danh sách giọng Fish Audio (fish_audio.voices)")
    at = voices.input(voices.value + "\nMy voice: https://fish.audio/m/0123456789abcdef0123456789abcdef").run(timeout=30)
    assert not at.exception
    assert load_key("fish_audio.model") == "s1"
    voices = dict(load_key("fish_audio.voices"))
    assert voices["My voice"] == "0123456789abcdef0123456789abcdef"
    assert voices["浩然 Haoran (中文, male)"] == "d675c275d1d44e57b4ef3840c5a23209"
    assert len(voices) == 3


def test_soniox_tts_model(config, monkeypatch):
    from core.tts_backend import soniox_tts

    monkeypatch.setattr(soniox_tts, "list_voices", lambda api_key, model=None: [])
    monkeypatch.setattr(soniox_tts, "configured_api_key", lambda: "")
    config(tts_method="soniox_tts")
    at = run()
    at = widget(at, "text_input", "Model Soniox TTS (soniox_tts.model)").input("tts-rt-v3").run(timeout=30)
    assert not at.exception
    assert load_key("soniox_tts.model") == "tts-rt-v3"
