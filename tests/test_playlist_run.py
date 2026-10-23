"""Lượt chạy playlist through its public interface, with a fake yt-dlp and a fake pipeline.

No network and no models: the fake yt-dlp returns fixed yt-dlp style dicts and writes an
empty mp4 into output/, the fake pipeline writes markers. Each test runs in a temporary folder.
"""
import json
import threading
from pathlib import Path

import pytest
import yaml

from core import playlist_run
from core.task_runner import TaskRunner

URL = "https://www.youtube.com/playlist?list=PL1"
CHANNEL = "https://www.youtube.com/@someone"


def watch(video_id):
    return f"https://www.youtube.com/watch?v={video_id}"


def entry(video_id, title, duration=None, **extra):
    return {"_type": "url", "ie_key": "Youtube", "id": video_id, "title": title,
            "duration": duration, "url": watch(video_id), **extra}


PLAYLIST = {
    "_type": "playlist", "id": "PL1", "title": "Talks: 2026/10", "webpage_url": URL,
    "entries": [
        entry("a1", "First: intro?", 61),
        entry("p2", "[Private video]"),
        entry("c3", "Second talk", 120.0),
        entry("d4", "[Deleted video]"),
        entry("e5", "Members only", 30, availability="subscriber_only"),
        entry("f6", "Third talk", 45),
    ],
}


class FakeYtdlp:
    """Reads fixed playlists; a download writes an empty mp4 named after the video into output/."""

    def __init__(self, infos):
        self.infos = infos
        self.downloads = []

    def extract_flat(self, url):
        return self.infos[url]

    def download(self, url):
        self.downloads.append(url)
        titles = {e["url"]: e["title"] for info in self.infos.values() for e in info.get("entries", [])}
        Path("output").mkdir(exist_ok=True)
        Path("output", f"{titles[url]}.mp4".replace(":", "").replace("?", "")).write_bytes(b"")


class FakePipeline:
    """Steps that write a marker into output/ and log/ like the real ones; records the plan asked for."""

    def __init__(self, extra=None):
        self.plans = []
        self.extra = extra

    def __call__(self, stage, dubbing):
        self.plans.append((stage, dubbing))
        def transcribe():
            Path("output/log").mkdir(parents=True, exist_ok=True)
            Path("output/log/asr.json").write_text("{}")
        def translate():
            Path("output/gpt_log").mkdir(parents=True, exist_ok=True)
            Path("output/gpt_log/cache.json").write_text("{}")
            if self.extra:
                self.extra()
            Path("output/trans.srt").write_text("subtitles")
        steps = [("Word-level transcription and alignment", transcribe),
                 ("Summarization and multi-step translation", translate)]
        if dubbing:
            steps.append(("Merge full audio", lambda: Path("output/dub.mp3").write_bytes(b"")))
        return steps


CONFIG = {
    "allowed_video_formats": ["mp4"], "allowed_audio_formats": ["wav", "mp3"],
    "ytb_resolution": "360", "youtube": {"proxy": None, "cookies_path": ""},
    "pause_before_translate": False, "pause_after_translate": False,
}


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("config.yaml").write_text(yaml.safe_dump(CONFIG), encoding="utf-8")
    monkeypatch.setattr(playlist_run, "_current", None)
    yield tmp_path
    run = playlist_run.current_run()
    if run:  # the run has no Stop yet (#16); end the thread the way the task runner does
        run._runner.stop()
        assert run.wait(3)
    assert TaskRunner._current is None


def finish(run):
    assert run.wait(5), "the run did not finish"
    return run.snapshot()


def test_read_playlist_lists_videos_with_index_title_duration_and_availability(workspace):
    playlist = playlist_run.read_playlist(URL, ytdlp=FakeYtdlp({URL: PLAYLIST}))

    assert playlist.url == URL and playlist.title == "Talks: 2026/10"
    assert [(v.video_id, v.index, v.title, v.duration, v.available) for v in playlist.videos] == [
        ("a1", 1, "First: intro?", 61, True),
        ("p2", 2, "[Private video]", None, False),
        ("c3", 3, "Second talk", 120.0, True),
        ("d4", 4, "[Deleted video]", None, False),
        ("e5", 5, "Members only", 30, False),
        ("f6", 6, "Third talk", 45, True),
    ]


def start(selected, scope=playlist_run.SUBTITLES, pipeline=None, ytdlp=None):
    ytdlp = ytdlp or FakeYtdlp({URL: PLAYLIST})
    playlist = playlist_run.read_playlist(URL, ytdlp=ytdlp)
    run = playlist_run.PlaylistRun.create(playlist, selected, scope, ytdlp=ytdlp, plan=pipeline or FakePipeline())
    run.start()
    return run, ytdlp


