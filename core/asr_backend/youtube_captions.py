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
        for j, (piece_start, text) in enumerate(pieces):
            piece_end = max(pieces[j + 1][0] if j + 1 < len(pieces) else end, piece_start)
            parts = text.split()
            total = sum(_letters(p) for p in parts)
            done = 0
            for part in parts:
                word_start = piece_start + (piece_end - piece_start) * done / total
                done += _letters(part)
                words.append({"word": part, "start": round(word_start / 1000, 3),
                              "end": round((piece_start + (piece_end - piece_start) * done / total) / 1000, 3)})
        segments.append({"start": round(start / 1000, 3), "end": round(end / 1000, 3),
                         "text": " ".join(w["word"] for w in words), "words": words})
    return {"segments": segments}


def read_captions(path):
    with open(path, encoding="utf-8") as f:
        return json3_to_result(json.load(f))
