"""Reading a Playlist again (#17): videos `Xong` in an earlier run are marked and not selected.

The videos are matched by their YouTube video ID through the state file in
``history/<playlist>/``, so a new video at the top of the playlist, which shifts the index of
every other video, does not change which videos are `Xong`.
"""
import json
from pathlib import Path

from core import playlist_run
from tests.test_playlist_run import URL, FakePipeline, FakeYtdlp, entry, finish, watch, workspace  # noqa: F401

ROOT = Path("history/Talks")


def playlist(*entries):
    return {"_type": "playlist", "id": "PL1", "title": "Talks", "webpage_url": URL, "entries": list(entries)}


FIRST = playlist(entry("a1", "Alpha", 60), entry("b2", "Beta", 60), entry("c3", "Gamma", 60))


def run_to_end(ytdlp, selected, pipeline=None):
    run = playlist_run.PlaylistRun.create(
        playlist_run.read_playlist(URL, ytdlp=ytdlp), selected, playlist_run.SUBTITLES,
        ytdlp=ytdlp, plan=pipeline or FakePipeline())
    run.start()
    snapshot = finish(run)
    assert snapshot.state == "completed"
    return snapshot


def marks(ytdlp):
    return [(v.video_id, v.index, v.done) for v in playlist_run.read_playlist(URL, ytdlp=ytdlp).videos]


def test_videos_done_in_an_earlier_run_are_marked_even_when_the_order_changed(workspace):
    ytdlp = FakeYtdlp({URL: FIRST})
    run_to_end(ytdlp, ["a1", "c3"])

    # The channel published "New" at the top, and "Gamma" moved before "Beta"
    ytdlp.infos[URL] = playlist(entry("n0", "New", 60), entry("a1", "Alpha", 60),
                                entry("c3", "Gamma", 60), entry("b2", "Beta", 60))

    assert marks(ytdlp) == [("n0", 1, False), ("a1", 2, True), ("c3", 3, True), ("b2", 4, False)]


def test_a_playlist_never_run_has_no_video_done(workspace):
    assert marks(FakeYtdlp({URL: FIRST})) == [("a1", 1, False), ("b2", 2, False), ("c3", 3, False)]


def test_a_second_run_of_the_new_videos_keeps_the_earlier_videos_done(workspace):
    ytdlp = FakeYtdlp({URL: FIRST})
    run_to_end(ytdlp, ["a1", "b2", "c3"])
    ytdlp.infos[URL] = playlist(entry("n0", "New", 60), *FIRST["entries"])
    ytdlp.downloads.clear()

    snapshot = run_to_end(ytdlp, ["n0"])

    assert ytdlp.downloads == [watch("n0")]
    assert (snapshot.done, snapshot.total) == (1, 1)
    assert sorted(p.name for p in ROOT.iterdir()) == [
        "1 - Alpha", "1 - New", "2 - Beta", "3 - Gamma", "playlist_run.json"]
    # A third reading still knows the videos of the first run
    assert marks(ytdlp) == [("n0", 1, True), ("a1", 2, True), ("b2", 3, True), ("c3", 4, True)]


def test_a_done_video_selected_again_is_processed_again_into_its_own_folder(workspace):
    ytdlp = FakeYtdlp({URL: FIRST})
    run_to_end(ytdlp, ["a1", "b2"])
    ytdlp.infos[URL] = playlist(entry("n0", "New", 60), *FIRST["entries"])
    ytdlp.downloads.clear()
    pipeline = FakePipeline()

    snapshot = run_to_end(ytdlp, ["a1", "n0"], pipeline)

    assert ytdlp.downloads == [watch("n0"), watch("a1")]
    assert len(pipeline.plans) == 2
    videos = {v.video_id: v for v in snapshot.videos}
    assert videos["a1"].folder == str(ROOT / "1 - Alpha")  # its folder, not "2 - Alpha"
    assert videos["n0"].folder == str(ROOT / "1 - New")
    assert (ROOT / "1 - Alpha" / "trans.srt").exists()
    assert not Path("output").exists() or not any(Path("output").iterdir())
    assert marks(ytdlp) == [("n0", 1, True), ("a1", 2, True), ("b2", 3, True), ("c3", 4, False)]


def test_a_new_video_never_gets_the_folder_of_another_video(workspace):
    ytdlp = FakeYtdlp({URL: playlist(entry("a1", "Talk", 60), entry("b2", "Other", 60))})
    run_to_end(ytdlp, ["a1"])
    # "a1" left the playlist; a new video with the same title takes index 1
    ytdlp.infos[URL] = playlist(entry("z9", "Talk", 60), entry("b2", "Other", 60))

    snapshot = run_to_end(ytdlp, ["z9", "b2"])

    videos = {v.video_id: v for v in snapshot.videos}
    assert videos["z9"].folder not in (str(ROOT / "1 - Talk"), None)
    assert Path(videos["z9"].folder).parent == ROOT
    assert sorted(p.name for p in (ROOT / "1 - Talk").iterdir()) == ["Talk.mp4", "gpt_log", "log", "trans.srt"]
    assert (Path(videos["z9"].folder) / "trans.srt").exists()
    folders = [v.folder for v in snapshot.videos if v.folder]
    assert len(folders) == len(set(folders))


def test_the_state_file_keeps_done_videos_that_are_not_selected(workspace):
    ytdlp = FakeYtdlp({URL: FIRST})
    run_to_end(ytdlp, ["a1"])

    run_to_end(ytdlp, ["b2"])

    state = json.loads((ROOT / "playlist_run.json").read_text(encoding="utf-8"))
    assert [(v["video_id"], v["selected"], v["status"], v["folder"]) for v in state["videos"]] == [
        ("a1", False, "done", "1 - Alpha"), ("b2", True, "done", "2 - Beta"), ("c3", False, "waiting", None)]
