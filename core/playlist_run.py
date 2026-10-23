"""Lượt chạy playlist: process the selected videos of a Playlist one after another on output/.

Decision: docs/adr/0002-playlist-tuan-tu-tren-output-chung.md. Terms: GLOSSARY.md.

Public interface
----------------
- ``read_playlist(url, ytdlp=None) -> Playlist``: the Playlist of a playlist or channel URL,
  read by yt-dlp in flat mode (no download). Each ``PlaylistVideo`` has its video ID, index
  (1-based, in the order of the Playlist), title, duration in seconds (or None) and whether it
  is available (private, deleted and members-only videos are not). A video `Xong` in an earlier
  run of the same Playlist, matched by its video ID in the state file, has ``done`` set.
- ``PlaylistRun.create(playlist, selected_ids, scope, ytdlp=None, plan=None)``: a Lượt chạy
  playlist of the selected available videos. ``scope`` is ``SUBTITLES`` (subtitles only) or
  ``DUBBING`` (subtitles and dubbing). A video known to an earlier run keeps its history folder,
  and a video `Xong` that is not selected stays `Xong` in the state file.
- ``run.start()`` makes the run the one of the process (``current_run()``) and processes the
  videos in a background thread. It raises ``PlaylistRunError`` when ``output/`` is not empty,
  another run is active, or another run is unfinished. ``run.pause()``, ``run.resume()``,
  ``run.wait(timeout)``.
- ``run.stop()`` stops cooperatively: the unfinished work of the current video (with ``log/``
  and ``gpt_log/``) is moved into its history folder, the video is ``WAITING`` again and
  ``output/`` is empty. The run is then unfinished: ``run.start()`` continues it (Tiếp tục).
- ``load_unfinished(ytdlp=None, plan=None)``: the unfinished run of this process, or the one
  of a state file in ``history/`` (after the app was closed or crashed), or None. It does not
  run by itself. ``run.end()`` (Kết thúc lượt chạy) marks it finished and keeps history.
- ``run.snapshot() -> RunSnapshot``: state of the run, progress ``done/total``, the video being
  processed and its current step, the pause message, and for each video its Trạng thái video
  (``WAITING``, ``RUNNING``, ``DONE``, ``FAILED``, ``UNAVAILABLE``), history folder, and for a
  ``FAILED`` video the step that failed and a short error message.

For each video: download it into ``output/`` → run the steps of the pipeline → move all of
``output/`` (with ``log/`` and ``gpt_log/``) into ``history/<playlist>/<index> - <title>/``.
Folder names are cleaned as the history save does (``onekeycleanup.sanitize_filename``), the
index is not padded; a name already used by another video gets the video ID appended. The review checkpoints of the pipeline do not pause during a run.

A video that fails (download, a step of the pipeline or the save) is ``FAILED`` with its step
and error; its unfinished work, with ``log/`` and ``gpt_log/``, is moved into its history folder
without deleting what the folder holds, and the run goes on with the next video. When
``FAILURES_TO_PAUSE`` videos fail in a row the run pauses itself with ``FAILED_IN_A_ROW``: that is
most often a system error (quota, API key, network, cookies). A video done in between resets
the count.

The state file ``history/<playlist>/playlist_run.json`` holds the URL, title, scope, the run
state (``running``, ``interrupted`` once stopped, or ``finished``) and every video with its
status and folder. It is written after every change of a Trạng thái video. A ``running`` state
with no run alive in the process means the app was closed or crashed: the work of the video
that was ``RUNNING`` is still in ``output/`` and is moved into its history folder on loading.

The unfinished work of a stopped or crashed video (``partial`` in the state file) is moved
back from its history folder into ``output/`` when its turn comes, and the video is not
downloaded again; the pipeline skips the steps whose intermediate files exist. A video `Xong`
that is selected again starts anew.

Settings are read from config.yaml at each step, as in ADR-0002: a change in the sidebar
applies to the following steps and videos.

Adapters, replaced in tests: ``ytdlp`` (``extract_flat(url) -> dict``, ``download(url)`` into
``output/``) and ``plan`` (``plan(stage, dubbing) -> [(label, callable)]``, ``get_steps``).
"""
from __future__ import annotations

