"""Duration estimation must work on a fresh install without NLTK corpora."""

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_estimator_starts_when_optional_g2p_data_is_unavailable():
    code = """
import sys
import types

g2p = types.ModuleType('g2p_en')
class MissingData:
    def __init__(self):
        raise LookupError('NLTK cmudict is unavailable')
g2p.G2p = MissingData
sys.modules['g2p_en'] = g2p

from core.tts_backend.estimate_duration import init_estimator
estimator = init_estimator()
assert estimator.count_syllables('Hello world', 'en') > 0
assert estimator.count_syllables('你好世界', 'zh') == 4
"""
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_vietnamese_duration_estimation_with_acronyms_and_numbers():
    import statistics
    import pytest
    from core.tts_backend.estimate_duration import init_estimator, estimate_duration

    estimator = init_estimator()

    breakdown = estimator.process_mixed_text(
        "chúng tôi chỉ có cửa sổ agent, có giao diện CLI, rồi có IDE."
    )
    assert "vi" in breakdown["language_breakdown"]
    assert breakdown["total_syllables"] == 18
    assert breakdown["estimated_duration"] == pytest.approx(5.34)

    # Measured Chirp3 HD durations (real_dur) from issue #23
    measured_cases = [
        ("Rồi nó phán một câu cực kỳ chắc nịch là 'Lỗi do cái này này'.", 4.20),
        (
            "Kiểu như PR nào cũng chỉ tầm 50 dòng. Không có mức giới hạn cố định nào cả. "
            "Đúng vậy, chắc chắn không có quy định cứng nhắc.",
            7.44,
        ),
        ("vốn có một—nếu muốn đạt tầm 60 FPS, bạn phải—", 3.80),
        ("chúng tôi chỉ có cửa sổ agent, có giao diện CLI, rồi có IDE.", 6.48),
        (
            "Hẹn gặp lại các bạn trong số tiếp theo. Được rồi. Cảm ơn mọi người. Tạm biệt.",
            5.48,
        ),
    ]
    relative_errors = [
        abs(estimate_duration(text, estimator) - real_dur) / real_dur
        for text, real_dur in measured_cases
    ]
    assert statistics.median(relative_errors) < 0.10


def test_pre_tts_trim_uses_accept_speed_factor_and_zero_min_trim_duration(monkeypatch):
    from core import _8_1_audio_task as audio_task
    from core.utils import config_utils

    with open(ROOT / "config.yaml", encoding="utf-8") as f:
        cfg = config_utils.yaml.load(f)
    assert cfg["min_trim_duration"] == 0

    # 12 Vietnamese syllables + 1 period = 12 * 0.28 + 0.1 = 3.46s
    # At max=1.4: 3.46 / 1.4 = 2.47s <= 2.76s (would NOT trim)
    # At accept=1.2: 3.46 / 1.2 = 2.88s > 2.76s (MUST trim)
    text = "Một hai ba bốn năm sáu bảy tám chín mười một hai."
    monkeypatch.setattr(audio_task, "speed_factor", {"min": 1.0, "accept": 1.2, "max": 1.4})
    monkeypatch.setattr(audio_task, "ask_gpt", lambda *a, **kw: {"result": "Một hai ba bốn."})

    assert audio_task.check_len_then_trim(text, duration=2.76) == "Một hai ba bốn."


def test_overlapping_subtitles_clamp_gap_and_tolerance_to_non_negative(monkeypatch):
    import pandas as pd
    from core import _8_2_dub_chunks as dub_chunks

    monkeypatch.setattr(dub_chunks, "get_audio_duration", lambda _: 20.0)
    monkeypatch.setattr(
        dub_chunks,
        "load_key",
        lambda key: 1.5 if key == "tolerance" else 1.2,
    )
    df = pd.DataFrame(
        {
            "number": [949, 950],
            "start_time": ["00:00:10.483", "00:00:13.063"],
            "end_time": ["00:00:13.483", "00:00:16.000"],
            "duration": [3.0, 2.937],
            "text": [
                "vốn có một—nếu muốn đạt tầm 60 FPS, bạn phải—",
                "làm như thế này.",
            ],
        }
    )

    analyzed = dub_chunks.analyze_subtitle_timing_and_speed(df)

    assert analyzed.loc[0, "gap"] == 0.0
    assert analyzed.loc[0, "tolerance"] == 0.0
    assert analyzed.loc[0, "tol_dur"] == 3.0


