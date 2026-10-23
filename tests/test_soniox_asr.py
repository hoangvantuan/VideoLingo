"""Contracts at the Soniox transport and response boundary (custom fork)."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from soniox.errors import SonioxInvalidRequestError, SonioxRateLimitError, SonioxServerError
from soniox.types import TranscriptionTranscript

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
        auto = soniox_asr.transcription_config("auto")
        self.assertEqual(auto.language_hints, ["en", "ja"])
        self.assertTrue(auto.enable_language_identification)
        fixed = soniox_asr.transcription_config("ja")
        self.assertEqual(fixed.language_hints, ["ja"])
        self.assertIsNone(fixed.enable_language_identification)
        self.assertTrue(fixed.enable_speaker_diarization)


def api_error(error_class, status):
    response = httpx.Response(status, request=httpx.Request("GET", "https://api.soniox.com/v1"))
    return error_class(f"HTTP {status}", response=response)


class FakeClient:
    """Stands in for soniox.SonioxClient; each API call takes the next scripted reply."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []
        self.deleted = []
        self.closed = False
        self.files = SimpleNamespace(upload=self.call("upload"),
                                     delete_if_exists=lambda file_id: self.deleted.append(("file", file_id)))
        self.stt = SimpleNamespace(create=self.call("create"), get=self.call("get"),
                                   get_transcript=self.call("get_transcript"),
                                   delete_if_exists=lambda tr_id: self.deleted.append(("transcription", tr_id)))

    def call(self, name):
        def reply(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            item = self.replies.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        return reply

    def close(self):
        self.closed = True


def transcription(status, error_message=None):
    return SimpleNamespace(id="tr1", status=status, error_message=error_message)


def transcript(*tokens):
    return TranscriptionTranscript(id="tr1", text="", tokens=list(tokens))


class SonioxTransportTests(unittest.TestCase):
    def run_transcribe(self, client, language="en"):
        config = {"whisper.language": language, "language_split_without_space": ["ja"]}
        with patch.object(soniox_asr, "SonioxClient", return_value=client) as make_client, patch.object(
            soniox_asr, "audio_slice_wav", return_value=b"wav"
        ), patch.object(soniox_asr, "load_key", side_effect=config.__getitem__), patch.object(
            soniox_asr, "load_key_or", side_effect=lambda key, default: config.get(key, default)
        ), patch.object(soniox_asr.time, "sleep"), patch.dict(
            soniox_asr.os.environ, {"SONIOX_API_KEY": "secret"}
        ):
            result = soniox_asr.transcribe_audio_soniox("raw.mp3", "vocal.mp3", 10, 20)
        self.assertEqual(make_client.call_args.kwargs["api_key"], "secret")
        return result

    def test_success_retries_transient_errors_and_cleans_up(self):
        client = FakeClient([
            api_error(SonioxRateLimitError, 429), SimpleNamespace(id="file1"),
            httpx.ConnectError("offline"), SimpleNamespace(id="tr1"),
            transcription("processing"), api_error(SonioxServerError, 503), transcription("completed"),
            transcript(token("Hi", 0, 100)),
        ])
        result = self.run_transcribe(client)
        self.assertEqual(result["segments"][0]["words"][0]["start"], 10.0)
        [upload] = [c for c in client.calls if c[0] == "upload"][-1:]
        self.assertEqual(upload[1], (b"wav",))
        [create] = [c for c in client.calls if c[0] == "create"][-1:]
        self.assertEqual(create[2]["model"], soniox_asr.MODEL)
        self.assertEqual(create[2]["file_id"], "file1")
        self.assertEqual(create[2]["config"].language_hints, ["en"])
        self.assertTrue(create[2]["config"].enable_speaker_diarization)
        self.assertEqual(client.deleted, [("transcription", "tr1"), ("file", "file1")])
        self.assertTrue(client.closed)

    def test_failed_transcription_still_deletes_remote_resources(self):
        client = FakeClient([
            SimpleNamespace(id="file1"), SimpleNamespace(id="tr1"),
            transcription("error", "bad audio"),
        ])
        with self.assertRaisesRegex(RuntimeError, "bad audio"):
            self.run_transcribe(client)
        self.assertEqual(client.deleted, [("transcription", "tr1"), ("file", "file1")])
        self.assertTrue(client.closed)

    def test_client_error_is_not_retried(self):
        client = FakeClient([api_error(SonioxInvalidRequestError, 400)])
        with self.assertRaisesRegex(RuntimeError, "HTTP 400"):
            self.run_transcribe(client)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.deleted, [])

    def test_cancel_while_polling_stops_and_cleans_up(self):
        client = FakeClient([SimpleNamespace(id="file1"), SimpleNamespace(id="tr1"),
                             transcription("processing")])

        def check_cancel():
            # The user cancels once Soniox reports the job is still processing.
            if any(name == "get" for name, *_ in client.calls):
                raise KeyboardInterrupt("cancelled")
        with patch.object(soniox_asr, "check_cancel", side_effect=check_cancel), \
                self.assertRaises(KeyboardInterrupt):
            self.run_transcribe(client)
        self.assertEqual(client.deleted, [("transcription", "tr1"), ("file", "file1")])

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
