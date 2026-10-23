"""Tab "Playlist": a `Xong` video can be watched in the tab, from a browser on another machine."""
from streamlit.testing.v1 import AppTest


def _app(root):
    import os

    from core import playlist_run
    from core.st_utils import playlist_tab

    os.chdir(root)

    def video(index, status, folder):
        return playlist_run.VideoSnapshot(video_id=f"v{index}", index=index, title=f"Video {index}", duration=60,
                                          selected=True, status=status, folder=folder)

    videos = (video(1, playlist_run.DONE, "history/P/1 - Video 1"), video(2, playlist_run.DONE, "history/P/2 - Video 2"),
              video(3, playlist_run.RUNNING, "history/P/3 - Video 3"))
    snapshot = playlist_run.RunSnapshot(state="running", url="u", title="P", scope=playlist_run.DUBBING, done=2, total=3,
                                        current_video=videos[2], current_step="", pause_message="", error="",
                                        videos=videos, unfinished=False, active=True)
    playlist_tab._video_viewer(snapshot)


def _run(tmp_path, pick=None):
    for name, files in {"1 - Video 1": ("output_sub.mp4", "output_dub.mp4"), "2 - Video 2": ("output_sub.mp4",)}.items():
        folder = tmp_path / "history" / "P" / name
        folder.mkdir(parents=True)
        for file in files:
            (folder / file).write_bytes(b"\x00")
    at = AppTest.from_function(_app, args=(str(tmp_path),)).run()
    if pick is not None:
        at.selectbox(key="playlist_watch").select(pick).run()
    assert not at.exception
    return at


def test_only_done_videos_can_be_picked(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    at = _run(tmp_path)

    assert at.selectbox(key="playlist_watch").options == ["1. Video 1", "2. Video 2"]


def test_a_done_video_shows_its_subtitle_and_dubbed_videos(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    at = _run(tmp_path)

    assert len(at.get("video")) == 2


def test_a_subtitles_only_video_shows_its_subtitle_video(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    at = _run(tmp_path, pick=2)

    assert len(at.get("video")) == 1