def files(folder):
    return sorted(p.relative_to(folder).as_posix() for p in Path(folder).rglob("*") if p.is_file())


def test_run_processes_every_selected_video_into_its_history_folder(workspace):
    pipeline = FakePipeline()
    run, ytdlp = start(["a1", "c3", "f6"], playlist_run.DUBBING, pipeline)
    assert playlist_run.current_run() is run

    snapshot = finish(run)

    assert snapshot.state == "completed" and (snapshot.done, snapshot.total) == (3, 3)
    assert snapshot.current_video is None
    assert ytdlp.downloads == [watch("a1"), watch("c3"), watch("f6")]
    assert pipeline.plans == [("all", True)] * 3
    root = Path("history/Talks_ 2026_10")
    assert sorted(p.name for p in root.iterdir()) == [
        "1 - First_ intro_", "3 - Second talk", "6 - Third talk", "playlist_run.json"]
    assert files(root / "1 - First_ intro_") == [
        "First intro.mp4", "dub.mp3", "gpt_log/cache.json", "log/asr.json", "trans.srt"]
    assert not Path("output").exists() or not any(Path("output").iterdir())
    videos = {v.video_id: v for v in snapshot.videos}
    assert [v.status for v in snapshot.videos] == [
        playlist_run.DONE, playlist_run.UNAVAILABLE, playlist_run.DONE,
        playlist_run.UNAVAILABLE, playlist_run.UNAVAILABLE, playlist_run.DONE]
    assert videos["c3"].folder == str(root / "3 - Second talk")

    state = json.loads((root / "playlist_run.json").read_text(encoding="utf-8"))
    assert (state["url"], state["title"], state["scope"], state["state"]) == (
        URL, "Talks: 2026/10", playlist_run.DUBBING, "finished")
    assert [(v["video_id"], v["status"], v["folder"]) for v in state["videos"]] == [
        ("a1", "done", "1 - First_ intro_"), ("p2", "unavailable", None), ("c3", "done", "3 - Second talk"),
        ("d4", "unavailable", None), ("e5", "unavailable", None), ("f6", "done", "6 - Third talk")]


def test_subtitles_scope_asks_for_subtitles_only(workspace):
    pipeline = FakePipeline()
    run, _ytdlp = start(["a1"], playlist_run.SUBTITLES, pipeline)
    finish(run)
    assert pipeline.plans == [("all", False)]
    assert not Path("history/Talks_ 2026_10/1 - First_ intro_/dub.mp3").exists()


def test_deselected_and_unavailable_videos_are_not_processed(workspace):
    run, ytdlp = start(["a1", "p2", "e5"])

    snapshot = finish(run)

    assert ytdlp.downloads == [watch("a1")]
    assert (snapshot.done, snapshot.total) == (1, 1)
    videos = {v.video_id: v for v in snapshot.videos}
    assert (videos["c3"].selected, videos["c3"].status, videos["c3"].folder) == (False, playlist_run.WAITING, None)
    assert (videos["p2"].selected, videos["p2"].status) == (False, playlist_run.UNAVAILABLE)
    assert (videos["e5"].selected, videos["e5"].status) == (False, playlist_run.UNAVAILABLE)
    assert sorted(p.name for p in Path("history/Talks_ 2026_10").iterdir()) == ["1 - First_ intro_", "playlist_run.json"]


def test_start_is_refused_while_output_holds_another_video(workspace):
    Path("output/log").mkdir(parents=True)
    Path("output/log/terminology.json").write_text("{}")
    ytdlp = FakeYtdlp({URL: PLAYLIST})
    run = playlist_run.PlaylistRun.create(playlist_run.read_playlist(URL, ytdlp=ytdlp), ["a1"],
                                          playlist_run.SUBTITLES, ytdlp=ytdlp, plan=FakePipeline())

    with pytest.raises(playlist_run.PlaylistRunError) as refused:
        run.start()

    assert str(refused.value) == playlist_run.OUTPUT_NOT_EMPTY
    assert "history" in str(refused.value) and "delete" in str(refused.value)
    assert ytdlp.downloads == [] and playlist_run.current_run() is None
    assert files("output") == ["log/terminology.json"]
    assert not Path("history").exists()


