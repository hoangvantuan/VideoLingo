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


def test_pre_tts_trim_uses_accept_speed_factor(monkeypatch):
    from core import _8_1_audio_task as audio_task

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






def test_merge_chunks_trims_multi_line_row_read_from_excel(monkeypatch, tmp_path):
    """`lines` read back from tts_tasks.xlsx is a string column (StringDtype on
    pandas 3), which refuses a list of more than one item."""
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

    # Two lines of 2.0s each: 4.0s, about 2.9s at max speed 1.4x > 2.0s slot
    write_wav(tmp_path / "1_0_temp.wav", 2.0)
    write_wav(tmp_path / "1_1_temp.wav", 2.0)

    def fake_speed(temp_file, output_file, speed_factor):
        dur = len(AudioSegment.from_wav(temp_file)) / 1000
        write_wav(output_file, dur / speed_factor)

    def fake_tts(text, save_as, number, tasks_df):
        write_wav(save_as, 1.0)

    monkeypatch.setattr(audio, "adjust_audio_speed", fake_speed)
    monkeypatch.setattr(audio, "tts_main", fake_tts)
    monkeypatch.setattr(audio, "ask_gpt", lambda prompt, **kw: {"result": "Ngắn."})

    tasks = pd.DataFrame(
        {
            "number": [1],
            "cut_off": [1],
            "tol_dur": [2.0],
            "tolerance": [0.0],
            "gap": [0.0],
            "real_dur": [4.0],
            "start_time": ["00:00:10.000"],
            "end_time": ["00:00:12.000"],
            "lines": ["['Dòng đầu quá dài.', 'Dòng sau cũng dài.']"],
        }
    )
    xlsx = tmp_path / "tts_tasks.xlsx"
    tasks.to_excel(xlsx, index=False)
    tasks = pd.read_excel(xlsx)

    result = audio.merge_chunks(tasks)

    assert list(audio.parse_task_literal(result.at[0, "lines"])) == ["Ngắn.", "Ngắn."]
    assert result.at[0, "new_sub_times"][-1][1] <= 12.0


def test_merge_chunks_trim_replaces_existing_temp_audio_with_resynthesized_line(monkeypatch, tmp_path):
    """The temp audio of the overflowing line already exists (written by
    generate_tts_audio), and tts_main skips a path that exists. The trimmed line
    must still be synthesized and replace it."""
    import pandas as pd
    from pydub import AudioSegment
    from pydub.generators import Sine
    from core import _10_gen_audio as audio
    from core.tts_backend import tts_main as tts_module

    config = {"speed_factor.accept": 1.2, "speed_factor.min": 1.0, "speed_factor.max": 1.4}
    monkeypatch.setattr(audio, "load_key", config.get)
    monkeypatch.setattr(audio, "TEMP_FILE_TEMPLATE", str(tmp_path / "{}_temp.wav"))
    monkeypatch.setattr(audio, "OUTPUT_FILE_TEMPLATE", str(tmp_path / "{}.wav"))
    monkeypatch.setattr(audio, "TRUNCATED_LOG", str(tmp_path / "log" / "dub_truncated.json"))
    duration = lambda path: len(AudioSegment.from_wav(path)) / 1000
    monkeypatch.setattr(audio, "get_audio_duration", duration)
    monkeypatch.setattr(tts_module, "get_audio_duration", duration)

    def write_wav(path, seconds):
        Sine(440).to_audio_segment(duration=int(seconds * 1000)).export(path, format="wav")

    # 3.5s is 2.5s at max speed 1.4x, more than the 2.0s slot
    write_wav(tmp_path / "1_0_temp.wav", 3.5)

    def fake_speed(temp_file, output_file, speed_factor):
        write_wav(output_file, duration(temp_file) / speed_factor)

    synthesized = []

    def fake_backend(text, save_as):
        synthesized.append(text)
        write_wav(save_as, 2.1)

    # The real tts_main runs; only the TTS service behind it is faked
    monkeypatch.setattr(audio, "adjust_audio_speed", fake_speed)
    monkeypatch.setattr(tts_module, "load_key", {"tts_method": "edge_tts"}.get)
    monkeypatch.setattr(tts_module, "edge_tts", fake_backend)
    monkeypatch.setattr(audio, "ask_gpt", lambda prompt, **kw: {"result": "Câu đã rút gọn."})

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

    assert synthesized == ["Câu đã rút gọn."]
    assert duration(tmp_path / "1_0_temp.wav") == 2.1
    assert result.at[0, "real_dur"] == 2.1
    assert result.at[0, "new_sub_times"][0][1] <= 12.0
    assert not (tmp_path / "log" / "dub_truncated.json").exists()


