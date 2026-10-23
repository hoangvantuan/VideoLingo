"""Regressions found by the review of the Lượt chạy playlist (spec #13).

Same fakes as tests/test_playlist_run.py. The pipeline here records the steps it ran per video,
raises in the translation for the videos named in ``fail``, skips a step whose file is already in
output/ (as the real one does), and can hold the transcription of one video at a gate.
"""
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from core import playlist_run
from core.task_runner import TaskRunner
from core.utils import output_lock
from tests.test_playlist_failures import ROOT, statuses, wait_for
from tests.test_playlist_run import (PLAYLIST, URL, FakeYtdlp, files, finish, start, watch,  # noqa: F401
                                     workspace)


class Pipeline:
    def __init__(self, fail=(), hold=None):
        self.fail = set(fail)
        self.hold = hold  # title of the video whose transcription waits at the gate
        self.gate = threading.Event()
        self.at_gate = threading.Event()
        self.ran = []

    def __call__(self, stage, dubbing):
        def video():
            return next(Path("output").glob("*.mp4")).stem

        def transcribe():
            if video() == self.hold:
                self.at_gate.set()
                self.gate.wait(3)
            if Path("output/log/asr.json").exists():
                return
            self.ran.append((video(), "transcribe"))
            Path("output/log").mkdir(parents=True, exist_ok=True)
            Path("output/log/asr.json").write_text("{}")

        def translate():
            if Path("output/trans.srt").exists():
                return
            self.ran.append((video(), "translate"))
            if video() in self.fail:
                raise RuntimeError("Quota exceeded")
            Path("output/trans.srt").write_text("subtitles")

        return [("Word-level transcription and alignment", transcribe),
                ("Summarization and multi-step translation", translate)]


def state_file():
    return json.loads((ROOT / "playlist_run.json").read_text(encoding="utf-8"))


def stopped_with_a_failed_and_a_waiting_video():
    """a1 done, c3 failed, stopped in the transcription of f6: the run is unfinished."""
    pipeline = Pipeline(fail={"Second talk"}, hold="Third talk")
    run, ytdlp = start(["a1", "c3", "f6"], pipeline=pipeline)
    assert pipeline.at_gate.wait(3)
    run.stop()
    pipeline.gate.set()
    finish(run)
    assert statuses(run.snapshot()) == [playlist_run.DONE, playlist_run.FAILED, playlist_run.WAITING]
    pipeline.hold = None
    pipeline.fail.clear()
    pipeline.ran.clear()
    return run, ytdlp, pipeline


# ------ Bug: TaskRunner._current reset by a single video run during the auto-pause ------

def test_pause_and_stop_apply_after_a_single_video_run_during_the_auto_pause(workspace):
    pipeline = Pipeline(fail={"First intro", "Second talk"})
    run, _ytdlp = start(["a1", "c3", "f6"], pipeline=pipeline)
    wait_for(run, "paused")
    single = TaskRunner()  # the single video mode uses output/ while the run is paused
    single.start([("Single video", lambda: None)])
    single._thread.join(3)
    assert TaskRunner._current is None
    pipeline.fail.clear()
    pipeline.ran.clear()
    pipeline.hold = "Second talk"

    run.resume()
    assert pipeline.at_gate.wait(3)
    run.stop()
    pipeline.gate.set()
    snapshot = finish(run)

    assert snapshot.state == "stopped" and snapshot.unfinished
    assert pipeline.ran == []  # stopped before the translation of c3, and f6 never began
    assert statuses(snapshot) == [playlist_run.FAILED, playlist_run.WAITING, playlist_run.WAITING]


# ------ Bug: is_locked() of another session while a run is starting ------

def test_is_locked_waits_for_a_run_that_is_starting_and_keeps_its_lock(workspace, monkeypatch):
    real_acquire = output_lock.acquire
    written, go = threading.Event(), threading.Event()

    def acquire():
        real_acquire()
        if not written.is_set():  # the run is starting: its lock is written, its thread not started
            written.set()
            go.wait(3)
    monkeypatch.setattr(output_lock, "acquire", acquire)
    pipeline = Pipeline(hold="First intro")
    starter = threading.Thread(target=lambda: start(["a1"], pipeline=pipeline))
    starter.start()
    assert written.wait(3)
    result = []
    checker = threading.Thread(target=lambda: result.append(output_lock.is_locked()))
    checker.start()
    time.sleep(0.2)
    blocked = result == []
    go.set()
    starter.join(3)
    checker.join(3)
    try:
        assert blocked, "is_locked() decided while the run was starting"
        assert result == [True] and output_lock.LOCK_FILE.exists()
    finally:
        pipeline.gate.set()
        finish(playlist_run.current_run())


# ------ Bug: retry_failed() refused after the state file was written ------

def test_retry_failed_refused_late_leaves_the_state_file_as_it_was(workspace, monkeypatch):
    run, _ytdlp = start(["a1", "c3"], pipeline=Pipeline(fail={"Second talk"}))
    finish(run)

    def acquire():
        raise OSError("Read-only file system")
    monkeypatch.setattr(output_lock, "acquire", acquire)
    with pytest.raises(OSError):
        run.retry_failed()

    assert statuses(run.snapshot(), ("a1", "c3")) == [playlist_run.DONE, playlist_run.FAILED]
    assert state_file()["state"] == "finished"
    assert [v["status"] for v in state_file()["videos"] if v["selected"]] == ["done", "failed"]
    assert not run.is_active


