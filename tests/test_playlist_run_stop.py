"""Stop, Tiếp tục and Kết thúc lượt chạy of a Lượt chạy playlist (#16), through the public interface.

The fake pipeline here behaves like the real one on a retry: a step whose output file already
exists is skipped. An app restart is a fresh process: no current run, the state file and the
folders of history/ and output/ as they were left.
"""
import json
import shutil
import threading
from pathlib import Path

import pytest

from core import playlist_run
from core.task_runner import TaskRunner
from tests.test_playlist_run import PLAYLIST, URL, FakeYtdlp, files, finish, watch, workspace  # noqa: F401

ROOT = Path("history/Talks_ 2026_10")
FIRST = ROOT / "1 - First_ intro_"


class ResumablePipeline:
    """Steps skip when their output exists, record the labels that ran, and check for a stop.

    ``block`` makes the translation of the first video wait after it wrote its LLM cache, so a
    test can stop the run in the middle of a step.
    """

    def __init__(self, block=None):
        self.ran = []
        self.block = block

    def __call__(self, stage, dubbing):
        def transcribe():
            if Path("output/log/asr.json").exists():
                return
            self.ran.append("transcribe")
            Path("output/log").mkdir(parents=True, exist_ok=True)
            Path("output/log/asr.json").write_text("{}")

        def translate():
            if Path("output/trans.srt").exists():
                return
            self.ran.append("translate")
            Path("output/gpt_log").mkdir(parents=True, exist_ok=True)
            Path("output/gpt_log/cache.json").write_text("{}")
            if self.block:
                self.block()
                self.block = None
            TaskRunner.check_cancel()
            Path("output/trans.srt").write_text("subtitles")

        return [("Word-level transcription and alignment", transcribe),
                ("Summarization and multi-step translation", translate)]


def start(selected, pipeline, ytdlp=None):
    ytdlp = ytdlp or FakeYtdlp({URL: PLAYLIST})
    run = playlist_run.PlaylistRun.create(playlist_run.read_playlist(URL, ytdlp=ytdlp), selected,
                                          playlist_run.SUBTITLES, ytdlp=ytdlp, plan=pipeline)
    run.start()
    return run, ytdlp


def stopped_in_first_translation(selected=("a1", "c3")):
    """A run stopped while the first video was being translated."""
    entered, release = threading.Event(), threading.Event()

    def block():
        entered.set()
        assert release.wait(3)

    run, ytdlp = start(list(selected), ResumablePipeline(block))
    assert entered.wait(3)
    run.stop()
    release.set()
    assert run.wait(3)
    return run, ytdlp


def state_file():
    return json.loads((ROOT / "playlist_run.json").read_text(encoding="utf-8"))


def output_is_empty():
    return not Path("output").exists() or not any(Path("output").iterdir())


def restart(monkeypatch):
    monkeypatch.setattr(playlist_run, "_current", None)


def test_stop_parks_the_unfinished_video_in_its_history_folder_and_leaves_output_empty(workspace):
    run, ytdlp = stopped_in_first_translation()

    snapshot = run.snapshot()
    assert snapshot.state == "stopped" and snapshot.unfinished
    assert snapshot.current_video is None and snapshot.current_step == ""
    videos = {v.video_id: v for v in snapshot.videos}
    assert (videos["a1"].status, videos["c3"].status) == (playlist_run.WAITING, playlist_run.WAITING)
    assert ytdlp.downloads == [watch("a1")]
    assert output_is_empty()
    assert files(FIRST) == ["First intro.mp4", "gpt_log/cache.json", "log/asr.json"]
    state = state_file()
    assert state["state"] == "interrupted"
    assert [(v["video_id"], v["status"]) for v in state["videos"] if v["selected"]] == [
        ("a1", "waiting"), ("c3", "waiting")]
    assert TaskRunner._current is None


def test_after_a_restart_the_unfinished_run_is_found_and_does_not_run_by_itself(workspace, monkeypatch):
    stopped_in_first_translation()
    restart(monkeypatch)

    ytdlp, pipeline = FakeYtdlp({URL: PLAYLIST}), ResumablePipeline()
    run = playlist_run.load_unfinished(ytdlp=ytdlp, plan=pipeline)

    assert run is not None and playlist_run.current_run() is run
    assert playlist_run.load_unfinished() is run  # another browser tab finds the same run
    snapshot = run.snapshot()
    assert snapshot.unfinished and snapshot.state not in ("running", "paused", "stopping")
    assert (snapshot.title, snapshot.url, snapshot.scope) == ("Talks: 2026/10", URL, playlist_run.SUBTITLES)
    assert (snapshot.done, snapshot.total) == (0, 2)
    assert run.wait(0.2)  # no thread was started
    assert ytdlp.downloads == [] and pipeline.ran == []
    assert files(FIRST) == ["First intro.mp4", "gpt_log/cache.json", "log/asr.json"]


