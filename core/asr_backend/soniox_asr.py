"""Soniox async speech-to-text backend on the official soniox SDK (custom fork, see CUSTOM.md)."""

import os
import time

import httpx
from rich import print as rprint
from soniox import SonioxClient
from soniox.errors import SonioxAPIError, SonioxError
from soniox.types import CreateTranscriptionConfig

from core.asr_backend.audio_preprocess import audio_slice_wav
from core.utils import check_cancel, load_key, load_key_or

MODEL = "stt-async-v5"
AUTO_HINTS = ["en", "ja"]
ATTEMPTS = 4
RETRY_STATUS = {408, 429}
POLL_INTERVAL = 2
POLL_TIMEOUT = 900
TIMEOUT = 120
SPLIT_GAP = 1


def configured_api_key():
    """SONIOX_API_KEY from the environment wins over whisper.soniox_api_key."""
    api_key = (os.environ.get("SONIOX_API_KEY") or "").strip()
    if not api_key:
        api_key = str(load_key_or("whisper.soniox_api_key", "") or "").strip()
    if not api_key or api_key.lower().startswith(("your_", "your ")):
        raise ValueError("Set SONIOX_API_KEY (or whisper.soniox_api_key) before using the Soniox runtime")
    return api_key


def transcription_config(language):
    config = CreateTranscriptionConfig(enable_speaker_diarization=True)
    if language and language != "auto":
        config.language_hints = [language]
    else:
        config.language_hints = AUTO_HINTS
        config.enable_language_identification = True
    return config


def _call(action, method, *args, **kwargs):
    """Call the SDK, retrying connection errors, 408/429 and 5xx (the SDK does not retry)."""
    for attempt in range(1, ATTEMPTS + 1):
        check_cancel()
        try:
            return method(*args, **kwargs)
        except httpx.TransportError as error:
            if attempt == ATTEMPTS:
                raise
            rprint(f"[yellow]Soniox connection failed ({error}); retrying {attempt}/{ATTEMPTS - 1}[/yellow]")
        except SonioxAPIError as error:
            status = error.status_code or 0
            if not (status in RETRY_STATUS or 500 <= status < 600) or attempt == ATTEMPTS:
                raise RuntimeError(f"Soniox {action} failed: {error}") from error
            rprint(f"[yellow]Soniox HTTP {status}; retrying {attempt}/{ATTEMPTS - 1}[/yellow]")
        time.sleep(3 * attempt)


def _wait_until_completed(client, transcription_id):
    # Own poll loop instead of client.stt.wait(): it sleeps without check_cancel().
    deadline = time.time() + POLL_TIMEOUT
    while True:
        status = _call("status", client.stt.get, transcription_id)
        if status.status == "completed":
            return
        if status.status == "error":
            raise RuntimeError(f"Soniox transcription failed: {status.error_message or 'unknown error'}")
        if time.time() > deadline:
            raise TimeoutError(f"Soniox transcription did not finish within {POLL_TIMEOUT} seconds")
        time.sleep(POLL_INTERVAL)


def _delete(delete, kind, resource_id):
    try:
        delete(resource_id)
    except (SonioxError, httpx.HTTPError) as error:
        rprint(f"[yellow]Could not delete Soniox {kind} {resource_id}: {error}[/yellow]")


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

    client = SonioxClient(api_key=api_key, timeout_sec=TIMEOUT)
    file_id = transcription_id = None
    try:
        file_id = _call("upload", client.files.upload, audio, filename="audio.wav").id
        transcription_id = _call("create", client.stt.create, model=MODEL, file_id=file_id,
                                 config=transcription_config(language)).id
        _wait_until_completed(client, transcription_id)
        transcript = _call("transcript", client.stt.get_transcript, transcription_id).model_dump()
    finally:
        # Never leave audio or transcripts behind on Soniox, even on failure.
        if transcription_id:
            _delete(client.stt.delete_if_exists, "transcription", transcription_id)
        if file_id:
            _delete(client.files.delete_if_exists, "file", file_id)
        client.close()

    parsed = soniox2whisper(transcript, language, no_space_languages, start or 0.0)
    rprint(f"[green]✓ Soniox transcription completed in {time.time() - started:.2f} seconds[/green]")
    return parsed