# ------ Spec #2/#4: retry_failed() runs only the `Lỗi` videos ------

def test_retry_failed_runs_only_the_failed_videos_and_continue_runs_the_waiting_ones(workspace):
    run, _ytdlp, pipeline = stopped_with_a_failed_and_a_waiting_video()

    run.retry_failed()
    snapshot = finish(run)

    assert pipeline.ran == [("Second talk", "translate")]
    assert statuses(snapshot) == [playlist_run.DONE, playlist_run.DONE, playlist_run.WAITING]
    assert snapshot.unfinished and state_file()["state"] == "interrupted"

    run.start()  # Tiếp tục
    snapshot = finish(run)
    assert statuses(snapshot) == [playlist_run.DONE, playlist_run.DONE, playlist_run.DONE]
    assert state_file()["state"] == "finished"


def test_an_ended_run_processes_no_more_waiting_video(workspace):
    run, ytdlp, pipeline = stopped_with_a_failed_and_a_waiting_video()
    run.end()

    run.retry_failed()
    snapshot = finish(run)

    assert pipeline.ran == [("Second talk", "translate")]
    videos = {v.video_id: v for v in snapshot.videos}
    assert videos["c3"].status == playlist_run.DONE and videos["f6"].status != playlist_run.DONE
    assert not snapshot.unfinished and state_file()["state"] == "finished"
    assert playlist_run.load_unfinished() is None
    assert ytdlp.downloads == [watch("a1"), watch("c3"), watch("f6")]


# ------ Spec #5: a `Lỗi` video not selected in a new run keeps its unfinished work ------

def test_a_failed_video_left_out_of_a_run_goes_on_from_its_history_folder_later(workspace, monkeypatch):
    pipeline = Pipeline(fail={"Second talk"})
    run, ytdlp = start(["a1", "c3"], pipeline=pipeline)
    finish(run)
    pipeline.fail.clear()

    playlist = playlist_run.read_playlist(URL, ytdlp=ytdlp)
    run = playlist_run.PlaylistRun.create(playlist, ["f6"], playlist_run.SUBTITLES, ytdlp=ytdlp, plan=pipeline)
    run.start()
    finish(run)
    second = {v["video_id"]: v for v in state_file()["videos"]}["c3"]
    assert (second["folder"], second["partial"]) == ("3 - Second talk", True)

    monkeypatch.setattr(playlist_run, "_current", None)
    pipeline.ran.clear()
    ytdlp.downloads.clear()
    playlist = playlist_run.read_playlist(URL, ytdlp=ytdlp)
    run = playlist_run.PlaylistRun.create(playlist, ["c3"], playlist_run.SUBTITLES, ytdlp=ytdlp, plan=pipeline)
    run.start()
    snapshot = finish(run)

    assert statuses(snapshot) == [playlist_run.DONE, playlist_run.DONE, playlist_run.DONE]
    assert ytdlp.downloads == [] and pipeline.ran == [("Second talk", "translate")]
    assert files(ROOT / "3 - Second talk") == ["Second talk.mp4", "log/asr.json", "trans.srt"]
    assert not (ROOT / "3 - Second talk [c3]").exists()


# ------ load_unfinished() leaves output/ alone while another process runs the playlist ------

def test_load_unfinished_does_not_take_output_from_a_run_of_another_process(workspace):
    folder = ROOT / "1 - First_ intro_"
    ROOT.mkdir(parents=True)
    (ROOT / "playlist_run.json").write_text(json.dumps({
        "version": 1, "url": URL, "title": "Talks: 2026/10", "scope": playlist_run.SUBTITLES,
        "state": "running", "videos": [{
            "video_id": "a1", "index": 1, "title": "First: intro?", "duration": 61, "selected": True,
            "status": "running", "folder": folder.name, "url": watch("a1")}],
    }), encoding="utf-8")
    Path("output").mkdir()
    Path("output/First intro.mp4").write_bytes(b"")
    other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        output_lock.LOCK_FILE.write_text(str(other.pid), encoding="utf-8")
        assert other.pid != os.getpid()

        playlist_run.load_unfinished()

        assert Path("output/First intro.mp4").exists() and not folder.exists()
        assert state_file()["state"] == "running"
    finally:
        other.kill()
        other.wait()


# ------ Spec #1: the run panel lists every video with its Trạng thái video ------

def test_the_run_panel_lists_unavailable_and_unselected_done_videos(workspace):
    from core.st_utils import playlist_tab
    run, ytdlp = start(["a1"], pipeline=Pipeline())
    finish(run)
    playlist = playlist_run.read_playlist(URL, ytdlp=ytdlp)
    run = playlist_run.PlaylistRun.create(playlist, ["c3"], playlist_run.SUBTITLES, ytdlp=ytdlp, plan=Pipeline())
    run.start()
    snapshot = finish(run)

    rows = playlist_tab._rows(snapshot)

    labels = playlist_tab._status_labels()
    assert [row["#"] for row in rows] == [1, 2, 3, 4, 5]  # f6 is neither selected nor done
    assert [row[playlist_tab.t("Status")] for row in rows] == [labels[playlist_run.DONE], labels[playlist_run.UNAVAILABLE], labels[playlist_run.DONE],
                              labels[playlist_run.UNAVAILABLE], labels[playlist_run.UNAVAILABLE]]
