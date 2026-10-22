"""Contracts at the Soniox transport and response boundary (custom fork)."""

import unittest
from unittest.mock import patch

from core.asr_backend import soniox_asr


def token(text, start, end, speaker="1", language=None):
    item = {"text": text, "start_ms": start, "end_ms": end, "speaker": speaker}
    if language:
        item["language"] = language
    return item


class SonioxConversionTests(unittest.TestCase):
    def test_english_subword_tokens_merge_into_words_with_offset(self):
        transcript = {"tokens": [
            token("Hel", 0, 100), token("lo", 100, 300), token(" world", 400, 700),
            token(".", 700, 720),
        ]}
        result = soniox_asr.soniox2whisper(transcript, "en", ["ja", "zh"], offset=30)
        self.assertEqual(result["language"], "en")
        [segment] = result["segments"]
        self.assertEqual(segment["text"], "Hello world.")
        self.assertEqual(
            [(w["word"], w["start"], w["end"]) for w in segment["words"]],
            [("Hello", 30.0, 30.3), ("world.", 30.4, 30.72)],
        )

    def test_japanese_tokens_stay_units_without_inserted_spaces(self):
        transcript = {"tokens": [
            token("今日", 0, 200, language="ja"), token("は", 200, 300, language="ja"),
            token("晴れ", 300, 600, language="ja"), token("。", 600, 650, language="ja"),
        ]}
        result = soniox_asr.soniox2whisper(transcript, "auto", ["ja", "zh"])
        self.assertEqual(result["language"], "ja")
        [segment] = result["segments"]
        self.assertEqual(segment["text"], "今日は晴れ。")
        self.assertEqual([w["word"] for w in segment["words"]], ["今日", "は", "晴れ", "。"])

    def test_segments_break_on_silence_and_speaker_change(self):
        transcript = {"tokens": [
            token("One", 0, 200), token(" two", 300, 500),
            token(" three", 1700, 1900),
            token(" four", 2000, 2200, speaker="2"),
        ]}
        result = soniox_asr.soniox2whisper(transcript, "en", [])
        self.assertEqual([s["text"] for s in result["segments"]], ["One two", "three", "four"])
        self.assertEqual([s["speaker_id"] for s in result["segments"]], ["1", "1", "2"])

    def test_auto_language_is_the_majority_and_config_uses_hints(self):
        transcript = {"tokens": [
            token("Hi", 0, 100, language="en"),
            token("こん", 200, 300, language="ja"), token("にちは", 300, 500, language="ja"),
        ]}
        self.assertEqual(soniox_asr.soniox2whisper(transcript, "auto", ["ja"])["language"], "ja")
        auto = soniox_asr.transcription_config("auto", "f1")
        self.assertEqual(auto["language_hints"], ["en", "ja"])
        self.assertTrue(auto["enable_language_identification"])
        fixed = soniox_asr.transcription_config("ja", "f1")
        self.assertEqual(fixed["language_hints"], ["ja"])
        self.assertNotIn("enable_language_identification", fixed)
        self.assertTrue(fixed["enable_speaker_diarization"])


class Reply:
    def __init__(self, status, body=None):
        self.status_code = status
        self.ok = 200 <= status < 300
        self.body = body or {}
        self.content = b"x"
        self.text = str(self.body)

    def json(self):
        return self.body


class FakeSession:
    def __init__(self, replies):
        self.replies = list(replies)
        self.headers = {}
        self.calls = []
        self.deleted = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url))
        return self.replies.pop(0)

    def delete(self, url, **kwargs):
        self.deleted.append(url)

    def close(self):
        pass


class SonioxTransportTests(unittest.TestCase):
    def run_transcribe(self, session):
        config = {"whisper.language": "en", "language_split_without_space": ["ja"]}
        with patch.object(soniox_asr.requests, "Session", return_value=session), patch.object(
            soniox_asr, "audio_slice_wav", return_value=b"wav"
        ), patch.object(soniox_asr, "load_key", side_effect=config.__getitem__), patch.object(
            soniox_asr, "load_key_or", side_effect=lambda key, default: config.get(key, default)
        ), patch.object(soniox_asr.time, "sleep"), patch.dict(
            soniox_asr.os.environ, {"SONIOX_API_KEY": "secret"}
        ):
            return soniox_asr.transcribe_audio_soniox("raw.mp3", "vocal.mp3", 10, 20)

    def test_success_retries_transient_errors_and_cleans_up(self):
        session = FakeSession([
            Reply(429), Reply(200, {"id": "file1"}),
            Reply(200, {"id": "tr1"}),
            Reply(200, {"status": "processing"}), Reply(503), Reply(200, {"status": "completed"}),
            Reply(200, {"tokens": [token("Hi", 0, 100)]}),
        ])
        result = self.run_transcribe(session)
        self.assertEqual(session.headers["Authorization"], "Bearer secret")
        self.assertEqual(result["segments"][0]["words"][0]["start"], 10.0)
        self.assertEqual(session.deleted, [f"{soniox_asr.API_BASE}/transcriptions/tr1",
                                           f"{soniox_asr.API_BASE}/files/file1"])

    def test_failed_transcription_still_deletes_remote_resources(self):
        session = FakeSession([
            Reply(200, {"id": "file1"}), Reply(200, {"id": "tr1"}),
            Reply(200, {"status": "error", "error_message": "bad audio"}),
        ])
        with self.assertRaisesRegex(RuntimeError, "bad audio"):
            self.run_transcribe(session)
        self.assertEqual(len(session.deleted), 2)

    def test_missing_key_is_rejected(self):
        with patch.dict(soniox_asr.os.environ, {"SONIOX_API_KEY": ""}), patch.object(
            soniox_asr, "load_key_or", return_value=""
        ):
            with self.assertRaisesRegex(ValueError, "SONIOX_API_KEY"):
                soniox_asr.configured_api_key()


class SonioxRuntimeHookTests(unittest.TestCase):
    def load_key(self, key):
        if key == "whisper":
            return {"runtime": "soniox", "language": "en", "model": "large-v3"}
        return "soniox"

    def test_soniox_runtime_reaches_media_discovery(self):
        from core import _2_asr as asr
        with patch.object(asr, "load_key", side_effect=self.load_key), patch.object(
            asr, "find_media_file", side_effect=FileNotFoundError("synthetic missing input")
        ), patch.object(soniox_asr, "configured_api_key", return_value="key"):
            with self.assertRaisesRegex(FileNotFoundError, "synthetic missing input"):
                asr.transcribe.__wrapped__()

    def test_missing_key_fails_before_media_preparation(self):
        from core import _2_asr as asr
        with patch.object(asr, "load_key", side_effect=self.load_key), patch.object(
            asr, "find_media_file"
        ) as find, patch.dict(soniox_asr.os.environ, {"SONIOX_API_KEY": ""}), patch.object(
            soniox_asr, "load_key_or", return_value=""
        ):
            with self.assertRaisesRegex(ValueError, "SONIOX_API_KEY"):
                asr.transcribe.__wrapped__()
        find.assert_not_called()


if __name__ == "__main__":
    unittest.main()
