"""Saving output/ into a chosen history folder keeps what that folder already holds."""
from pathlib import Path

from core.utils.onekeycleanup import cleanup


def test_cleanup_to_a_chosen_folder_merges_into_its_content(tmp_path, monkeypatch):
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

    cleanup(destination=str(destination))

    assert not Path("output").exists()
    assert sorted(p.relative_to(destination).as_posix() for p in destination.rglob("*") if p.is_file()) == [
        ".subtitle_done", "First.mp4", "audio/chunk.wav", "audio/earlier.wav", "earlier.txt",
        "gpt_log/cache.json", "log/earlier.json", "log/translation.json", "trans.srt",
    ]
    assert (destination / "trans.srt").read_text() == "new"
    assert not Path("history/First").exists()