def test_generate_tts_audio_reruns_only_offending_line_in_multi_line_row(monkeypatch, tmp_path):
    """Per-line trigger catches the v9 #131 shape: line 0 is > 2x its own
    estimate while the row total (9.04s vs 5.06s = 1.79x) is under 2x."""
    import pandas as pd
    from pydub import AudioSegment
    from pydub.generators import Sine
    from core import _10_gen_audio as audio

    monkeypatch.setattr(audio, "TEMP_FILE_TEMPLATE", str(tmp_path / "{}_temp.wav"))
    monkeypatch.setattr(audio, "LONG_TTS_LOG", str(tmp_path / "log" / "tts_long_lines.json"), raising=False)
    monkeypatch.setattr(
        audio,
        "get_audio_duration",
        lambda path: len(AudioSegment.from_wav(path)) / 1000,
    )

    def write_wav(path, seconds):
        Sine(440).to_audio_segment(duration=int(seconds * 1000)).export(path, format="wav")

    tts_calls = []
    # Line 0: 5.36s (> 2 * 1.32s), retry -> 1.48s; Line 1: 2.08s; Line 2: 1.60s
    durations = iter([5.36, 1.48, 2.08, 1.60])

    def fake_tts(text, save_as, number, tasks_df):
        tts_calls.append((text, number))
        write_wav(save_as, next(durations))

    monkeypatch.setattr(audio, "tts_main", fake_tts)
    monkeypatch.setattr(
        audio,
        "ask_gpt",
        lambda prompt, **kw: {"text": "khi có các ticket,"},
    )

    original_lines = [
        "...khi có các ticket,",
        "ta chỉ cần triển khai từng ticket",
        "trong một phiên code riêng biệt.",
    ]
    tasks = pd.DataFrame(
        {
            "number": [131],
            "est_dur": [5.06],
            "lines": [original_lines],
        }
    )

    result = audio.generate_tts_audio(tasks)

    assert tts_calls == [
        ("...khi có các ticket,", 131),
        ("khi có các ticket,", 131),
        ("ta chỉ cần triển khai từng ticket", 131),
        ("trong một phiên code riêng biệt.", 131),
    ]
    assert result.at[0, "real_dur"] == round(1.48 + 2.08 + 1.60, 2)
    assert result.at[0, "lines"] == original_lines
    assert not (tmp_path / "log" / "tts_long_lines.json").exists()


def test_generate_tts_audio_keeps_old_audio_and_logs_when_retry_is_longer(monkeypatch, tmp_path):
    import json
    import pandas as pd
    from pydub import AudioSegment
    from pydub.generators import Sine
    from core import _10_gen_audio as audio

    monkeypatch.setattr(audio, "TEMP_FILE_TEMPLATE", str(tmp_path / "{}_temp.wav"))
    monkeypatch.setattr(audio, "LONG_TTS_LOG", str(tmp_path / "log" / "tts_long_lines.json"), raising=False)
    monkeypatch.setattr(
        audio,
        "get_audio_duration",
        lambda path: len(AudioSegment.from_wav(path)) / 1000,
    )

    def write_wav(path, seconds):
        Sine(440).to_audio_segment(duration=int(seconds * 1000)).export(path, format="wav")

    durations = iter([5.0, 6.2])

    def fake_tts(text, save_as, number, tasks_df):
        write_wav(save_as, next(durations))

    monkeypatch.setattr(audio, "tts_main", fake_tts)
    monkeypatch.setattr(
        audio,
        "ask_gpt",
        lambda prompt, **kw: {"text": "npx skills at latest add mattpocock slash skills."},
    )

    tasks = pd.DataFrame(
        {
            "number": [27],
            "est_dur": [2.125],
            "lines": [["npx skills@latest add mattpocock/skills."]],
        }
    )

    result = audio.generate_tts_audio(tasks)

    assert result.at[0, "real_dur"] == 5.0
    log_path = tmp_path / "log" / "tts_long_lines.json"
    assert log_path.exists()
    logged = json.loads(log_path.read_text(encoding="utf-8"))
    assert len(logged) == 1
    assert logged[0]["number"] == 27
    assert logged[0]["line_index"] == 0
    assert logged[0]["real_dur"] == 5.0


