"""Soniox text-to-speech backend on the official soniox SDK (custom fork, see CUSTOM.md)."""

import os
import struct
import time
from pathlib import Path

import httpx
from soniox import SonioxClient
from soniox.errors import SonioxAPIError
from soniox.types import CreateTtsConfig

from core.utils import check_cancel, load_key_or, rprint

CLONED = "cloned"  # accent group of the voices cloned in this Soniox project
MODEL = "tts-rt-v2"
LANGUAGE = "vi"
VOICE = "Linh"  # young Vietnamese female
ATTEMPTS = 4
RETRY_STATUS = {408, 429}
TIMEOUT = 120


def configured_api_key():
    """SONIOX_API_KEY, then soniox_tts.api_key, then the Soniox ASR key: one account serves both."""
    for value in (os.environ.get("SONIOX_API_KEY"),
                  load_key_or("soniox_tts.api_key", ""),
                  load_key_or("whisper.soniox_api_key", "")):
        value = str(value or "").strip()
        if value and not value.lower().startswith(("your_", "your ")):
            return value
    raise ValueError("Set the Soniox API key in the dubbing settings (or SONIOX_API_KEY) before using Soniox TTS")


def list_cloned_voices(api_key, model=MODEL):
    """Voices cloned in this project that are ready for `model`; the voice field takes their ID."""
    client = SonioxClient(api_key=api_key, timeout_sec=15)
    try:
        return [{"id": voice.id, "name": voice.name or voice.id, "accent": CLONED,
                 "description": "your cloned voice"}
                for voice in client.voices.list_all()
                if any(item.model == model and item.status == "ready" for item in voice.models)]
    finally:
        client.close()


def list_voices(api_key, model=MODEL):
    """Cloned voices first, then the built-in ones: [{"id", "gender", "age", "accent", "description"...}]."""
    cloned = list_cloned_voices(api_key, model)
    client = SonioxClient(api_key=api_key, timeout_sec=15)
    try:
        return cloned + [voice.model_dump() for voice in client.voices.list_all_shared(model, limit=200)]
    finally:
        client.close()


def request_payload(text):
    """Keyword arguments of client.tts.generate()."""
    speed = float(load_key_or("soniox_tts.speed", 1.0) or 1.0)
    return {
        "model": load_key_or("soniox_tts.model", MODEL) or MODEL,
        "language": load_key_or("soniox_tts.language", LANGUAGE) or LANGUAGE,
        "voice": load_key_or("soniox_tts.voice", VOICE) or VOICE,
        "text": text,
        "config": CreateTtsConfig(audio_format="wav",
                                  speed=min(1.3, max(0.7, speed)) if speed != 1.0 else None),
    }


def fix_wav_sizes(audio):
    """Soniox streams WAV with 0xFFFFFFFF RIFF/data sizes; write the real ones."""
    data = audio.find(b"data", 12)
    if audio[:4] != b"RIFF" or data < 0:
        return audio
    audio = bytearray(audio)
    audio[4:8] = struct.pack("<I", len(audio) - 8)
    audio[data + 4:data + 8] = struct.pack("<I", len(audio) - data - 8)
    return bytes(audio)


def _generate(client, request):
    """client.tts.generate(), retrying connection errors, 408/429 and 5xx (the SDK does not retry)."""
    for attempt in range(1, ATTEMPTS + 1):
        check_cancel()
        try:
            return client.tts.generate(**request)
        except httpx.TransportError as error:
            if attempt == ATTEMPTS:
                raise
            rprint(f"[yellow]Soniox TTS connection failed ({error}); retrying {attempt}/{ATTEMPTS - 1}[/yellow]")
        except SonioxAPIError as error:
            status = error.status_code or 0
            if not (status in RETRY_STATUS or 500 <= status < 600) or attempt == ATTEMPTS:
                raise RuntimeError(f"Soniox TTS request failed: {error}") from error
            rprint(f"[yellow]Soniox TTS HTTP {status}; retrying {attempt}/{ATTEMPTS - 1}[/yellow]")
        time.sleep(2 * attempt)


def soniox_tts(text, save_path):
    api_key = configured_api_key()
    request = request_payload(text)
    client = SonioxClient(api_key=api_key, timeout_sec=TIMEOUT)
    try:
        audio = _generate(client, request)
    finally:
        client.close()
    save_path = Path(save_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    # The SDK returns the streamed bytes as is, so the WAV sizes still need fixing.
    save_path.write_bytes(fix_wav_sizes(audio))
    print(f"Audio saved to {save_path}")


if __name__ == "__main__":
    soniox_tts("Xin chào! Chào mừng bạn đến với VideoLingo.", "test.wav")