import json
import os
import threading
import traceback
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable

from core.task_runner import StopTask, TaskRunner
from core.utils.config_utils import load_key
from core.utils.history_folder import merge_output
from core.utils.onekeycleanup import cleanup, sanitize_filename

OUTPUT = Path("output")
HISTORY = Path("history")
STATE_FILE = "playlist_run.json"

# Scope of a run
SUBTITLES = "subtitles"
DUBBING = "dubbing"  # subtitles and dubbing

# Trạng thái video
WAITING = "waiting"
RUNNING = "running"
DONE = "done"
FAILED = "failed"
UNAVAILABLE = "unavailable"

# Steps of a video besides those of the pipeline. Labels and messages are translation keys.
DOWNLOAD_STEP = "Download video"
SAVE_STEP = "Save to 'history'"
OUTPUT_NOT_EMPTY = ("`output/` holds the files of another video. Archive them to 'history' "
                    "or delete them in the single video mode, then start the playlist.")
RUN_ACTIVE = "A playlist run is already active."
RUN_UNFINISHED = "A playlist run is unfinished. Continue it or end it first."

# State of a run in its state file
RUN_RUNNING = "running"
RUN_INTERRUPTED = "interrupted"
RUN_FINISHED = "finished"

FAILED_IN_A_ROW = ("2 videos failed in a row, so the playlist run paused. This is often a system error "
                   "(quota, API key, network or cookies): fix it, then resume.")
FAILURES_TO_PAUSE = 2
ERROR_LENGTH = 300  # characters of the error message kept for a failed video

# Private, deleted and members-only videos as yt-dlp lists them in flat mode
UNAVAILABLE_TITLES = {"[Private video]", "[Deleted video]"}
UNAVAILABLE_KINDS = {"private", "premium_only", "subscriber_only", "needs_auth"}


@dataclass(frozen=True)
class PlaylistVideo:
    video_id: str
    index: int
    title: str
    duration: float | None
    available: bool
    url: str
    done: bool = False  # `Xong` in an earlier run of this Playlist


@dataclass(frozen=True)
class Playlist:
    url: str
    title: str
    videos: tuple[PlaylistVideo, ...]


def youtube_options():
    """Proxy and cookies of config.yaml, with the meaning they have for the downloader."""
    options = {}
    youtube = load_key("youtube") or {}
    proxy = youtube.get("proxy")
    if proxy is not None:
        if not isinstance(proxy, str):
            raise ValueError('youtube.proxy must be null, an empty string, or a proxy URL')
        options["proxy"] = proxy.strip()
    cookies_path = str(youtube.get("cookies_path") or "").strip().strip('"')
    if cookies_path:
        if not os.path.isfile(cookies_path):
            raise ValueError(f"Cookies file not found: {cookies_path}")
        options["cookiefile"] = cookies_path
    return options


class Ytdlp:
    """yt-dlp: flat reading of a Playlist, and the existing downloader for one video."""

    def extract_flat(self, url):
        from yt_dlp import YoutubeDL
        options = {**youtube_options(), "extract_flat": "in_playlist", "skip_download": True, "quiet": True}
        with YoutubeDL(options) as ydl:
            return ydl.extract_info(url, download=False)

    def download(self, url):
        from core._1_ytdlp import download_video_ytdlp
        download_video_ytdlp(url, resolution=load_key("ytb_resolution"))


def _entries(info, ytdlp):
    """The video entries of a playlist; the tabs of a channel (Videos, Shorts, Live) are read too."""
    for item in info.get("entries") or []:
        if not item:
            continue
        if item.get("_type") == "playlist":
            yield from _entries(item, ytdlp)
        elif item.get("ie_key") == "YoutubeTab" and item.get("url"):
            yield from _entries(ytdlp.extract_flat(item["url"]), ytdlp)
        elif item.get("id"):
            yield item


