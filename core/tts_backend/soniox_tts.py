"""Soniox text-to-speech backend (custom fork, see CUSTOM.md)."""

import os
import struct
import time
from pathlib import Path

import requests

from core.utils import check_cancel, load_key_or, rprint

TTS_URL = "https://tts-rt.soniox.com/tts"
VOICES_URL = "https://api.soniox.com/v1/shared-voices"
CLONED_VOICES_URL = "https://api.soniox.com/v1/voices"
CLONED = "cloned"  # accent group of the voices cloned in this Soniox project
MODEL = "tts-rt-v2"
LANGUAGE = "vi"
VOICE = "Linh"  # young Vietnamese female
ATTEMPTS = 4
RETRY_STATUS = {408, 429}


def configured_api_key():
    """SONIOX_API_KEY, then soniox_tts.api_key, then the Soniox ASR key: one account serves both."""
    for value in (os.environ.get("SONIOX_API_KEY"),
                  load_key_or("soniox_tts.api_key", ""),
                  load_key_or("whisper.soniox_api_key", "")):
        value = str(value or "").strip()
        if value and not value.lower().startswith(("your_", "your ")):
            return value
    raise ValueError("Set the Soniox API key in the dubbing settings (or SONIOX_API_KEY) before using Soniox TTS")


def _pages(url, api_key, params):
    items, cursor = [], None
    while True:
        response = requests.get(url, headers={"Authorization": f"Bearer {api_key}"},
                                params={**params, **({"cursor": cursor} if cursor else {})}, timeout=15)
        if not response.ok:
            raise RuntimeError(f"Soniox voices request failed: HTTP {response.status_code} {response.text[:200]}")
        body = response.json()
        items.extend(body.get("voices") or [])
        cursor = body.get("next_page_cursor")
        if not cursor:
            return items


def list_cloned_voices(api_key, model=MODEL):
    """Voices cloned in this project that are ready for `model`; the voice field takes their ID."""
    voices = []
    for voice in _pages(CLONED_VOICES_URL, api_key, {}):
        if any(item.get("model") == model and item.get("status") == "ready" for item in voice.get("models") or []):
            voices.append({"id": voice["id"], "name": voice.get("name") or voice["id"],
                           "accent": CLONED, "description": "your cloned voice"})
    return voices


def list_voices(api_key, model=MODEL):
    """Cloned voices first, then the built-in ones: [{"id", "gender", "age", "accent", "description"...}]."""
    return list_cloned_voices(api_key, model) + _pages(VOICES_URL, api_key, {"model": model, "limit": 200})


def request_payload(text):
    payload = {
        "model": load_key_or("soniox_tts.model", MODEL) or MODEL,
        "language": load_key_or("soniox_tts.language", LANGUAGE) or LANGUAGE,
        "voice": load_key_or("soniox_tts.voice", VOICE) or VOICE,
        "audio_format": "wav",
        "text": text,
    }
    speed = float(load_key_or("soniox_tts.speed", 1.0) or 1.0)
    if speed != 1.0:
        payload["speed"] = min(1.3, max(0.7, speed))
    return payload


def fix_wav_sizes(audio):
    """Soniox streams WAV with 0xFFFFFFFF RIFF/data sizes; write the real ones."""
    data = audio.find(b"data", 12)
    if audio[:4] != b"RIFF" or data < 0:
        return audio
    audio = bytearray(audio)
    audio[4:8] = struct.pack("<I", len(audio) - 8)
    audio[data + 4:data + 8] = struct.pack("<I", len(audio) - data - 8)
    return bytes(audio)


def soniox_tts(text, save_path):
    api_key = configured_api_key()
    payload = request_payload(text)
    for attempt in range(1, ATTEMPTS + 1):
        check_cancel()
        try:
            response = requests.post(TTS_URL, headers={"Authorization": f"Bearer {api_key}"},
                                     json=payload, timeout=120)
        except (requests.ConnectionError, requests.Timeout) as error:
            if attempt == ATTEMPTS:
                raise
            rprint(f"[yellow]Soniox TTS connection failed ({error}); retrying {attempt}/{ATTEMPTS - 1}[/yellow]")
        else:
            retryable = response.status_code in RETRY_STATUS or 500 <= response.status_code < 600
            if response.ok or not retryable or attempt == ATTEMPTS:
                break
            rprint(f"[yellow]Soniox TTS HTTP {response.status_code}; retrying {attempt}/{ATTEMPTS - 1}[/yellow]")
        time.sleep(2 * attempt)
    if not response.ok:
        raise RuntimeError(f"Soniox TTS request failed: HTTP {response.status_code} {response.text[:300]}")
    save_path = Path(save_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    save_path.write_bytes(fix_wav_sizes(response.content))
    print(f"Audio saved to {save_path}")


if __name__ == "__main__":
    soniox_tts("Xin chào! Chào mừng bạn đến với VideoLingo.", "test.wav")
