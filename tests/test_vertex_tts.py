"""Contracts of the Vertex (Cloud Text-to-Speech) dubbing backend (custom fork, F9)."""

import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.tts_backend import vertex_tts
from core.utils.google_credentials import GoogleCredentialError


class Reply:
    def __init__(self, status, body=None):
        self.status_code = status
        self.ok = 200 <= status < 300
        self.body = body or {}
        self.text = str(self.body)

    def json(self):
        return self.body


def config(values):
    return lambda key, default=None: values.get(key, default)


class VertexTtsTests(unittest.TestCase):
    def setUp(self):
        for target, value in (("auth_headers", {"Authorization": "Bearer tok"}), ("project", "videolingo-512414")):
            patcher = patch.object(vertex_tts.google_credentials, target, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_payload_uses_configured_voice_language_and_clamped_speed(self):
        values = {"vertex_tts.voice": "vi-VN-Chirp3-HD-Charon", "vertex_tts.language": "vi-VN", "vertex_tts.speed": 3}
        with patch.object(vertex_tts, "load_key_or", side_effect=config(values)):
            payload = vertex_tts.request_payload("Xin chào")
        self.assertEqual(payload, {
            "input": {"text": "Xin chào"},
            "voice": {"languageCode": "vi-VN", "name": "vi-VN-Chirp3-HD-Charon"},
            "audioConfig": {"audioEncoding": "LINEAR16", "speakingRate": 2.0},
        })
        with patch.object(vertex_tts, "load_key_or", side_effect=config({"vertex_tts.speed": 0.1})):
            self.assertEqual(vertex_tts.request_payload("x")["audioConfig"]["speakingRate"], 0.25)

    def test_empty_config_uses_a_vietnamese_chirp3_hd_voice(self):
        with patch.object(vertex_tts, "load_key_or", side_effect=config({"vertex_tts.voice": ""})):
            payload = vertex_tts.request_payload("x")
        self.assertEqual(payload["voice"], {"languageCode": "vi-VN", "name": "vi-VN-Chirp3-HD-Aoede"})
        self.assertEqual(payload["audioConfig"]["speakingRate"], 1.0)

    def test_audio_is_decoded_and_written_billed_to_the_configured_project(self):
        wav = b"RIFF\x24\x00\x00\x00WAVEfmt "
        reply = Reply(200, {"audioContent": base64.b64encode(wav).decode()})
        with tempfile.TemporaryDirectory() as folder, patch.object(
            vertex_tts, "load_key_or", side_effect=config({})
        ), patch.object(vertex_tts.requests, "post", return_value=reply) as post:
            target = Path(folder) / "sub" / "1.wav"
            vertex_tts.vertex_tts("Xin chào", target)
            self.assertEqual(target.read_bytes(), wav)
        self.assertEqual(post.call_args.args[0], "https://texttospeech.googleapis.com/v1/text:synthesize")
        self.assertEqual(post.call_args.kwargs["headers"],
                         {"Authorization": "Bearer tok", "x-goog-user-project": "videolingo-512414"})
        self.assertEqual(post.call_args.kwargs["json"]["input"], {"text": "Xin chào"})

    def test_api_error_is_reported_once_for_the_dispatcher_to_retry(self):
        body = {"error": {"code": 429, "message": "Quota exceeded for Chirp3RequestsPerMinutePerProject",
                          "status": "RESOURCE_EXHAUSTED"}}
        with patch.object(vertex_tts, "load_key_or", side_effect=config({})), patch.object(
            vertex_tts.requests, "post", return_value=Reply(429, body)
        ) as post, self.assertRaisesRegex(RuntimeError, "HTTP 429.*Quota exceeded"):
            vertex_tts.vertex_tts("x", "unused.wav")
        self.assertEqual(post.call_count, 1)

    def test_permission_error_points_to_the_setup_section(self):
        body = {"error": {"code": 403, "message": "Permission denied", "status": "PERMISSION_DENIED"}}
        with patch.object(vertex_tts, "load_key_or", side_effect=config({})), patch.object(
            vertex_tts.requests, "post", return_value=Reply(403, body)
        ), self.assertRaisesRegex(RuntimeError, "HTTP 403.*Setup Google Cloud"):
            vertex_tts.vertex_tts("x", "unused.wav")

    def test_missing_credential_fails_before_any_request(self):
        def missing():
            raise GoogleCredentialError('No Google credential; see "Setup Google Cloud" in CUSTOM.md')

        with patch.object(vertex_tts.google_credentials, "auth_headers", side_effect=missing), patch.object(
            vertex_tts, "load_key_or", side_effect=config({})
        ), patch.object(vertex_tts.requests, "post") as post, self.assertRaisesRegex(
            GoogleCredentialError, "Setup Google Cloud"
        ):
            vertex_tts.vertex_tts("x", "unused.wav")
        post.assert_not_called()

    def test_dispatcher_routes_vertex_tts(self):
        from core.tts_backend import tts_main
        with tempfile.TemporaryDirectory() as folder, patch.object(
            tts_main, "load_key", return_value="vertex_tts"
        ), patch.object(tts_main, "vertex_tts") as backend, patch.object(tts_main, "get_audio_duration", return_value=1.0):
            target = str(Path(folder) / "1.wav")
            tts_main.tts_main("Xin chào các bạn", target, 1, None)
        backend.assert_called_once_with("Xin chào các bạn", target)


if __name__ == "__main__":
    unittest.main()