def read_playlist(url, ytdlp=None) -> Playlist:
    ytdlp = ytdlp or Ytdlp()
    info = ytdlp.extract_flat(url)
    if not info or "entries" not in info:
        raise ValueError("This URL is not a playlist or a channel.")
    videos, seen = [], set()
    for item in _entries(info, ytdlp):
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        title = item.get("title") or item["id"]
        available = title not in UNAVAILABLE_TITLES and item.get("availability") not in UNAVAILABLE_KINDS
        videos.append(PlaylistVideo(
            video_id=item["id"], index=len(videos) + 1, title=title, duration=item.get("duration"),
            available=available,
            url=item.get("url") or item.get("webpage_url") or f"https://www.youtube.com/watch?v={item['id']}",
        ))
    title = info.get("title") or info.get("id") or "playlist"
    earlier = _earlier_videos(title)
    videos = [replace(v, done=earlier.get(v.video_id, {}).get("status") == DONE) for v in videos]
    return Playlist(url=url, title=title, videos=tuple(videos))


def _earlier_videos(title) -> dict:
    """The videos of the state file of an earlier run of the Playlist, by video ID; {} without one."""
    try:
        data = json.loads((HISTORY / sanitize_filename(title) / STATE_FILE).read_text(encoding="utf-8"))
        return {v["video_id"]: v for v in data["videos"]}
    except (OSError, ValueError, KeyError, TypeError):
        return {}


@dataclass(frozen=True)
class VideoSnapshot:
    video_id: str
    index: int
    title: str
    duration: float | None
    selected: bool
    status: str
    folder: str | None  # history folder, None for a video that is not processed
    url: str = ""
    failed_step: str = ""
    error: str = ""
    partial: bool = False  # its history folder holds unfinished work, moved back into output/ on its turn


@dataclass(frozen=True)
class RunSnapshot:
    state: str  # running | paused | stopping | stopped | completed | error, as TaskRunner
    url: str
    title: str
    scope: str
    done: int
    total: int
    current_video: VideoSnapshot | None
    current_step: str  # translation key of the step of the current video, "" between videos
    pause_message: str
    error: str
    videos: tuple[VideoSnapshot, ...]
    unfinished: bool = False  # not active and not finished: it can be continued or ended


class PlaylistRunError(Exception):
    """A run can not start; the message is a translation key."""


def _unattended_runner():
    """A TaskRunner whose steps do not wait for a review: ``core.pipeline`` reads ``unattended``.

    Not a subclass: ``TaskRunner._run`` sets ``type(self)._current``, which ``check_cancel()``
    and the review checkpoints read on ``TaskRunner`` itself.
    """
    runner = TaskRunner()
    runner.unattended = True
    return runner


