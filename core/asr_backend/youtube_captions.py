"""Custom: the captions of a YouTube video take the place of the recognition (whisper.runtime "youtube").

Only a track in the language of the video is used, never one that YouTube translates: the track
made by the uploader in that language, else the automatic captions of the speech ("<lang>-orig").
A translated track has a ``tlang`` parameter in its URL.
"""
import json
import os
import re

CAPTIONS_FILE = "youtube_captions.json3"


def _json3_url(formats):
    for fmt in formats or []:
        url = fmt.get("url") or ""
        if fmt.get("ext") == "json3" and "tlang=" not in url:
            return url
    return None


def pick_track(info):
    """(language, kind, url) of the original captions of a video, or None. kind is "manual" or "auto"."""
    base = str(info.get("language") or "").split("-")[0].lower()
    manual = info.get("subtitles") or {}
    auto = info.get("automatic_captions") or {}
    if base:
        for lang, formats in manual.items():
            url = _json3_url(formats)
            if lang.split("-")[0].lower() == base and url:
                return base, "manual", url
        url = _json3_url(auto.get(f"{base}-orig"))
        if url:
            return base, "auto", url
    for lang, formats in auto.items():
        url = _json3_url(formats)
        if lang.endswith("-orig") and url:
            return lang[: -len("-orig")].split("-")[0].lower(), "auto", url
    return None


def save_captions(ydl, info, save_path="output"):
    """Download the original captions next to the video. Returns {"path", "language", "kind"} or None."""
    track = pick_track(info)
    if not track:
        return None
    language, kind, url = track
    data = json.loads(ydl.urlopen(url).read())
    path = os.path.join(save_path, CAPTIONS_FILE)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return {"path": path, "language": language, "kind": kind}


_SPEAKER_MARKER_RE = re.compile(r"(?:>>+|<<+|(?:&gt;){2,}|(?:&lt;){2,})")
_UNCERTAIN_CAPTION_RE = re.compile(r"\[\?\s*(.*?)\s*\?\]?", re.DOTALL)
_UNCERTAIN_FRAGMENT_RE = re.compile(r"\[\?\s*|\s*\?\]")
_CC_NON_SPEECH_RE = re.compile(
    r"\[\s*(?:"
    r"noise|inaudible|laughter|laughs|chuckles|snorts|applause|music|"
    r"clears\s+throat|background(?:\s+noise|\s+music)?|audio\s+out|blank[_ ]audio|"
    r"non-english\s+speech|video\s+playback|end\s+playback|gasps?|sighs?|"
    r"overlapping(?:\s+speech)?|(?:crowd\s+)?cheering|sound|coughs?|silence|"
    r"tiếng\s+ồn(?:\s+[^\]]*)?|không\s+nghe\s+rõ|không\s+rõ(?:\s+tiếng)?|"
    r"không\s+thể\s+nghe\s+rõ|(?:tiếng\s+)?cười(?:\s+[^\]]*)?|tiếng\s+nền|"
    r"âm\s+thanh\s+nền|mất\s+tiếng|mất\s+âm\s+thanh|hắng\s+giọng|(?:âm\s+)?nhạc|"
    r"(?:tiếng\s+)?vỗ\s+tay|tiếng\s+nước\s+ngoài|tiếng\s+động|video\s+phát\s+lại|"
    r"phát\s+video|hết\s+video|kết\s+thúc\s+video|hết\s+đoạn\s+phát|thở\s+dài|"
    r"thở\s+hắt\s+ra|hít\s+(?:một\s+hơi|sâu|vào)|(?:tiếng\s+)?reo\s+hò|"
    r"tiếng\s+(?:nói\s+)?(?:phía\s+sau|phía\s+dưới|dưới\s+lớp|ở\s+nền)|"
    r"nói\s+đè(?:\s+nhau)?|đoạn\s+bị\s+che/hỏng|chỗ\s+trống|(?:tiếng\s+)?ho|im\s+lặng"
    r")\s*\]",
    re.IGNORECASE,
)


def clean_caption_text(text: str) -> str:
    """Strip speaker-change markers (>>), non-speech CC tags ([laughter], [NOISE]), and unwrap [? word ?]."""
    if not text:
        return ""
    text = _UNCERTAIN_CAPTION_RE.sub(r"\1", text)
    text = _UNCERTAIN_FRAGMENT_RE.sub("", text)
    text = _SPEAKER_MARKER_RE.sub(" ", text)
    text = _CC_NON_SPEECH_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def _letters(text):
    return len(re.sub(r"[^\w]", "", text)) or 1


def json3_to_result(data):
    """The json3 captions as a recognition result: one segment for each caption, with timed words.

    Automatic captions time each word (tOffsetMs); a caption of the uploader is one piece of text,
    whose time is shared among its words by their length.
    """
    events = [e for e in data.get("events", []) if any((s.get("utf8") or "").strip() for s in e.get("segs") or [])]
    segments = []
    for i, event in enumerate(events):
        start = event.get("tStartMs", 0)
        end = start + event.get("dDurationMs", 0)
        if i + 1 < len(events) and start < events[i + 1].get("tStartMs", 0) < end:
            end = events[i + 1]["tStartMs"]  # automatic captions overlap the next one while it rolls in
        pieces = [(start + s.get("tOffsetMs", 0), s["utf8"]) for s in event["segs"] if (s.get("utf8") or "").strip()]
        words = []
        for j, (piece_start, raw_text) in enumerate(pieces):
            piece_end = max(pieces[j + 1][0] if j + 1 < len(pieces) else end, piece_start)
            text = clean_caption_text(raw_text)
            if not text:
                continue
            parts = text.split()
            total = sum(_letters(p) for p in parts)
            done = 0
            for part in parts:
                word_start = piece_start + (piece_end - piece_start) * done / total
                done += _letters(part)
                words.append({"word": part, "start": round(word_start / 1000, 3),
                              "end": round((piece_start + (piece_end - piece_start) * done / total) / 1000, 3)})
        if words:
            segments.append({"start": round(start / 1000, 3), "end": round(end / 1000, 3),
                             "text": " ".join(w["word"] for w in words), "words": words})
    return {"segments": segments}


def read_captions(path):
    with open(path, encoding="utf-8") as f:
        return json3_to_result(json.load(f))
