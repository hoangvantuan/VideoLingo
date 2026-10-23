"""#15: a video that fails does not block the Lượt chạy playlist; 2 failures in a row pause it.

Same fakes as tests/test_playlist_run.py; the pipeline raises at a chosen step for chosen videos.
"""
import json
import time
from pathlib import Path

import pytest

from core import playlist_run
from core.utils import output_lock
from tests.test_playlist_run import PLAYLIST, URL, FakePipeline, FakeYtdlp, files, finish, start, watch, workspace  # noqa: F401

ROOT = Path("history/Talks_ 2026_10")
TRANSLATE = "Summarization and multi-step translation"


class OutputCheckingYtdlp(FakeYtdlp):
    """Records whether output/ was empty when each download began."""

    def __init__(self, infos):
        super().__init__(infos)
        self.output_empty = []

    def download(self, url):
        self.output_empty.append(not Path("output").exists()
                                 or not any(p != output_lock.LOCK_FILE for p in Path("output").iterdir()))
        super().download(url)


class FailingPipeline(FakePipeline):
    """Raises in the translation step, after its LLM cache is written, for the videos named in `fail`."""

    def __init__(self, fail, message="Quota exceeded\nTraceback (most recent call last): ..."):
        super().__init__(extra=self._maybe_fail)
        self.fail = set(fail)
        self.message = message

    def _maybe_fail(self):
        if {p.stem for p in Path("output").glob("*.mp4")} & self.fail:
            raise RuntimeError(self.message)


def wait_for(run, state, timeout=5):
    deadline = time.monotonic() + timeout
    while run.snapshot().state != state:
        assert time.monotonic() < deadline, f"the run did not reach {state}: {run.snapshot().state}"
        time.sleep(0.02)
    return run.snapshot()


def statuses(snapshot, ids=("a1", "c3", "f6")):
    videos = {v.video_id: v for v in snapshot.videos}
    return [videos[video_id].status for video_id in ids]


def test_a_failed_video_keeps_its_work_in_history_and_the_run_goes_on(workspace):
    earlier = ROOT / "3 - Second talk" / "notes.txt"
    earlier.parent.mkdir(parents=True)
    earlier.write_text("kept")
    # The folder is the video's own from an earlier run (#17): a folder no state file claims is not reused
    (ROOT / "playlist_run.json").write_text(json.dumps({"videos": [
        {"video_id": "c3", "status": playlist_run.FAILED, "folder": "3 - Second talk"}]}), encoding="utf-8")
    ytdlp = OutputCheckingYtdlp({URL: PLAYLIST})

    run, _ytdlp = start(["a1", "c3", "f6"], pipeline=FailingPipeline({"Second talk"}), ytdlp=ytdlp)
    snapshot = finish(run)

    assert snapshot.state == "completed"
    assert statuses(snapshot) == [playlist_run.DONE, playlist_run.FAILED, playlist_run.DONE]
    assert (snapshot.done, snapshot.total) == (2, 3)
    failed = {v.video_id: v for v in snapshot.videos}["c3"]
    assert (failed.failed_step, failed.error) == (TRANSLATE, "Quota exceeded")
    assert failed.folder == str(ROOT / "3 - Second talk")
    assert files(ROOT / "3 - Second talk") == ["Second talk.mp4", "gpt_log/cache.json", "log/asr.json", "notes.txt"]
    assert earlier.read_text() == "kept"
    assert ytdlp.downloads == [watch("a1"), watch("c3"), watch("f6")]
    assert ytdlp.output_empty == [True, True, True]
    assert not Path("output").exists() or not any(Path("output").iterdir())

    state = json.loads((ROOT / "playlist_run.json").read_text(encoding="utf-8"))
    video = next(v for v in state["videos"] if v["video_id"] == "c3")
    assert (video["status"], video["failed_step"], video["error"]) == ("failed", TRANSLATE, "Quota exceeded")
    done = next(v for v in state["videos"] if v["video_id"] == "a1")
    assert (done["failed_step"], done["error"]) == ("", "")


def test_a_failed_download_is_recorded_with_the_download_step(workspace):
    class BrokenDownload(FakeYtdlp):
        def download(self, url):
            if url == watch("a1"):
                Path("output").mkdir(exist_ok=True)
                Path("output/partial.part").write_bytes(b"")
                raise RuntimeError("Sign in to confirm you're not a bot")
            super().download(url)

    run, _ytdlp = start(["a1", "c3"], ytdlp=BrokenDownload({URL: PLAYLIST}))
    snapshot = finish(run)

    assert snapshot.state == "completed"
    failed = {v.video_id: v for v in snapshot.videos}["a1"]
    assert (failed.status, failed.failed_step, failed.error) == (
        playlist_run.FAILED, playlist_run.DOWNLOAD_STEP, "Sign in to confirm you're not a bot")
    assert files(ROOT / "1 - First_ intro_") == ["partial.part"]
    assert statuses(snapshot, ("c3",)) == [playlist_run.DONE]


def test_two_failures_in_a_row_pause_the_run_with_a_message_until_resume(workspace):
    pipeline = FailingPipeline({"First intro", "Second talk"})
    run, ytdlp = start(["a1", "c3", "f6"], pipeline=pipeline)

    snapshot = wait_for(run, "paused")

    assert snapshot.pause_message == playlist_run.FAILED_IN_A_ROW
    assert statuses(snapshot) == [playlist_run.FAILED, playlist_run.FAILED, playlist_run.WAITING]
    assert snapshot.current_video is None
    assert not run.wait(0.3) and ytdlp.downloads == [watch("a1"), watch("c3")]
    assert not Path("output").exists() or not any(Path("output").iterdir())

    pipeline.fail.clear()  # the cause is fixed; Resume runs the video that just failed first (#19)
    run.resume()
    snapshot = finish(run)
    assert snapshot.state == "completed" and snapshot.pause_message == ""
    assert statuses(snapshot) == [playlist_run.FAILED, playlist_run.DONE, playlist_run.DONE]


def test_a_success_between_two_failures_resets_the_count(workspace):
    run, ytdlp = start(["a1", "c3", "f6"], pipeline=FailingPipeline({"First intro", "Third talk"}))

    snapshot = finish(run)

    assert snapshot.state == "completed" and snapshot.pause_message == ""
    assert statuses(snapshot) == [playlist_run.FAILED, playlist_run.DONE, playlist_run.FAILED]
    assert len(ytdlp.downloads) == 3


@pytest.mark.parametrize("message, short", [
    ("", "RuntimeError"),
    ("x" * 1000, "x" * 300),
])
def test_the_error_of_a_video_is_short(workspace, message, short):
    run, _ytdlp = start(["a1"], pipeline=FailingPipeline({"First intro"}, message=message))
    snapshot = finish(run)
    assert {v.video_id: v for v in snapshot.videos}["a1"].error == short


def test_failure_messages_exist_in_every_locale():
    from translations.translations import DISPLAY_LANGUAGES
    keys = {playlist_run.FAILED_IN_A_ROW, "Failed step", "Error"}
    root = Path(__file__).resolve().parents[1] / "translations"
    missing = {language: sorted(keys - json.loads((root / f"{language}.json").read_text(encoding="utf-8")).keys())
               for language in DISPLAY_LANGUAGES.values()}
    assert missing == {language: [] for language in DISPLAY_LANGUAGES.values()}