@dataclass
class PlaylistRun:
    url: str
    title: str
    scope: str
    videos: list[VideoSnapshot]
    ytdlp: object = None
    plan: Callable | None = None
    current_step: str = ""
    run_state: str = ""  # state in the state file, "" before the run is started
    _runner: TaskRunner = field(default_factory=_unattended_runner)

    @classmethod
    def create(cls, playlist: Playlist, selected_ids, scope, ytdlp=None, plan=None) -> "PlaylistRun":
        if scope not in (SUBTITLES, DUBBING):
            raise ValueError(f"Unknown scope: {scope}")
        selected_ids = set(selected_ids)
        root = HISTORY / sanitize_filename(playlist.title)
        earlier = _earlier_videos(playlist.title)
        # Folders of other videos: of an earlier run, or on disk from a video that left the Playlist
        taken = {v.get("folder") for v in earlier.values()} | (
            {p.name for p in root.iterdir()} if root.is_dir() else set())
        videos = []
        for video in playlist.videos:
            selected = video.available and video.video_id in selected_ids
            done = video.available and earlier.get(video.video_id, {}).get("status") == DONE
            folder = earlier.get(video.video_id, {}).get("folder")
            if folder is None and selected:
                folder = sanitize_filename(f"{video.index} - {video.title}")
                if folder in taken:
                    folder = sanitize_filename(f"{video.index} - {video.title} [{video.video_id}]")
                taken.add(folder)
            status = UNAVAILABLE if not video.available else DONE if done and not selected else WAITING
            videos.append(VideoSnapshot(
                video_id=video.video_id, index=video.index, title=video.title, duration=video.duration,
                selected=selected, status=status, folder=folder if selected or done else None,
                url=video.url))
        return cls(url=playlist.url, title=playlist.title, scope=scope, videos=videos,
                   ytdlp=ytdlp or Ytdlp(), plan=plan)

    @classmethod
    def _load(cls, path: Path, ytdlp=None, plan=None) -> "PlaylistRun":
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("version") != 1:
            raise ValueError(f"Unknown version of {path}")
        run = cls(url=data["url"], title=data["title"], scope=data["scope"],
                  videos=[VideoSnapshot(**v) for v in data["videos"]], ytdlp=ytdlp or Ytdlp(), plan=plan,
                  run_state=data["state"])
        if run.run_state == RUN_RUNNING:  # closed or crashed: the work of the video is in output/
            for position, video in enumerate(run.videos):
                if video.status == RUNNING:
                    merge_output(run.folder / video.folder)
                    run.videos[position] = replace(video, status=WAITING, partial=True)
            run._save(RUN_INTERRUPTED)
        return run

    @property
    def folder(self) -> Path:
        """``history/<playlist>/``, which holds the state file and the folder of each video."""
        return HISTORY / sanitize_filename(self.title)

    # ------ Control ------

    def start(self):
        global _current
        with _lock:
            if _current is not None and _current is not self and _current._runner.is_active:
                raise PlaylistRunError(RUN_ACTIVE)
            if self._runner.is_active:
                raise PlaylistRunError(RUN_ACTIVE)
            unfinished = _unfinished_state_file()
            if unfinished is not None and not (self.run_state == RUN_INTERRUPTED
                                               and unfinished == self.folder / STATE_FILE):
                raise PlaylistRunError(RUN_UNFINISHED)
            if OUTPUT.exists() and any(OUTPUT.iterdir()):
                raise PlaylistRunError(OUTPUT_NOT_EMPTY)
            _current = self
            self._save(RUN_RUNNING)
            self._runner.start([("Playlist", self._process_all)])

    def pause(self):
        self._runner.pause()

    def resume(self):
        self._runner.resume()

    def stop(self):
        """Stop before the next step; the current video is parked in its history folder."""
        self._runner.stop()

    def end(self):
        """Kết thúc lượt chạy: no more video is processed, history is kept as it is."""
        with _lock:
            if self._runner.is_active:
                raise PlaylistRunError(RUN_ACTIVE)
            self._save(RUN_FINISHED)

    def wait(self, timeout=None) -> bool:
        """True once the background thread has ended."""
        thread = self._runner._thread
        if thread:
            thread.join(timeout)
        return not self._runner.is_active

    # ------ State ------

    def snapshot(self) -> RunSnapshot:
        videos = tuple(self.videos)
        current = next((v for v in videos if v.status == RUNNING), None)
        return RunSnapshot(
            state=self._runner.state, url=self.url, title=self.title, scope=self.scope,
            done=sum(v.selected and v.status == DONE for v in videos),
            total=sum(v.selected for v in videos),
            current_video=self._public(current) if current else None,
            current_step=self.current_step if current else "",
            pause_message=self._runner.pause_message, error=self._runner.error_msg,
            videos=tuple(self._public(v) for v in videos),
            unfinished=self.run_state in (RUN_RUNNING, RUN_INTERRUPTED) and not self._runner.is_active)

    def _public(self, video):
        """The video with the path of its history folder."""
        return replace(video, folder=str(self.folder / video.folder) if video.folder else None)

    def _save(self, state):
        """Write the state file; a temporary file first, so a crash never leaves half of it."""
        self.run_state = state
        self.folder.mkdir(parents=True, exist_ok=True)
        data = {"version": 1, "url": self.url, "title": self.title, "scope": self.scope, "state": state,
                "videos": [vars(v) for v in self.videos]}
        temporary = self.folder / (STATE_FILE + ".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, self.folder / STATE_FILE)

    def _set_status(self, position, status, **fields):
        self.videos[position] = replace(self.videos[position], status=status, **fields)
        self._save(RUN_RUNNING)

    # ------ Background thread ------

    def _process_all(self):
        failures = 0  # videos failed in a row
        try:
            for position, video in enumerate(self.videos):
                if video.selected and video.status == WAITING:
                    TaskRunner.check_cancel()
                    try:
                        self._process(position)
                        failures = 0
                    except StopTask:
                        raise
                    except Exception as error:
                        self._fail(position, error)
                        failures += 1
                        if failures >= FAILURES_TO_PAUSE:
                            self._runner.pause(FAILED_IN_A_ROW)
                            TaskRunner.check_cancel()
        except StopTask:
            self._park()
            raise
        self.current_step = ""
        self._save(RUN_FINISHED)

    def _park(self):
        """Move the work of the current video into its history folder; it waits for Tiếp tục."""
        for position, video in enumerate(self.videos):
            if video.status == RUNNING:
                merge_output(self.folder / video.folder)
                self.videos[position] = replace(video, status=WAITING, partial=True)
        self.current_step = ""
        self._save(RUN_INTERRUPTED)

    def _process(self, position):
        video = self.videos[position]
        self._set_status(position, RUNNING, failed_step="", error="")
        self.current_step = DOWNLOAD_STEP
        if video.partial:  # work of a stopped or crashed video; a video done before starts anew
            merge_output(OUTPUT, source=self.folder / video.folder)
            self.videos[position] = replace(self.videos[position], partial=False)
        if not _has_media():
            self.ytdlp.download(video.url)
        from core.pipeline import get_steps
        for label, step in (self.plan or get_steps)("all", self.scope == DUBBING):
            TaskRunner.check_cancel()
            self.current_step = label
            step()
        TaskRunner.check_cancel()
        self.current_step = SAVE_STEP
        cleanup(destination=str(self.folder / video.folder))
        if OUTPUT.exists() and any(OUTPUT.iterdir()):
            raise RuntimeError(f"Some files of output/ could not be moved to {self.folder / video.folder}")
        self._set_status(position, DONE)

    def _fail(self, position, error):
        """Mark the video ``FAILED`` and move its unfinished work into its history folder."""
        traceback.print_exception(error)
        step, self.current_step = self.current_step, ""
        destination = self.folder / self.videos[position].folder
        cleanup(destination=str(destination))
        self._set_status(position, FAILED, failed_step=step, error=_short(error), partial=True)
        if OUTPUT.exists() and any(OUTPUT.iterdir()):
            raise RuntimeError(f"Some files of output/ could not be moved to {destination}")


def _short(error):
    """The first line of the error message, or the name of the error when it has none."""
    lines = [line.strip() for line in str(error).splitlines() if line.strip()]
    return lines[0][:ERROR_LENGTH] if lines else type(error).__name__


_lock = threading.Lock()
_current: "PlaylistRun | None" = None


def current_run() -> "PlaylistRun | None":
    """The Lượt chạy playlist of this process, shared by every browser tab, or None."""
    return _current


def _has_media():
    from core._1_ytdlp import find_media_file
    try:
        find_media_file(str(OUTPUT))
    except Exception:
        return False
    return True


def _unfinished_state_file() -> Path | None:
    """The state file of an unfinished run in history/, the most recent one."""
    found = []
    for path in HISTORY.glob(f"*/{STATE_FILE}"):
        try:
            state = json.loads(path.read_text(encoding="utf-8")).get("state")
        except (OSError, ValueError):
            continue
        if state in (RUN_RUNNING, RUN_INTERRUPTED):
            found.append(path)
    return max(found, key=lambda p: p.stat().st_mtime, default=None)


def load_unfinished(ytdlp=None, plan=None) -> "PlaylistRun | None":
    """The unfinished run: the one of this process, or the one of a state file in history/.

    A run loaded from history/ becomes ``current_run()``, so every browser tab finds the same.
    It does not run by itself.
    """
    global _current
    with _lock:
        if _current is not None and (_current._runner.is_active or _current.snapshot().unfinished):
            return _current
        path = _unfinished_state_file()
        if path is None:
            return None
        _current = PlaylistRun._load(path, ytdlp=ytdlp, plan=plan)
        return _current