def test_continue_moves_the_unfinished_video_back_and_does_not_redo_finished_steps(workspace, monkeypatch):
    stopped_in_first_translation()
    restart(monkeypatch)
    ytdlp, pipeline = FakeYtdlp({URL: PLAYLIST}), ResumablePipeline()
    run = playlist_run.load_unfinished(ytdlp=ytdlp, plan=pipeline)

    run.start()
    snapshot = finish(run)

    assert snapshot.state == "completed" and (snapshot.done, snapshot.total) == (2, 2)
    assert not snapshot.unfinished
    assert ytdlp.downloads == [watch("c3")]  # the first video was already downloaded
    assert pipeline.ran == ["translate", "transcribe", "translate"]
    assert files(FIRST) == ["First intro.mp4", "gpt_log/cache.json", "log/asr.json", "trans.srt"]
    assert output_is_empty()
    assert state_file()["state"] == "finished"
    assert playlist_run.load_unfinished() is None


def test_a_stopped_run_continues_in_the_same_process(workspace):
    run, ytdlp = stopped_in_first_translation()

    run.start()
    snapshot = finish(run)

    assert snapshot.state == "completed" and snapshot.done == 2
    assert ytdlp.downloads == [watch("a1"), watch("c3")]
    assert files(FIRST) == ["First intro.mp4", "gpt_log/cache.json", "log/asr.json", "trans.srt"]


def test_after_a_crash_the_unfinished_work_left_in_output_continues(workspace, monkeypatch):
    run, _ytdlp = start(["a1", "c3"], ResumablePipeline())
    finish(run)
    # The state file and output/ as a crash in the translation of the first video leaves them
    state = state_file()
    state["state"] = "running"
    for video in state["videos"]:
        if video["selected"]:
            video["status"] = "running" if video["video_id"] == "a1" else "waiting"
    (ROOT / "playlist_run.json").write_text(json.dumps(state), encoding="utf-8")
    (FIRST / "trans.srt").unlink()
    FIRST.rename("output")
    shutil.rmtree(ROOT / "3 - Second talk")
    restart(monkeypatch)

    ytdlp, pipeline = FakeYtdlp({URL: PLAYLIST}), ResumablePipeline()
    loaded = playlist_run.load_unfinished(ytdlp=ytdlp, plan=pipeline)
    assert loaded.snapshot().unfinished and ytdlp.downloads == [] and pipeline.ran == []
    assert [v.status for v in loaded.snapshot().videos if v.selected] == [playlist_run.WAITING] * 2

    loaded.start()
    snapshot = finish(loaded)

    assert snapshot.state == "completed" and snapshot.done == 2
    assert ytdlp.downloads == [watch("c3")]
    assert pipeline.ran == ["translate", "transcribe", "translate"]
    assert files(FIRST) == ["First intro.mp4", "gpt_log/cache.json", "log/asr.json", "trans.srt"]
    assert output_is_empty()


def test_end_run_keeps_history_and_the_run_is_no_longer_unfinished(workspace, monkeypatch):
    run, ytdlp = stopped_in_first_translation()
    before = files("history")

    run.end()

    assert not run.snapshot().unfinished
    assert state_file()["state"] == "finished"
    assert files("history") == before
    assert playlist_run.load_unfinished() is None
    restart(monkeypatch)
    assert playlist_run.load_unfinished() is None
    assert ytdlp.downloads == [watch("a1")]


def test_end_run_after_a_crash_moves_output_into_history(workspace, monkeypatch):
    stopped_in_first_translation()
    state = state_file()
    state["state"] = "running"
    state["videos"][0]["status"] = "running"
    (ROOT / "playlist_run.json").write_text(json.dumps(state), encoding="utf-8")
    FIRST.rename("output")
    restart(monkeypatch)

    playlist_run.load_unfinished().end()

    assert output_is_empty()
    assert files(FIRST) == ["First intro.mp4", "gpt_log/cache.json", "log/asr.json"]
    assert playlist_run.load_unfinished() is None


def test_end_is_refused_while_the_run_is_active(workspace):
    release = threading.Event()
    run, _ytdlp = start(["a1"], ResumablePipeline(lambda: release.wait(3)))
    try:
        with pytest.raises(playlist_run.PlaylistRunError):
            run.end()
    finally:
        release.set()
    finish(run)


def test_only_one_run_at_a_time_while_one_is_unfinished(workspace, monkeypatch):
    stopped_in_first_translation()
    for restarted in (False, True):
        if restarted:
            restart(monkeypatch)
        with pytest.raises(playlist_run.PlaylistRunError) as refused:
            start(["f6"], ResumablePipeline())
        assert str(refused.value) == playlist_run.RUN_UNFINISHED

    playlist_run.load_unfinished().end()
    run, ytdlp = start(["f6"], ResumablePipeline())
    assert finish(run).state == "completed" and ytdlp.downloads == [watch("f6")]


def test_new_messages_exist_in_every_locale():
    from translations.translations import DISPLAY_LANGUAGES
    keys = {playlist_run.RUN_UNFINISHED, playlist_run.RUN_ACTIVE}
    root = Path(__file__).resolve().parents[1] / "translations"
    missing = {language: sorted(keys - json.loads((root / f"{language}.json").read_text(encoding="utf-8")).keys())
               for language in DISPLAY_LANGUAGES.values()}
    assert missing == {language: [] for language in DISPLAY_LANGUAGES.values()}
