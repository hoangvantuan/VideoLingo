"""Soniox async speech-to-text backend (custom fork, see CUSTOM.md)."""

import os
import time

import requests
from rich import print as rprint

from core.asr_backend.audio_preprocess import audio_slice_wav
from core.utils import check_cancel, load_key, load_key_or

API_BASE = "https://api.soniox.com/v1"
MODEL = "stt-async-v5"
AUTO_HINTS = ["en", "ja"]
ATTEMPTS = 4
RETRY_STATUS = {408, 429}
POLL_INTERVAL = 2
POLL_TIMEOUT = 900
SPLIT_GAP = 1


def configured_api_key():
    """SONIOX_API_KEY from the environment wins over whisper.soniox_api_key."""
    api_key = (os.environ.get("SONIOX_API_KEY") or "").strip()
    if not api_key:
        api_key = str(load_key_or("whisper.soniox_api_key", "") or "").strip()
    if not api_key or api_key.lower().startswith(("your_", "your ")):
        raise ValueError("Set SONIOX_API_KEY (or whisper.soniox_api_key) before using the Soniox runtime")
    return api_key


def transcription_config(language, file_id):
    config = {"model": MODEL, "file_id": file_id, "enable_speaker_diarization": True}
    if language and language != "auto":
        config["language_hints"] = [language]
    else:
        config["language_hints"] = AUTO_HINTS
        config["enable_language_identification"] = True
    return config


def _request(session, method, path, **kwargs):
    """Call the Soniox API, retrying connection errors, 408/429 and 5xx."""
    for attempt in range(1, ATTEMPTS + 1):
        check_cancel()
        try:
            response = session.request(method, f"{API_BASE}{path}", timeout=120, **kwargs)
        except (requests.ConnectionError, requests.Timeout) as error:
            if attempt == ATTEMPTS:
                raise
            rprint(f"[yellow]Soniox connection failed ({error}); retrying {attempt}/{ATTEMPTS - 1}[/yellow]")
        else:
            retryable = response.status_code in RETRY_STATUS or 500 <= response.status_code < 600
            if response.ok or not retryable or attempt == ATTEMPTS:
                break
            rprint(f"[yellow]Soniox HTTP {response.status_code}; retrying {attempt}/{ATTEMPTS - 1}[/yellow]")
        time.sleep(3 * attempt)
    if not response.ok:
        raise RuntimeError(f"Soniox {method} {path} failed: HTTP {response.status_code} {response.text[:500]}")
    return response.json() if response.content else {}


def _wait_until_completed(session, transcription_id):
    deadline = time.time() + POLL_TIMEOUT
    while True:
        status = _request(session, "GET", f"/transcriptions/{transcription_id}")
        if status.get("status") == "completed":
            return
        if status.get("status") == "error":
            raise RuntimeError(f"Soniox transcription failed: {status.get('error_message', 'unknown error')}")
        if time.time() > deadline:
            raise TimeoutError(f"Soniox transcription did not finish within {POLL_TIMEOUT} seconds")
        time.sleep(POLL_INTERVAL)


def _delete(session, path):
    try:
        session.delete(f"{API_BASE}{path}", timeout=30)
    except requests.RequestException as error:
        rprint(f"[yellow]Could not delete Soniox resource {path}: {error}[/yellow]")


def tokens_to_words(tokens, language, no_space_languages, offset=0.0):
    """Group Soniox sub-word tokens into words.

    Spaced languages open a new word on a token that starts with a space;
    languages written without spaces (ja, zh...) keep every token as a unit.
    """
    words = []
    for token in tokens:
        text = token.get("text", "")
        if token.get("translation_status") == "translation" or not text or text == "<end>":
            continue
        start = offset + token["start_ms"] / 1000
        end = offset + token["end_ms"] / 1000
        token_language = token.get("language") or language
        unit = token_language in no_space_languages
        if words and not unit and not text[0].isspace() and not words[-1]["unit"]:
            words[-1]["word"] += text
            words[-1]["end"] = end
            continue
        if not text.strip():
            continue
        words.append({"word": text.strip(), "start": start, "end": end,
                      "speaker": token.get("speaker"), "language": token_language, "unit": unit})
    return words


def words_to_segments(words):
    """Break segments on a silence over SPLIT_GAP seconds or a speaker change."""
    segments = []
    for word in words:
        seg = segments[-1] if segments else None
        if (seg is None or word["start"] - seg["end"] > SPLIT_GAP
                or word["speaker"] != seg["speaker_id"]):
            seg = {"text": "", "start": word["start"], "end": word["end"],
                   "speaker_id": word["speaker"], "words": []}
            segments.append(seg)
        if seg["text"] and not (word["unit"] and seg["words"][-1]["unit"]):
            seg["text"] += " "
        seg["text"] += word["word"]
        seg["end"] = word["end"]
        seg["words"].append({"word": word["word"], "start": word["start"], "end": word["end"],
                             "unit": word["unit"]})
    for seg in segments:
        for word in seg["words"]:
            word.pop("unit")
    return segments


def soniox2whisper(transcript, language, no_space_languages, offset=0.0):
    tokens = transcript.get("tokens") or []
    counts = {}
    for token in tokens:
        if token.get("language") and token.get("translation_status") != "translation":
            counts[token["language"]] = counts.get(token["language"], 0) + 1
    if language == "auto":
        language = max(counts, key=counts.get) if counts else None
    words = tokens_to_words(tokens, language, set(no_space_languages), offset)
    return {"segments": words_to_segments(words), "language": language}


def transcribe_audio_soniox(raw_audio_path, vocal_audio_path, start=None, end=None):
    rprint(f"[cyan]🎤 Transcribing with Soniox {MODEL}: {vocal_audio_path}[/cyan]")
    api_key = configured_api_key()
    language = load_key("whisper.language")
    no_space_languages = load_key_or("language_split_without_space", []) or []
    started = time.time()
    audio = audio_slice_wav(vocal_audio_path, start, end)

    session = requests.Session()
    session.headers["Authorization"] = f"Bearer {api_key}"
    file_id = transcription_id = None
    try:
        file_id = _request(session, "POST", "/files",
                           files={"file": ("audio.wav", audio, "audio/wav")})["id"]
        transcription_id = _request(session, "POST", "/transcriptions",
                                    json=transcription_config(language, file_id))["id"]
        _wait_until_completed(session, transcription_id)
        transcript = _request(session, "GET", f"/transcriptions/{transcription_id}/transcript")
    finally:
        # Never leave audio or transcripts behind on Soniox, even on failure.
        if transcription_id:
            _delete(session, f"/transcriptions/{transcription_id}")
        if file_id:
            _delete(session, f"/files/{file_id}")
        session.close()

    parsed = soniox2whisper(transcript, language, no_space_languages, start or 0.0)
    rprint(f"[green]✓ Soniox transcription completed in {time.time() - started:.2f} seconds[/green]")
    return parsed