def test_generate_tts_audio_rejects_empty_or_degenerate_retry(monkeypatch, tmp_path):
    import pytest
    import pandas as pd
    from pydub import AudioSegment
    from pydub.generators import Sine
    from core import _10_gen_audio as audio

    monkeypatch.setattr(audio, "TEMP_FILE_TEMPLATE", str(tmp_path / "{}_temp.wav"))
    monkeypatch.setattr(audio, "LONG_TTS_LOG", str(tmp_path / "log" / "tts_long_lines.json"), raising=False)
    monkeypatch.setattr(
        audio,
        "get_audio_duration",
        lambda path: len(AudioSegment.from_wav(path)) / 1000,
    )

    def write_wav(path, seconds):
        Sine(440).to_audio_segment(duration=int(seconds * 1000)).export(path, format="wav")

    # Row 1: LLM returns None -> must not convert to "None" or synthesize
    # Row 2: LLM returns "." -> punctuation-only, rejected without calling tts_main
    # Row 3: LLM returns "OK" -> synthesized wav is 0.1s (< 0.5x line_est), rejected
    # Row 4: LLM returns unchanged text (after strip) -> skip second tts_main call
    line_text = "npx skills@latest add mattpocock/skills."
    replies = iter([{"text": None}, {"text": "."}, {"text": "OK"}, {"text": f"  {line_text}  "}])
    durations = iter([5.0, 5.0, 5.0, 0.1, 5.0])
    tts_calls = []

    def fake_tts(text, save_as, number, tasks_df):
        tts_calls.append((text, number))
        write_wav(save_as, next(durations))

    monkeypatch.setattr(audio, "tts_main", fake_tts)
    monkeypatch.setattr(audio, "ask_gpt", lambda prompt, **kw: next(replies))

    tasks = pd.DataFrame(
        {
            "number": [1, 2, 3, 4],
            "est_dur": [2.125, 2.125, 2.125, 2.125],
            "lines": [[line_text], [line_text], [line_text], [line_text]],
        }
    )

    result = audio.generate_tts_audio(tasks)

    assert ("None", 1) not in tts_calls
    assert (".", 2) not in tts_calls
    assert tts_calls == [
        (line_text, 1),
        (line_text, 2),
        (line_text, 3),
        ("OK", 3),
        (line_text, 4),
    ]
    assert list(result["real_dur"]) == [5.0, 5.0, 5.0, 5.0]


def test_generate_tts_audio_ignores_short_line_wav_padding_noise(monkeypatch, tmp_path):
    """Short utterances like 'Ừm.' (0.38s est, 1.24s real) or 'Được rồi.'
    (0.66s est, 1.48s real) exceed 2x est_dur solely because Vertex TTS wavs
    carry ~0.5-0.6s fixed padding. They must not trigger retry or logging."""
    import pandas as pd
    from pydub import AudioSegment
    from pydub.generators import Sine
    from core import _10_gen_audio as audio
    from core.utils import models

    assert audio.LONG_TTS_LOG == models._10_TTS_LONG_LINES
    monkeypatch.setattr(audio, "TEMP_FILE_TEMPLATE", str(tmp_path / "{}_temp.wav"))
    monkeypatch.setattr(audio, "LONG_TTS_LOG", str(tmp_path / "log" / "tts_long_lines.json"))
    monkeypatch.setattr(
        audio,
        "get_audio_duration",
        lambda path: len(AudioSegment.from_wav(path)) / 1000,
    )

    def write_wav(path, seconds):
        Sine(440).to_audio_segment(duration=int(seconds * 1000)).export(path, format="wav")

    durations = iter([1.24, 1.48])
    tts_calls = []

    def fake_tts(text, save_as, number, tasks_df):
        tts_calls.append((text, number))
        write_wav(save_as, next(durations))

    monkeypatch.setattr(audio, "tts_main", fake_tts)
    monkeypatch.setattr(
        audio,
        "ask_gpt",
        lambda *a, **kw: (_ for _ in ()).throw(AssertionError("ask_gpt must not be called for padding noise")),
    )

    tasks = pd.DataFrame(
        {
            "number": [7, 8],
            "est_dur": [0.38, 0.66],
            "lines": [["Ừm."], ["Được rồi."]],
        }
    )

    result = audio.generate_tts_audio(tasks)

    assert tts_calls == [("Ừm.", 7), ("Được rồi.", 8)]
    assert list(result["real_dur"]) == [1.24, 1.48]
    assert not (tmp_path / "log" / "tts_long_lines.json").exists()


