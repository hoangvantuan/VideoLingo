"""The lock of output/ (#18): a Lượt chạy playlist holds it, the single video mode and the API read it.

Same fakes as tests/test_playlist_run.py: no network, no models, a temporary folder.
"""
import os
import subprocess
import sys
import threading
from pathlib import Path

from core import playlist_run
from core.utils import output_lock
from tests.test_playlist_run import FakePipeline, files, finish, start, watch, workspace  # noqa: F401


def held_during(extra):
    """A pipeline whose translation step waits until the test lets it go."""
    entered, release = threading.Event(), threading.Event()

    def step():
        entered.set()
        assert release.wait(3)
        if extra:
            extra()

    return FakePipeline(extra=step), entered, release


def test_a_run_holds_the_lock_while_it_runs_and_drops_it_once_it_ends(workspace):
    seen = []
    pipeline, entered, release = held_during(lambda: seen.append(output_lock.is_locked()))
    run, _ytdlp = start(["a1", "c3"], pipeline=pipeline)
    assert entered.wait(3)
    assert output_lock.LOCK_FILE.exists() and output_lock.is_locked()

    release.set()
    snapshot = finish(run)

    assert snapshot.state == "completed" and snapshot.done == 2
    assert seen == [True, True]  # held for the second video too
    assert not output_lock.is_locked() and not output_lock.LOCK_FILE.exists()
    assert not Path("output").exists() or not any(Path("output").iterdir())
    assert ".playlist_run.lock" not in files("history")


def test_a_paused_run_keeps_the_lock(workspace):
    pipeline, entered, release = held_during(None)
    run, _ytdlp = start(["a1"], pipeline=pipeline)
    assert entered.wait(3)
    run.pause()
    release.set()
    assert not run.wait(0.3)
    assert output_lock.is_locked()
    run.resume()
    finish(run)
    assert not output_lock.is_locked()


def test_a_run_that_fails_drops_the_lock(workspace):
    def broken():
        raise RuntimeError("quota")

    run, _ytdlp = start(["a1"], pipeline=FakePipeline(extra=broken))
    finish(run)
    assert not output_lock.is_locked() and not output_lock.LOCK_FILE.exists()


def test_a_stopped_run_drops_the_lock(workspace):
    pipeline, entered, release = held_during(None)
    run, _ytdlp = start(["a1", "c3"], pipeline=pipeline)
    assert entered.wait(3)
    run._runner.stop()  # Stop of the tab comes with #16; the task runner stops the same way
    release.set()
    assert finish(run).state == "stopped"
    assert not output_lock.is_locked() and not output_lock.LOCK_FILE.exists()


def write_lock(pid):
    output_lock.LOCK_FILE.parent.mkdir(exist_ok=True)
    output_lock.LOCK_FILE.write_text(str(pid), encoding="utf-8")


def dead_pid():
    process = subprocess.Popen([sys.executable, "-c", "pass"])
    process.wait()
    return process.pid


def test_a_lock_left_by_this_process_without_a_live_run_is_ignored_and_a_run_can_start(workspace):
    write_lock(os.getpid())  # the app crashed in the middle of a run, the process is a new one

    assert not output_lock.is_locked()
    assert not output_lock.LOCK_FILE.exists()

    run, ytdlp = start(["a1"])
    assert finish(run).state == "completed" and ytdlp.downloads == [watch("a1")]


def test_a_lock_left_by_a_dead_process_is_ignored(workspace):
    write_lock(dead_pid())

    assert not output_lock.is_locked()
    run, _ytdlp = start(["a1"])
    assert finish(run).state == "completed"


def test_a_lock_of_another_live_process_is_held(workspace):
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        write_lock(process.pid)  # Streamlit runs the playlist, the API process reads the lock
        assert output_lock.is_locked()
    finally:
        process.kill()
        process.wait()
    assert not output_lock.is_locked()


def test_an_unreadable_lock_is_ignored(workspace):
    write_lock("garbage")
    assert not output_lock.is_locked()

