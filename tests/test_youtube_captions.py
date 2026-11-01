"""Custom: the original-language YouTube captions take the place of the recognition."""
import json
from unittest.mock import patch

import pytest

from core import _2_asr as asr
from core._1_ytdlp import find_captions, write_input_manifest
from core.asr_backend import youtube_captions as yc

ORIG = "https://www.youtube.com/api/timedtext?v=x&kind=asr&lang=en&fmt=json3"
TRANSLATED = ORIG + "&tlang=vi"


def formats(url):
    return [{"ext": "vtt", "url": url + "&fmt=vtt"}, {"ext": "json3", "url": url}]


def test_auto_captions_pick_the_original_track_never_a_translation():
    info = {"language": "en-US", "subtitles": {},
            "automatic_captions": {"vi": formats(TRANSLATED), "en": formats(ORIG), "en-orig": formats(ORIG)}}
    assert yc.pick_track(info) == ("en", "auto", ORIG)


def test_uploader_track_in_the_video_language_comes_first():
    manual = "https://www.youtube.com/api/timedtext?v=x&lang=en-GB&fmt=json3"
    info = {"language": "en", "subtitles": {"vi": formats(manual + "x"), "en-GB": formats(manual)},
            "automatic_captions": {"en-orig": formats(ORIG)}}
    assert yc.pick_track(info) == ("en", "manual", manual)


def test_without_video_language_any_orig_track_is_used():
    info = {"language": None, "subtitles": {"fr": formats("https://x/fr")},
            "automatic_captions": {"ja": formats(TRANSLATED), "ja-orig": formats(ORIG)}}
    assert yc.pick_track(info) == ("ja", "auto", ORIG)


def test_no_original_track():
    info = {"language": "en", "subtitles": {"vi": formats("https://x/vi")},
            "automatic_captions": {"vi": formats(TRANSLATED)}}
    assert yc.pick_track(info) is None


AUTO = {"events": [
    {"tStartMs": 0, "dDurationMs": 50000},  # window style, no text
    {"tStartMs": 1000, "dDurationMs": 4000, "segs": [
        {"utf8": "Hello"}, {"utf8": " world,", "tOffsetMs": 500}, {"utf8": " again.", "tOffsetMs": 1500}]},
    {"tStartMs": 3000, "dDurationMs": 10, "aAppend": 1, "segs": [{"utf8": "\n"}]},
    {"tStartMs": 4000, "dDurationMs": 2000, "segs": [{"utf8": "Next", "tOffsetMs": 0}]},
]}


def test_automatic_captions_keep_the_time_of_each_word():
    result = yc.json3_to_result(AUTO)
    assert [s["text"] for s in result["segments"]] == ["Hello world, again.", "Next"]
    words = result["segments"][0]["words"]
    assert [(w["word"], w["start"], w["end"]) for w in words] == [
        ("Hello", 1.0, 1.5), ("world,", 1.5, 2.5), ("again.", 2.5, 4.0)]  # ends where the next caption starts
    assert result["segments"][1]["words"] == [{"word": "Next", "start": 4.0, "end": 6.0}]


def test_uploader_caption_shares_its_time_by_word_length():
    data = {"events": [{"tStartMs": 0, "dDurationMs": 3000, "segs": [{"utf8": "ab abcd"}]}]}
    words = yc.json3_to_result(data)["segments"][0]["words"]
    assert [(w["word"], w["start"], w["end"]) for w in words] == [("ab", 0.0, 1.0), ("abcd", 1.0, 3.0)]


def test_manifest_keeps_the_captions(tmp_path):
    video = tmp_path / "v.mp4"
    video.write_bytes(b"")
    path = tmp_path / yc.CAPTIONS_FILE
    path.write_text(json.dumps(AUTO), encoding="utf-8")
    captions = {"path": str(path), "language": "en", "kind": "auto"}
    write_input_manifest(str(video), "video", str(tmp_path), captions=captions)
    assert find_captions(str(tmp_path)) == captions
    write_input_manifest(str(video), "video", str(tmp_path))
    assert find_captions(str(tmp_path)) is None


def test_youtube_runtime_without_captions_fails_before_preparing_audio():
    with patch.object(asr, "load_key", return_value="youtube"), patch.object(asr, "find_captions", return_value=None), \
            patch.object(asr, "prepare_audio") as prepare:
        with pytest.raises(ValueError, match="No YouTube captions"):
            asr.transcribe.__wrapped__()
        prepare.assert_not_called()


def test_youtube_runtime_saves_the_caption_words(tmp_path):
    path = tmp_path / yc.CAPTIONS_FILE
    path.write_text(json.dumps(AUTO), encoding="utf-8")
    keys = {"whisper.runtime": "youtube", "whisper.language": "en", "demucs": False}
    with patch.object(asr, "load_key", side_effect=keys.get), \
            patch.object(asr, "find_captions", return_value={"path": str(path), "language": "en", "kind": "auto"}), \
            patch.object(asr, "find_media_file", return_value=("v.mp4", "video")), \
            patch.object(asr, "prepare_audio") as prepare, patch.object(asr, "update_key") as update, \
            patch.object(asr, "save_results") as save:
        asr.transcribe.__wrapped__()
    prepare.assert_called_once_with("v.mp4", "video", False)
    update.assert_called_once_with("whisper.detected_language", "en")
    assert list(save.call_args.args[0]["text"]) == ["Hello", "world,", "again.", "Next"]
