"""Tests for speaker-change marker (>>) and non-speech CC tag ([...]) cleaning."""

import pytest

from core._8_2_dub_chunks import clean_line
from core.asr_backend.audio_preprocess import process_transcription
from core.asr_backend.youtube_captions import clean_caption_text, json3_to_result
from core.tts_backend.tts_main import clean_text_for_tts


@pytest.mark.parametrize(
    "raw,expected",
    [
        (">> Everyone's got a story.", "Everyone's got a story."),
        (">> [laughter]", ""),
        ("[music]", ""),
        ("[INAUDIBLE]", ""),
        ("parameters are [INAUDIBLE]", "parameters are"),
        ("How do you use [? generalizing ?] in practice?", "How do you use generalizing in practice?"),
        ("It's [? a cure. ?]\nI don't buy that.", "It's a cure. I don't buy that."),
        ("Vector [0, 1] and tokens [CLS], [SEP], [MASK]", "Vector [0, 1] and tokens [CLS], [SEP], [MASK]"),
        ("Matrix [1, 0, 0] with [cos(φ), sin(φ)] and [1 - P(A)]", "Matrix [1, 0, 0] with [cos(φ), sin(φ)] and [1 - P(A)]"),
    ],
)
def test_clean_caption_text(raw, expected):
    assert clean_caption_text(raw) == expected


def test_json3_to_result_strips_speaker_markers_and_cc_tags_and_skips_empty_events():
    data = {
        "events": [
            {"tStartMs": 0, "dDurationMs": 1000, "segs": [{"utf8": "[music]"}]},
            {
                "tStartMs": 1000,
                "dDurationMs": 2000,
                "segs": [
                    {"utf8": ">> Everyone's", "tOffsetMs": 0},
                    {"utf8": " got [INAUDIBLE]", "tOffsetMs": 500},
                    {"utf8": " a [? generalizing ?] vector [0, 1].", "tOffsetMs": 1000},
                    {"utf8": " [laughter]", "tOffsetMs": 1800},
                ],
            },
            {"tStartMs": 3000, "dDurationMs": 1000, "segs": [{"utf8": ">> [applause]"}]},
            {"tStartMs": 4000, "dDurationMs": 1000, "segs": [{"utf8": "Token [CLS] works."}]},
        ]
    }
    res = json3_to_result(data)
    assert [seg["text"] for seg in res["segments"]] == [
        "Everyone's got a generalizing vector [0, 1].",
        "Token [CLS] works.",
    ]


def test_process_transcription_strips_speaker_markers_and_skips_empty_words():
    result = {
        "segments": [
            {
                "start": 0.0,
                "end": 2.0,
                "words": [
                    {"word": ">>", "start": 0.0, "end": 0.2},
                    {"word": ">>Hello", "start": 0.2, "end": 1.0},
                    {"word": "world<<", "start": 1.0, "end": 2.0},
                ],
            }
        ]
    }
    df = process_transcription(result)
    assert list(df["text"]) == ["Hello", "world"]


@pytest.mark.parametrize(
    "raw,expected",
    [
        (">> Xin chào các bạn.", "Xin chào các bạn."),
        ("[cười] >>", ""),
        ("[hắng giọng] Bắt đầu thôi.", "Bắt đầu thôi."),
        ("Phần này [KHÔNG NGHE RÕ] và [TIẾNG ỒN] rất nhiều.", "Phần này và rất nhiều."),
        ("Ta có [? tổng quát hóa ?] trên đoạn [0, 1] với [CLS].", "Ta có tổng quát hóa trên đoạn [0, 1] với [CLS]."),
        ("[nội dung câu lệnh] và [mất mát của R1 cộng mất mát của R2]", "[nội dung câu lệnh] và [mất mát của R1 cộng mất mát của R2]"),
    ],
)
def test_clean_text_for_tts_strips_markers_and_cc_tags_preserving_math(raw, expected):
    assert clean_text_for_tts(raw) == expected


def test_clean_line_and_process_srt_strip_speaker_markers_identically(tmp_path, monkeypatch):
    import core._8_1_audio_task as audio_task

    assert clean_line(">> Đây là câu đầu tiên.") == "Đây là câu đầu tiên."
    assert clean_line("[cười] >>") == "[cười]"
    assert clean_line("Câu một. >> Câu hai (cười)") == "Câu một. Câu hai"

    trans_srt = tmp_path / "trans_subs_for_audio.srt"
    src_srt = tmp_path / "src_subs_for_audio.srt"
    trans_srt.write_text(
        "1\n00:00:00,000 --> 00:00:03,000\n>> Đây là câu đầu tiên (cười)\n\n"
        "2\n00:00:03,000 --> 00:00:06,000\nCâu thứ hai >> tiếp theo\n",
        encoding="utf-8",
    )
    src_srt.write_text(
        "1\n00:00:00,000 --> 00:00:03,000\n>> This is the first sentence\n\n"
        "2\n00:00:03,000 --> 00:00:06,000\nSecond sentence >> next\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(audio_task, "TRANS_SUBS_FOR_AUDIO_FILE", str(trans_srt))
    monkeypatch.setattr(audio_task, "SRC_SUBS_FOR_AUDIO_FILE", str(src_srt))
    monkeypatch.setattr(audio_task, "load_key", lambda k: 1.0 if k == "min_subtitle_duration" else None)

    df = audio_task.process_srt()
    assert list(df["text"]) == ["Đây là câu đầu tiên", "Câu thứ hai tiếp theo"]
