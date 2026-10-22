"""Contracts of the Soniox TTS backend (custom fork)."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
from soniox.errors import SonioxInvalidRequestError, SonioxRateLimitError
from soniox.types import GetSharedVoicesResponse, GetVoicesResponse

from core.tts_backend import soniox_tts
from core.st_utils.tts_settings import KEY_PATHS, PROVIDERS


def api_error(error_class, status):
    response = httpx.Response(status, request=httpx.Request("POST", "https://tts-rt.soniox.com/tts"))
    return error_class(f"HTTP {status}", response=response)


def fake_client():
    """Stands in for soniox.SonioxClient."""
    return MagicMock(spec_set=["tts", "voices", "close"])


def config(values):
    return lambda key, default=None: values.get(key, default)


class SonioxTtsTests(unittest.TestCase):
    def test_payload_uses_configured_voice_language_and_clamped_speed(self):
        values = {"soniox_tts.voice": "Daniel", "soniox_tts.language": "vi", "soniox_tts.speed": 2}
        with patch.object(soniox_tts, "load_key_or", side_effect=config(values)):
            request = soniox_tts.request_payload("Xin chào")
        settings = request.pop("config")
        self.assertEqual(request, {"model": "tts-rt-v2", "language": "vi", "voice": "Daniel",
                                   "text": "Xin chào"})
        self.assertEqual((settings.audio_format, settings.speed), ("wav", 1.3))
        with patch.object(soniox_tts, "load_key_or", side_effect=config({})):
            self.assertIsNone(soniox_tts.request_payload("x")["config"].speed)

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

    def synthesize(self, client, target):
        with patch.object(soniox_tts, "configured_api_key", return_value="key"), patch.object(
            soniox_tts, "load_key_or", side_effect=config({})
        ), patch.object(soniox_tts, "SonioxClient", return_value=client) as make_client, patch.object(
            soniox_tts.time, "sleep"
        ):
            soniox_tts.soniox_tts("Xin chào", target)
        self.assertEqual(make_client.call_args.kwargs["api_key"], "key")

    def test_audio_is_written_after_retrying_a_rate_limit(self):
        client = fake_client()
        client.tts.generate.side_effect = [api_error(SonioxRateLimitError, 429),
                                           httpx.ReadTimeout("slow"), b"ID3mp3"]
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "sub" / "1.wav"
            self.synthesize(client, target)
            self.assertEqual(target.read_bytes(), b"ID3mp3")
        self.assertEqual(client.tts.generate.call_count, 3)
        kwargs = client.tts.generate.call_args.kwargs
        self.assertEqual((kwargs["text"], kwargs["voice"], kwargs["language"], kwargs["model"]),
                         ("Xin chào", "Linh", "vi", "tts-rt-v2"))
        client.close.assert_called_once()

    def test_streamed_wav_sizes_are_rewritten(self):
        import io, struct, wave
        pcm = b"\x01\x00" * 2400
        header = (b"RIFF" + struct.pack("<I", 0xFFFFFFFF) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 1, 24000, 48000, 2, 16)
                  + b"data" + struct.pack("<I", 0xFFFFFFFF))
        fixed = soniox_tts.fix_wav_sizes(header + pcm)
        with wave.open(io.BytesIO(fixed)) as audio:
            self.assertEqual(audio.getnframes(), 2400)
        self.assertEqual(soniox_tts.fix_wav_sizes(b"not wav"), b"not wav")

    def test_client_error_is_not_retried(self):
        client = fake_client()
        client.tts.generate.side_effect = api_error(SonioxInvalidRequestError, 400)
        with self.assertRaisesRegex(RuntimeError, "HTTP 400"):
            self.synthesize(client, "unused.wav")
        self.assertEqual(client.tts.generate.call_count, 1)
        client.close.assert_called_once()

    def test_ready_cloned_voices_come_first_then_paged_shared_voices(self):
        cloned = GetVoicesResponse.model_validate({"voices": [
            {"id": "uuid-1", "name": "Giọng BBook", "filename": "a.wav", "created_at": "2026-01-01T00:00:00Z",
             "models": [{"model": "tts-rt-v2", "status": "ready"}]},
            {"id": "uuid-2", "name": "Đang xử lý", "filename": "b.wav", "created_at": "2026-01-01T00:00:00Z",
             "models": [{"model": "tts-rt-v2", "status": "processing"}]},
        ], "next_page_cursor": None})
        linh = {"id": "Linh", "description": "young", "gender": "female", "age": "young",
                "accent": "vietnamese", "use_case": [], "style": []}
        shared = [GetSharedVoicesResponse.model_validate({"voices": [linh], "next_page_cursor": "c2"}),
                  GetSharedVoicesResponse.model_validate({"voices": [{**linh, "id": "Mai"}],
                                                          "next_page_cursor": None})]
        responses = {"/voices": [cloned], "/shared-voices": shared}
        requests = []

        def request(method, path, params=None, **kwargs):
            requests.append((path, params))
            return httpx.Response(200, json=responses[path].pop(0).model_dump(mode="json"),
                                  request=httpx.Request(method, "https://api.soniox.com/v1" + path))
        with patch.object(soniox_tts.SonioxClient, "request", side_effect=request, autospec=False):
            voices = soniox_tts.list_voices("key")
        self.assertEqual([v["id"] for v in voices], ["uuid-1", "Linh", "Mai"])
        self.assertEqual((voices[0]["name"], voices[0]["accent"]), ("Giọng BBook", soniox_tts.CLONED))
        self.assertEqual((voices[1]["gender"], voices[1]["accent"]), ("female", "vietnamese"))
        self.assertEqual(requests[1], ("/shared-voices", {"model": "tts-rt-v2", "limit": 200}))
        self.assertEqual(requests[2][1]["cursor"], "c2")

    def test_soniox_is_a_selectable_provider(self):
        self.assertEqual(PROVIDERS["Soniox"], ("soniox_tts",))
        self.assertEqual(KEY_PATHS["Soniox"], ("soniox_tts.api_key",))


if __name__ == "__main__":
    unittest.main()
