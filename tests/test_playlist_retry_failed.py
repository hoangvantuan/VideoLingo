"""#19: run the `Lỗi` videos again from the step that failed, and Resume after an auto-pause.

Same fakes as tests/test_playlist_run.py. The pipeline here skips a step whose intermediate
file is already in output/, as the real one does, and records the steps it ran per video.
"""
import json
from pathlib import Path

import pytest

from core import playlist_run
from tests.test_playlist_failures import ROOT, FailingPipeline, statuses, wait_for
from tests.test_playlist_run import (PLAYLIST, URL, FakeYtdlp, entry, files, finish, start, watch,  # noqa: F401
                                     workspace)


class SkippingPipeline:
    """Transcribe and translate like FakePipeline, each skipped when its file exists in output/.

    ``ran`` lists (video, step) for the steps that did their work; the translation raises for the
    videos named in ``fail`` after its LLM cache is written, and reuses that cache when present.
    """

    def __init__(self, fail=()):
        self.fail = set(fail)
        self.ran = []
        self.cache_found = []

    def __call__(self, stage, dubbing):
        def video():
            return next(Path("output").glob("*.mp4")).stem

        def transcribe():
            if Path("output/log/asr.json").exists():
                return
            self.ran.append((video(), "transcribe"))
            Path("output/log").mkdir(parents=True, exist_ok=True)
            Path("output/log/asr.json").write_text("{}")

        def translate():
            if Path("output/trans.srt").exists():
                return
            self.ran.append((video(), "translate"))
            cache = Path("output/gpt_log/cache.json")
            self.cache_found.append((video(), cache.exists()))
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text("{}")
            if video() in self.fail:
                raise RuntimeError("Quota exceeded")
            Path("output/trans.srt").write_text("subtitles")

        return [("Word-level transcription and alignment", transcribe),
                ("Summarization and multi-step translation", translate)]


def test_resume_after_two_failures_in_a_row_runs_the_video_that_just_failed_first(workspace):
    pipeline = SkippingPipeline(fail={"First intro", "Second talk"})
    run, ytdlp = start(["a1", "c3", "f6"], pipeline=pipeline)
    wait_for(run, "paused")
    pipeline.fail.clear()  # the user fixed the cause

    run.resume()
    snapshot = finish(run)

    assert snapshot.state == "completed" and snapshot.pause_message == ""
    assert statuses(snapshot) == [playlist_run.FAILED, playlist_run.DONE, playlist_run.DONE]
    assert ytdlp.downloads == [watch("a1"), watch("c3"), watch("f6")]  # not downloaded again
    assert pipeline.ran == [
        ("First intro", "transcribe"), ("First intro", "translate"),
        ("Second talk", "transcribe"), ("Second talk", "translate"),
        ("Second talk", "translate"),  # the step that failed, before the next video
        ("Third talk", "transcribe"), ("Third talk", "translate"),
    ]
    second = {v.video_id: v for v in snapshot.videos}["c3"]
    assert (second.failed_step, second.error) == ("", "")
    assert files(ROOT / "3 - Second talk") == ["Second talk.mp4", "gpt_log/cache.json", "log/asr.json", "trans.srt"]


def test_the_video_that_just_failed_fails_again_after_resume_and_the_run_pauses_again(workspace):
    pipeline = SkippingPipeline(fail={"First intro", "Second talk"})
    run, _ytdlp = start(["a1", "c3", "f6"], pipeline=pipeline)
    wait_for(run, "paused")
    run.resume()

    snapshot = wait_for(run, "paused")
    assert snapshot.pause_message == playlist_run.FAILED_IN_A_ROW
    assert statuses(snapshot) == [playlist_run.FAILED, playlist_run.FAILED, playlist_run.WAITING]
    assert pipeline.ran.count(("Second talk", "translate")) == 2
    run.stop()
    assert run.wait(3)


def test_retry_failed_runs_each_failed_video_from_the_step_that_failed(workspace):
    pipeline = SkippingPipeline(fail={"Second talk"})
    run, ytdlp = start(["a1", "c3", "f6"], pipeline=pipeline)
    assert statuses(finish(run)) == [playlist_run.DONE, playlist_run.FAILED, playlist_run.DONE]
    pipeline.fail.clear()
    pipeline.ran.clear()
    pipeline.cache_found.clear()

    run.retry_failed()
    snapshot = finish(run)

    assert snapshot.state == "completed"
    assert statuses(snapshot) == [playlist_run.DONE, playlist_run.DONE, playlist_run.DONE]
    assert (snapshot.done, snapshot.total) == (3, 3)
    assert ytdlp.downloads == [watch("a1"), watch("c3"), watch("f6")]  # nothing downloaded again
    assert pipeline.ran == [("Second talk", "translate")]  # the transcription is not run again
    assert pipeline.cache_found == [("Second talk", True)]  # with the LLM cache of the first try
    second = {v.video_id: v for v in snapshot.videos}["c3"]
    assert second.folder == str(ROOT / "3 - Second talk")
    assert (second.failed_step, second.error, second.partial) == ("", "", False)
    assert files(ROOT / "3 - Second talk") == ["Second talk.mp4", "gpt_log/cache.json", "log/asr.json", "trans.srt"]
    assert not Path("output").exists() or not any(Path("output").iterdir())
    state = json.loads((ROOT / "playlist_run.json").read_text(encoding="utf-8"))
    assert state["state"] == "finished"
    assert [v["status"] for v in state["videos"] if v["selected"]] == ["done"] * 3