def test_review_checkpoints_do_not_pause_a_run_even_when_enabled(workspace):
    from core import pipeline
    config = yaml.safe_dump({**CONFIG, "pause_before_translate": True, "pause_after_translate": True})
    Path("config.yaml").write_text(config, encoding="utf-8")

    def reviews():
        pipeline.review_terminology()
        pipeline.review_translation()

    run, _ytdlp = start(["a1", "c3"], pipeline=FakePipeline(extra=reviews))

    snapshot = finish(run)
    assert snapshot.state == "completed" and snapshot.done == 2
    assert Path("config.yaml").read_text(encoding="utf-8") == config


def test_pause_holds_the_run_until_resume_and_any_holder_controls_it(workspace):
    entered, release = threading.Event(), threading.Event()

    def slow():
        entered.set()
        assert release.wait(3)

    run, ytdlp = start(["a1", "c3"], pipeline=FakePipeline(extra=slow))
    assert entered.wait(3)
    snapshot = run.snapshot()
    assert (snapshot.current_video.video_id, snapshot.current_step) == (
        "a1", "Summarization and multi-step translation")
    assert (snapshot.done, snapshot.total) == (0, 2)

    # Another browser tab, or the page after F5, finds the same run
    playlist_run.current_run().pause()
    release.set()
    assert not run.wait(0.3)
    assert run.snapshot().state == "paused" and ytdlp.downloads == [watch("a1")]

    playlist_run.current_run().resume()
    snapshot = finish(run)
    assert snapshot.state == "completed" and snapshot.done == 2


def test_a_second_run_is_refused_while_one_is_active(workspace):
    release = threading.Event()
    run, _ytdlp = start(["a1"], pipeline=FakePipeline(extra=lambda: release.wait(3)))
    ytdlp = FakeYtdlp({URL: PLAYLIST})
    other = playlist_run.PlaylistRun.create(playlist_run.read_playlist(URL, ytdlp=ytdlp), ["c3"],
                                            playlist_run.SUBTITLES, ytdlp=ytdlp, plan=FakePipeline())
    try:
        with pytest.raises(playlist_run.PlaylistRunError, match="already active"):
            other.start()
        assert playlist_run.current_run() is run
    finally:
        release.set()
    finish(run)


def test_channel_tabs_are_read_as_one_playlist(workspace):
    videos_tab = CHANNEL + "/videos"
    shorts_tab = CHANNEL + "/shorts"
    channel = {"_type": "playlist", "id": "UC1", "title": "Someone", "entries": [
        {"_type": "url", "ie_key": "YoutubeTab", "url": videos_tab, "title": "Someone - Videos"},
        {"_type": "url", "ie_key": "YoutubeTab", "url": shorts_tab, "title": "Someone - Shorts"},
    ]}
    tabs = {
        videos_tab: {"_type": "playlist", "entries": [entry("v1", "Long one", 600), entry("v2", "Long two", 700)]},
        shorts_tab: {"_type": "playlist", "entries": [entry("s1", "Short", 20), entry("v1", "Long one", 600)]},
    }
    playlist = playlist_run.read_playlist(CHANNEL, ytdlp=FakeYtdlp({CHANNEL: channel, **tabs}))
    assert playlist.title == "Someone"
    assert [(v.video_id, v.index) for v in playlist.videos] == [("v1", 1), ("v2", 2), ("s1", 3)]


def test_ytdlp_reads_flat_with_the_proxy_and_cookies_and_downloads_with_the_existing_downloader(workspace, monkeypatch):
    import yt_dlp
    from core import _1_ytdlp
    Path("cookies.txt").write_text("# Netscape HTTP Cookie File\n")
    Path("config.yaml").write_text(yaml.safe_dump(
        {**CONFIG, "youtube": {"proxy": " socks5://proxy.example.com:1080 ", "cookies_path": "cookies.txt"}}),
        encoding="utf-8")
    recorded = {}

    class YoutubeDL:
        def __init__(self, options):
            recorded["options"] = options
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def extract_info(self, url, download):
            recorded["call"] = (url, download)
            return PLAYLIST

    monkeypatch.setattr(yt_dlp, "YoutubeDL", YoutubeDL)
    downloads = []
    monkeypatch.setattr(_1_ytdlp, "download_video_ytdlp", lambda url, **kwargs: downloads.append((url, kwargs)))

    playlist = playlist_run.read_playlist(URL)
    playlist_run.Ytdlp().download(playlist.videos[0].url)

    assert recorded["call"] == (URL, False)
    options = recorded["options"]
    assert options["extract_flat"] == "in_playlist"
    assert (options["proxy"], options["cookiefile"]) == ("socks5://proxy.example.com:1080", "cookies.txt")
    assert downloads == [(watch("a1"), {"resolution": "360"})]
