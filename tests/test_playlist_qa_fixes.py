"""Regressions found by the browser QA of the Lượt chạy playlist (spec #13).

B1: the download step renamed the lock of output/. B2: a refused control lost its message at
the next refresh of the panel. B3: the error of a failed yt-dlp download was kept as ``ERROR:``.
B4: after a run the form still showed the videos it had just done as not done.
Same fakes as tests/test_playlist_run.py; yt-dlp itself is a fake class, no network.
"""
import os
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import core._1_ytdlp as ytdlp_module
from core import playlist_run
from core.utils import output_lock
from tests.test_playlist_failures import ROOT, statuses
from tests.test_playlist_run import (PLAYLIST, URL, FakePipeline, FakeYtdlp, finish, start,  # noqa: F401
                                     workspace)


class FakeYoutubeDL:
    """Writes ``<title>..mp4`` and a thumbnail as yt-dlp does; the trailing dot is renamed away."""

    def __init__(self, options):
        self.save_path = os.path.dirname(options["outtmpl"])

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def download(self, urls):
        titles = {e["url"]: e["title"] for e in PLAYLIST["entries"]}
        stem = titles[urls[0]].replace(":", "").replace("?", "")
        Path(self.save_path, f"{stem}..mp4").write_bytes(b"")
        Path(self.save_path, f"{stem}..jpg").write_bytes(b"")


@pytest.fixture
def real_download(workspace, monkeypatch):
    monkeypatch.setattr(ytdlp_module, "update_ytdlp", lambda: FakeYoutubeDL)


# ------ B1: the download step renamed output/.playlist_run.lock ------

def test_the_download_keeps_the_lock_and_still_renames_the_video(real_download):
    output_lock.acquire()

    ytdlp_module.download_video_ytdlp(PLAYLIST["entries"][0]["url"])

    names = sorted(os.listdir("output"))
    assert ".playlist_run.lock" in names and "playlist_run.lock" not in names
    assert "First intro.mp4" in names  # the rename pass still runs on the files of the video


def test_a_run_keeps_output_locked_after_the_download_and_no_lock_goes_to_history(real_download):
    seen = []

    def plan(stage, dubbing):
        def transcribe():
            seen.append((sorted(os.listdir("output")), output_lock.is_locked()))
            Path("output/trans.srt").write_text("subtitles")
        return [("Word-level transcription and alignment", transcribe)]

    ytdlp = FakeYtdlp({URL: PLAYLIST})
    ytdlp.download = playlist_run.Ytdlp().download  # the real download step, with the fake yt-dlp
    run, _ = start(["a1", "c3"], pipeline=plan, ytdlp=ytdlp)
    snapshot = finish(run)

    assert statuses(snapshot, ("a1", "c3")) == [playlist_run.DONE, playlist_run.DONE]
    for names, locked in seen:
        assert ".playlist_run.lock" in names and "playlist_run.lock" not in names
        assert locked
    assert not [p for p in ROOT.rglob("*") if p.name.endswith("playlist_run.lock")]
    assert not Path("output").exists()


# ------ B3: the stored error of a yt-dlp failure ------

def test_short_keeps_the_message_of_a_ytdlp_error():
    error = Exception("ERROR: \r[download] Got error: HTTP Error 500: Internal Server Error\nmore")

    assert "HTTP Error 500: Internal Server Error" in playlist_run._short(error)


@pytest.mark.parametrize("message, expected", [
    ("Quota exceeded\nTraceback line", "Quota exceeded"),
    ("ERROR:\nCookies file not found: x.txt", "Cookies file not found: x.txt"),
    ("  \n", "RuntimeError"),
    ("", "RuntimeError"),
])
def test_short_takes_the_first_line_with_a_message(message, expected):
    assert playlist_run._short(RuntimeError(message)) == expected


# ------ B2: a refused control lost its message at the next refresh of the panel ------

def _tab():
    from core.st_utils import playlist_tab
    playlist_tab.render()


class RefusingRun:
    """A run paused by FAILED_IN_A_ROW whose Resume is refused: output/ holds other files."""

    is_active = True

    def __init__(self):
        self.stopped = False
        video = playlist_run.VideoSnapshot(video_id="a1", index=1, title="First: intro?", duration=61,
                                           selected=True, status=playlist_run.FAILED, folder="1 - x",
                                           failed_step="Download video", error="Quota exceeded")
        self.paused = playlist_run.RunSnapshot(
            state="paused", url=URL, title="Talks: 2026/10", scope=playlist_run.SUBTITLES, done=0, total=1,
            current_video=video, current_step="", pause_message=playlist_run.FAILED_IN_A_ROW, error="",
            videos=(video,), active=True)

    def snapshot(self):
        return self.paused

    def resume(self):
        raise playlist_run.PlaylistRunError(playlist_run.OUTPUT_NOT_EMPTY)

    def stop(self):
        self.stopped = True

    def wait(self, timeout=None):
        return True


def refusal_shown(at):
    from core.st_utils import playlist_tab
    return any(playlist_tab.t(playlist_run.OUTPUT_NOT_EMPTY) in e.value for e in at.error)


def test_a_refused_resume_keeps_its_message_until_the_next_action(workspace, monkeypatch):
    run = RefusingRun()
    monkeypatch.setattr(playlist_run, "_current", run)
    at = AppTest.from_function(_tab).run(timeout=30)
    assert not at.exception and not refusal_shown(at)

    at = at.button(key="playlist_resume").click().run(timeout=30)
    assert refusal_shown(at)
    at = at.run(timeout=30)  # the panel refreshes
    assert refusal_shown(at)

    at = at.button(key="playlist_stop_paused").click().run(timeout=30)
    assert run.stopped and not refusal_shown(at)


# ------ B4: after a run the form showed the videos it had just done as not done ------

def test_after_a_run_the_form_shows_its_videos_done_and_unticked(workspace, monkeypatch):
    ytdlp = FakeYtdlp({URL: PLAYLIST})
    playlist = playlist_run.read_playlist(URL, ytdlp=ytdlp)  # read before the run, as the form holds it
    run = playlist_run.PlaylistRun.create(playlist, ["a1", "c3"], playlist_run.SUBTITLES, ytdlp=ytdlp,
                                          plan=FakePipeline())
    run.start()
    finish(run)

    at = AppTest.from_function(_tab)
    at.session_state["_playlist"] = playlist
    at = at.run(timeout=30)
    assert not at.exception

    from core.st_utils import playlist_tab
    done = playlist_tab.t("Done")
    boxes = {box.label.split(".")[0]: box for box in at.checkbox}
    assert done in boxes["1"].label and not boxes["1"].value
    assert done in boxes["3"].label and not boxes["3"].value
    assert done not in boxes["6"].label and boxes["6"].value


def test_mark_done_reads_the_state_file_of_the_playlist(workspace):
    playlist = playlist_run.read_playlist(URL, ytdlp=FakeYtdlp({URL: PLAYLIST}))
    run, _ = start(["c3"])
    finish(run)

    marked = playlist_run.mark_done(playlist)

    assert [v.video_id for v in marked.videos if v.done] == ["c3"]
    assert [replace_done(v) for v in marked.videos] == [replace_done(v) for v in playlist.videos]


def replace_done(video):
    from dataclasses import replace
    return replace(video, done=False)
