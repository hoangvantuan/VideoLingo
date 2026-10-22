"""Contracts of the Soniox TTS backend (custom fork)."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.tts_backend import soniox_tts
from core.st_utils.tts_settings import KEY_PATHS, PROVIDERS


class Reply:
    def __init__(self, status, body=None, content=b""):
        self.status_code = status
        self.ok = 200 <= status < 300
        self.body = body or {}
        self.content = content
        self.text = str(self.body)

    def json(self):
        return self.body


def config(values):
    return lambda key, default=None: values.get(key, default)


class SonioxTtsTests(unittest.TestCase):
    def test_payload_uses_configured_voice_language_and_clamped_speed(self):
        values = {"soniox_tts.voice": "Daniel", "soniox_tts.language": "vi", "soniox_tts.speed": 2}
        with patch.object(soniox_tts, "load_key_or", side_effect=config(values)):
            payload = soniox_tts.request_payload("Xin chào")
        self.assertEqual(payload, {"model": "tts-rt-v2", "language": "vi", "voice": "Daniel",
                                   "audio_format": "wav", "text": "Xin chào", "speed": 1.3})
        with patch.object(soniox_tts, "load_key_or", side_effect=config({})):
            self.assertNotIn("speed", soniox_tts.request_payload("x"))

    def test_key_falls_back_to_the_asr_key(self):
        with patch.dict(soniox_tts.os.environ, {"SONIOX_API_KEY": ""}), patch.object(
            soniox_tts, "load_key_or",
            side_effect=config({"soniox_tts.api_key": "", "whisper.soniox_api_key": "asr-key"}),
        ):
            self.assertEqual(soniox_tts.configured_api_key(), "asr-key")
        with patch.dict(soniox_tts.os.environ, {"SONIOX_API_KEY": ""}), patch.object(
            soniox_tts, "load_key_or", side_effect=config({})
        ), self.assertRaises(ValueError):
            soniox_tts.configured_api_key()

    def test_audio_is_written_after_retrying_a_rate_limit(self):
        replies = [Reply(429), Reply(200, content=b"RIFFwav")]
        with tempfile.TemporaryDirectory() as folder, patch.object(
            soniox_tts, "configured_api_key", return_value="key"
        ), patch.object(soniox_tts, "load_key_or", side_effect=config({})), patch.object(
            soniox_tts.requests, "post", side_effect=replies
        ) as post, patch.object(soniox_tts.time, "sleep"):
            target = Path(folder) / "sub" / "1.wav"
            soniox_tts.soniox_tts("Xin chào", target)
            self.assertEqual(target.read_bytes(), b"RIFFwav")
        self.assertEqual(post.call_count, 2)
        self.assertEqual(post.call_args.kwargs["headers"], {"Authorization": "Bearer key"})
        self.assertEqual(post.call_args.args[0], soniox_tts.TTS_URL)

    def test_client_error_is_not_retried(self):
        with patch.object(soniox_tts, "configured_api_key", return_value="key"), patch.object(
            soniox_tts, "load_key_or", side_effect=config({})
        ), patch.object(soniox_tts.requests, "post", return_value=Reply(400, {"error": "bad voice"})) as post:
            with self.assertRaisesRegex(RuntimeError, "HTTP 400"):
                soniox_tts.soniox_tts("x", "unused.wav")
        self.assertEqual(post.call_count, 1)

    def test_voices_are_paged_for_the_selected_model(self):
        pages = [Reply(200, {"voices": [{"id": "Linh"}], "next_page_cursor": "c2"}),
                 Reply(200, {"voices": [{"id": "Mai"}], "next_page_cursor": None})]
        with patch.object(soniox_tts.requests, "get", side_effect=pages) as get:
            self.assertEqual([v["id"] for v in soniox_tts.list_voices("key")], ["Linh", "Mai"])
        self.assertEqual(get.call_args_list[0].kwargs["params"], {"model": "tts-rt-v2", "limit": 200})
        self.assertEqual(get.call_args_list[1].kwargs["params"]["cursor"], "c2")

    def test_soniox_is_a_selectable_provider(self):
        self.assertEqual(PROVIDERS["Soniox"], ("soniox_tts",))
        self.assertEqual(KEY_PATHS["Soniox"], ("soniox_tts.api_key",))


if __name__ == "__main__":
    unittest.main()
