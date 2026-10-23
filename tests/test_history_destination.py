"""Saving output/ into a chosen history folder keeps what that folder already holds."""
from pathlib import Path

from core.utils.history_folder import merge_output


def test_merge_output_into_a_chosen_folder_keeps_its_content(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    destination = Path("history/My list/01 - First")
    (destination / "log").mkdir(parents=True)
    (destination / "audio").mkdir()
    (destination / "earlier.txt").write_text("earlier")
    (destination / "log" / "earlier.json").write_text("{}")
    (destination / "audio" / "earlier.wav").write_text("audio")
    (destination / "trans.srt").write_text("old")
    for folder in ("log", "gpt_log", "audio"):
        Path("output", folder).mkdir(parents=True)
    Path("output/First.mp4").write_text("video")
    Path("output/.subtitle_done").touch()
    Path("output/trans.srt").write_text("new")
    Path("output/log/translation.json").write_text("{}")
    Path("output/gpt_log/cache.json").write_text("{}")
    Path("output/audio/chunk.wav").write_text("chunk")

    merge_output(destination)

    assert not Path("output").exists()
    assert sorted(p.relative_to(destination).as_posix() for p in destination.rglob("*") if p.is_file()) == [
        ".subtitle_done", "First.mp4", "audio/chunk.wav", "audio/earlier.wav", "earlier.txt",
        "gpt_log/cache.json", "log/earlier.json", "log/translation.json", "trans.srt",
    ]
    assert (destination / "trans.srt").read_text() == "new"
    assert not Path("history/First").exists()


def test_merge_output_leaves_the_excluded_files_in_output(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("output/log").mkdir(parents=True)
    Path("output/.playlist_run.lock").write_text("1")
    Path("output/log/.playlist_run.lock").write_text("not the lock")
    Path("output/First.mp4").write_text("video")

    merge_output("history/First", exclude=(".playlist_run.lock",))

    assert [p.as_posix() for p in Path("output").rglob("*")] == ["output/.playlist_run.lock"]
    assert sorted(p.name for p in Path("history/First").rglob("*") if p.is_file()) == [".playlist_run.lock", "First.mp4"]
