"""tts_max_workers caps parallel TTS requests without touching LLM max_workers (custom fork)."""

import pandas as pd
import pytest


def tts_parallelism(monkeypatch, tts_method, max_workers, values):
    """Run generate_tts_audio with fake config and report the worker count it used."""
    from core import _10_gen_audio as audio
    seen, real_executor = [], audio.ThreadPoolExecutor

    class Executor:
        def __init__(self, max_workers):
            seen.append(max_workers)
            self.inner = real_executor(max_workers=max_workers)

        def __enter__(self):
            return self.inner.__enter__()

        def __exit__(self, *args):
            return self.inner.__exit__(*args)

    monkeypatch.setattr(audio, "ThreadPoolExecutor", Executor)
    monkeypatch.setattr(audio, "process_row", lambda row, tasks: (row["number"], 1.0))
    monkeypatch.setattr(audio, "load_key", lambda key: tts_method if key == "tts_method" else max_workers)
    monkeypatch.setattr(audio, "load_key_or", lambda key, default=None: values.get(key, default))
    audio.generate_tts_audio(pd.DataFrame({"number": range(8)}))
    return seen


@pytest.mark.parametrize("tts_max_workers, expected", [(1, 1), (0, 4), (None, 4), (8, 4)])
def test_tts_parallelism_is_capped(monkeypatch, tts_max_workers, expected):
    assert tts_parallelism(monkeypatch, "openai_tts", 4, {"tts_max_workers": tts_max_workers}) == [expected]


@pytest.mark.parametrize("vertex_max_workers, expected", [(6, 6), (None, 4)])
def test_vertex_tts_max_workers_replaces_the_tts_parallelism(monkeypatch, vertex_max_workers, expected):
    """With vertex_tts, vertex_tts.max_workers wins over both max_workers and tts_max_workers."""
    values = {"tts_max_workers": 1, "vertex_tts.max_workers": vertex_max_workers}
    assert tts_parallelism(monkeypatch, "vertex_tts", 1, values) == [expected]
