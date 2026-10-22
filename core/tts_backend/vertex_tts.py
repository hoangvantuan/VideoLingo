"""Vertex AI dubbing backend: Cloud Text-to-Speech over REST (custom fork, see CUSTOM.md)."""

import base64
from pathlib import Path

import requests

from core.utils import check_cancel, load_key_or
from core.utils import google_credentials

SYNTHESIZE_URL = "https://texttospeech.googleapis.com/v1/text:synthesize"
LANGUAGE = "vi-VN"
VOICE = "vi-VN-Chirp3-HD-Aoede"
MIN_SPEED, MAX_SPEED = 0.25, 2.0  # speakingRate range of Cloud TTS


def request_payload(text):
    speed = float(load_key_or("vertex_tts.speed", 1.0) or 1.0)
    return {
        "input": {"text": text},
        "voice": {"languageCode": load_key_or("vertex_tts.language", LANGUAGE) or LANGUAGE,
                  "name": load_key_or("vertex_tts.voice", VOICE) or VOICE},
        "audioConfig": {"audioEncoding": "LINEAR16", "speakingRate": min(MAX_SPEED, max(MIN_SPEED, speed))},
    }


def _error_message(response):
    try:
        message = response.json().get("error", {}).get("message")
    except ValueError:
        message = None
    message = message or response.text[:300]
    if response.status_code in (401, 403):
        message += f"; check the service account and its roles, {google_credentials.SETUP_HINT}"
    return f"Cloud TTS request failed: HTTP {response.status_code} {message}"


def request_headers():
    """Bearer token plus the quota project billed for Cloud TTS calls."""
    return {**google_credentials.auth_headers(), "x-goog-user-project": google_credentials.project()}


def vertex_tts(text, save_path):
    """Synthesize `text` to a WAV file; errors are raised for the retry loop of tts_main."""
    check_cancel()
    response = requests.post(SYNTHESIZE_URL, headers=request_headers(), json=request_payload(text), timeout=120)
    if not response.ok:
        raise RuntimeError(_error_message(response))
    save_path = Path(save_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    save_path.write_bytes(base64.b64decode(response.json()["audioContent"]))  # LINEAR16 comes with a WAV header
    print(f"Audio saved to {save_path}")


if __name__ == "__main__":
    vertex_tts("Xin chào! Chào mừng bạn đến với VideoLingo.", "test.wav")