def test_merge_chunks_retries_trim_and_resynthesizes_before_truncating(monkeypatch, tmp_path):
    import pandas as pd
    from pydub import AudioSegment
    from pydub.generators import Sine
    from core import _10_gen_audio as audio

    config = {"speed_factor.accept": 1.2, "speed_factor.min": 1.0, "speed_factor.max": 1.4}
    monkeypatch.setattr(audio, "load_key", config.get)
    monkeypatch.setattr(audio, "TEMP_FILE_TEMPLATE", str(tmp_path / "{}_temp.wav"))
    monkeypatch.setattr(audio, "OUTPUT_FILE_TEMPLATE", str(tmp_path / "{}.wav"))
    monkeypatch.setattr(audio, "TRUNCATED_LOG", str(tmp_path / "log" / "dub_truncated.json"))
    monkeypatch.setattr(
        audio,
        "get_audio_duration",
        lambda path: len(AudioSegment.from_wav(path)) / 1000,
    )

    def write_wav(path, seconds):
        Sine(440).to_audio_segment(duration=int(seconds * 1000)).export(path, format="wav")

    # Initial temp audio is 3.5s (2.5s at max speed 1.4x > 2.0s slot)
    write_wav(tmp_path / "1_0_temp.wav", 3.5)

    def fake_speed(temp_file, output_file, speed_factor):
        dur = len(AudioSegment.from_wav(temp_file)) / 1000
        write_wav(output_file, dur / speed_factor)

    tts_calls = []

    def fake_tts(text, save_as, number, tasks_df):
        tts_calls.append((text, number))
        write_wav(save_as, 2.1)

    monkeypatch.setattr(audio, "adjust_audio_speed", fake_speed)
    monkeypatch.setattr(audio, "tts_main", fake_tts)
    monkeypatch.setattr(
        audio,
        "ask_gpt",
        lambda prompt, **kw: {"result": "Câu đã rút gọn."},
    )

    tasks = pd.DataFrame(
        {
            "number": [1],
            "cut_off": [1],
            "tol_dur": [2.0],
            "tolerance": [0.0],
            "gap": [0.0],
            "real_dur": [3.5],
            "start_time": ["00:00:10.000"],
            "end_time": ["00:00:12.000"],
            "lines": [["Một câu tiếng Việt rất dài bị tràn khung thời gian."]],
        }
    )

    result = audio.merge_chunks(tasks)

    assert tts_calls == [("Câu đã rút gọn.", 1)]
    assert result.at[0, "lines"] == ["Câu đã rút gọn."]
    assert result.at[0, "real_dur"] == 2.1
    assert result.at[0, "new_sub_times"][0][1] <= 12.0
    assert not (tmp_path / "log" / "dub_truncated.json").exists()


def test_merge_chunks_truncates_after_max_two_trim_retries(monkeypatch, tmp_path):
    import json
    import pandas as pd
    from pydub import AudioSegment
    from pydub.generators import Sine
    from core import _10_gen_audio as audio

    config = {"speed_factor.accept": 1.2, "speed_factor.min": 1.0, "speed_factor.max": 1.4}
    monkeypatch.setattr(audio, "load_key", config.get)
    monkeypatch.setattr(audio, "TEMP_FILE_TEMPLATE", str(tmp_path / "{}_temp.wav"))
    monkeypatch.setattr(audio, "OUTPUT_FILE_TEMPLATE", str(tmp_path / "{}.wav"))
    monkeypatch.setattr(audio, "TRUNCATED_LOG", str(tmp_path / "log" / "dub_truncated.json"))
    monkeypatch.setattr(
        audio,
        "get_audio_duration",
        lambda path: len(AudioSegment.from_wav(path)) / 1000,
    )

    def write_wav(path, seconds):
        Sine(440).to_audio_segment(duration=int(seconds * 1000)).export(path, format="wav")

    write_wav(tmp_path / "1_0_temp.wav", 4.2)

    def fake_speed(temp_file, output_file, speed_factor):
        dur = len(AudioSegment.from_wav(temp_file)) / 1000
        write_wav(output_file, dur / speed_factor)

    tts_calls = []

    def fake_tts(text, save_as, number, tasks_df):
        tts_calls.append(text)
        # Still 3.5s even after shortening (2.5s at 1.4x > 2.0s slot)
        write_wav(save_as, 3.5)

    replies = iter([{"result": "Ngắn lần 1."}, {"result": "Ngắn lần 2."}, {"result": "Ngắn lần 3."}])
    monkeypatch.setattr(audio, "adjust_audio_speed", fake_speed)
    monkeypatch.setattr(audio, "tts_main", fake_tts)
    monkeypatch.setattr(audio, "ask_gpt", lambda prompt, **kw: next(replies))

    tasks = pd.DataFrame(
        {
            "number": [1],
            "cut_off": [1],
            "tol_dur": [2.0],
            "tolerance": [0.0],
            "gap": [0.0],
            "real_dur": [4.2],
            "start_time": ["00:00:10.000"],
            "end_time": ["00:00:12.000"],
            "lines": [["Câu ban đầu quá dài."]],
        }
    )

    result = audio.merge_chunks(tasks)

    assert tts_calls == ["Ngắn lần 1.", "Ngắn lần 2."]
    assert result.at[0, "lines"] == ["Ngắn lần 2."]
    assert result.at[0, "new_sub_times"] == [[10.0, 12.0]]
    log = json.loads((tmp_path / "log" / "dub_truncated.json").read_text(encoding="utf-8"))
    assert log == [
        {
            "number": 1,
            "line": "Ngắn lần 2.",
            "spoken_seconds": 2.5,
            "kept_seconds": 2.0,
            "speed_factor": 1.4,
        }
    ]