def test_generate_tts_audio_skips_retry_when_line_est_is_zero_and_ignores_row_est_nan(monkeypatch, tmp_path):
    import pandas as pd
    from pydub import AudioSegment
    from pydub.generators import Sine
    from core import _10_gen_audio as audio

    monkeypatch.setattr(audio, "TEMP_FILE_TEMPLATE", str(tmp_path / "{}_temp.wav"))
    monkeypatch.setattr(audio, "LONG_TTS_LOG", str(tmp_path / "log" / "tts_long_lines.json"))
    monkeypatch.setattr(
        audio,
        "get_audio_duration",
        lambda path: len(AudioSegment.from_wav(path)) / 1000,
    )

    def write_wav(path, seconds):
        Sine(440).to_audio_segment(duration=int(seconds * 1000)).export(path, format="wav")

    # Row 1: line estimate is 0.0 (empty line) -> no retry even though wav is 5.0s
    # Row 2: row est_dur is NaN, but per-line estimate (~2.125s) is valid and 5.0s > 2x + >1.5s excess -> retries!
    durations = iter([5.0, 5.0, 2.2])
    tts_calls = []

    def fake_tts(text, save_as, number, tasks_df):
        tts_calls.append((text, number))
        write_wav(save_as, next(durations))

    monkeypatch.setattr(audio, "tts_main", fake_tts)
    monkeypatch.setattr(
        audio,
        "ask_gpt",
        lambda prompt, **kw: {"text": "npx skills at latest add mattpocock slash skills."},
    )

    tasks = pd.DataFrame(
        {
            "number": [1, 2],
            "est_dur": [0.0, float("nan")],
            "lines": [[""], ["npx skills@latest add mattpocock/skills."]],
        }
    )

    result = audio.generate_tts_audio(tasks)

    assert tts_calls == [
        ("", 1),
        ("npx skills@latest add mattpocock/skills.", 2),
        ("npx skills at latest add mattpocock slash skills.", 2),
    ]
    assert list(result["real_dur"]) == [5.0, 2.2]


def test_trim_and_resynthesize_chunk_uses_retried_spoken_text_and_rejects_longer_trim(monkeypatch, tmp_path):
    import pandas as pd
    from pydub import AudioSegment
    from pydub.generators import Sine
    from core import _10_gen_audio as audio

    config = {
        "speed_factor.accept": 1.2,
        "speed_factor.min": 1.0,
        "speed_factor.max": 1.4,
        "max_workers": 1,
        "tts_method": "edge_tts",
    }
    monkeypatch.setattr(audio, "load_key", config.get)
    monkeypatch.setattr(audio, "TEMP_FILE_TEMPLATE", str(tmp_path / "{}_temp.wav"))
    monkeypatch.setattr(audio, "OUTPUT_FILE_TEMPLATE", str(tmp_path / "{}.wav"))
    monkeypatch.setattr(audio, "TRUNCATED_LOG", str(tmp_path / "log" / "dub_truncated.json"))
    monkeypatch.setattr(audio, "LONG_TTS_LOG", str(tmp_path / "log" / "tts_long_lines.json"), raising=False)
    monkeypatch.setattr(
        audio,
        "get_audio_duration",
        lambda path: len(AudioSegment.from_wav(path)) / 1000,
    )

    def write_wav(path, seconds):
        Sine(440).to_audio_segment(duration=int(seconds * 1000)).export(path, format="wav")

    def fake_speed(temp_file, output_file, speed_factor):
        dur = len(AudioSegment.from_wav(temp_file)) / 1000
        write_wav(output_file, dur / speed_factor)

    # Initial TTS: 6.0s (> 2x est_dur) -> retry gives 3.5s (still overflows 2.0s slot at 1.4x)
    # Trim attempt 1: gives 4.0s (> 3.5s, must be rejected so real_dur stays 3.5s and does not regress to 4.0s!)
    durations = iter([6.0, 3.5, 4.0])
    prompts_seen = []

    def fake_tts(text, save_as, number, tasks_df):
        write_wav(save_as, next(durations))

    def fake_gpt(prompt, **kw):
        prompts_seen.append((kw.get("log_title"), prompt))
        if kw.get("log_title") == "tts_correct_text":
            return {"text": "Văn bản đã làm sạch cho TTS."}
        return {"result": "Văn bản rút gọn hơn."}

    monkeypatch.setattr(audio, "adjust_audio_speed", fake_speed)
    monkeypatch.setattr(audio, "tts_main", fake_tts)
    monkeypatch.setattr(audio, "ask_gpt", fake_gpt)

    tasks = pd.DataFrame(
        {
            "number": [1],
            "cut_off": [1],
            "tol_dur": [2.0],
            "tolerance": [0.0],
            "gap": [0.0],
            "est_dur": [2.125],
            "start_time": ["00:00:10.000"],
            "end_time": ["00:00:12.000"],
            "lines": [["npx skills@latest add mattpocock/skills."]],
        }
    )

    tasks = audio.generate_tts_audio(tasks)
    assert tasks.at[0, "real_dur"] == 3.5

    result = audio.merge_chunks(tasks)

    sub_trim_prompts = [p for title, p in prompts_seen if title == "sub_trim"]
    assert len(sub_trim_prompts) == 1
    assert "Văn bản đã làm sạch cho TTS." in sub_trim_prompts[0]
    assert result.at[0, "real_dur"] == 3.5
    assert result.at[0, "lines"] == ["npx skills@latest add mattpocock/skills."]