def test_retry_failed_is_refused_while_the_run_is_active(workspace):
    pipeline = SkippingPipeline(fail={"First intro", "Second talk"})
    run, _ytdlp = start(["a1", "c3", "f6"], pipeline=pipeline)
    wait_for(run, "paused")

    with pytest.raises(playlist_run.PlaylistRunError):
        run.retry_failed()
    run.stop()
    assert run.wait(3)


def test_retry_failed_is_refused_when_output_is_not_empty_and_the_videos_stay_failed(workspace):
    run, _ytdlp = start(["a1", "c3"], pipeline=SkippingPipeline(fail={"Second talk"}))
    finish(run)
    Path("output").mkdir()
    Path("output/other.mp4").write_bytes(b"")

    with pytest.raises(playlist_run.PlaylistRunError, match="output"):
        run.retry_failed()

    assert statuses(run.snapshot(), ("a1", "c3")) == [playlist_run.DONE, playlist_run.FAILED]


def test_a_failed_video_selected_in_a_new_run_goes_on_from_its_history_folder(workspace, monkeypatch):
    pipeline = SkippingPipeline(fail={"Second talk"})
    run, ytdlp = start(["a1", "c3"], pipeline=pipeline)
    finish(run)
    monkeypatch.setattr(playlist_run, "_current", None)  # the app was closed and opened again
    pipeline.fail.clear()
    pipeline.ran.clear()
    ytdlp.downloads.clear()

    playlist = playlist_run.read_playlist(URL, ytdlp=ytdlp)
    assert [(v.video_id, v.done) for v in playlist.videos if v.video_id in ("a1", "c3")] == [("a1", True), ("c3", False)]
    run = playlist_run.PlaylistRun.create(playlist, ["c3"], playlist_run.SUBTITLES, ytdlp=ytdlp, plan=pipeline)
    run.start()
    snapshot = finish(run)

    assert statuses(snapshot, ("a1", "c3")) == [playlist_run.DONE, playlist_run.DONE]
    assert ytdlp.downloads == []
    assert pipeline.ran == [("Second talk", "translate")]
    assert files(ROOT / "3 - Second talk") == ["Second talk.mp4", "gpt_log/cache.json", "log/asr.json", "trans.srt"]


def test_an_error_outside_the_videos_leaves_the_run_unfinished_with_no_video_running(workspace, monkeypatch):
    from core.utils import output_lock
    real_cleanup = playlist_run.cleanup
    def cleanup(destination):
        if "Second talk" in destination:
            raise OSError("No space left on device")  # the failure of the video can not be recorded
        real_cleanup(destination=destination)
    monkeypatch.setattr(playlist_run, "cleanup", cleanup)
    pipeline = SkippingPipeline(fail={"Second talk"})
    run, ytdlp = start(["a1", "c3", "f6"], pipeline=pipeline)

    snapshot = finish(run)

    assert snapshot.state == "error" and snapshot.unfinished
    assert statuses(snapshot) == [playlist_run.DONE, playlist_run.WAITING, playlist_run.WAITING]
    assert snapshot.current_video is None
    assert files(ROOT / "3 - Second talk") == ["Second talk.mp4", "gpt_log/cache.json", "log/asr.json"]
    assert not Path("output").exists() or not any(Path("output").iterdir())
    assert not output_lock.is_locked()
    assert json.loads((ROOT / "playlist_run.json").read_text(encoding="utf-8"))["state"] == "interrupted"

    # Tiếp tục, once the cause is fixed: the video goes on from its history folder
    monkeypatch.setattr(playlist_run, "cleanup", real_cleanup)
    pipeline.fail.clear()
    run.start()
    snapshot = finish(run)
    assert snapshot.state == "completed"
    assert statuses(snapshot) == [playlist_run.DONE, playlist_run.DONE, playlist_run.DONE]
    assert ytdlp.downloads == [watch("a1"), watch("c3"), watch("f6")]


def test_retry_failed_videos_exists_in_every_locale():
    from translations.translations import DISPLAY_LANGUAGES
    root = Path(__file__).resolve().parents[1] / "translations"
    missing = [language for language in DISPLAY_LANGUAGES.values()
               if "Retry failed videos" not in json.loads((root / f"{language}.json").read_text(encoding="utf-8"))]
    assert missing == []
