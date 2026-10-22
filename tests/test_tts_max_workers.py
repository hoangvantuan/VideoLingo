"""tts_max_workers caps parallel TTS requests without touching LLM max_workers (custom fork)."""

import pandas as pd
import pytest


@pytest.mark.parametrize("tts_max_workers, expected", [(1, 1), (0, 4), (None, 4), (8, 4)])
def test_tts_parallelism_is_capped(monkeypatch, tts_max_workers, expected):
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
    monkeypatch.setattr(audio, "load_key", lambda key: "openai_tts" if key == "tts_method" else 4)
    monkeypatch.setattr(audio, "load_key_or", lambda key, default=None: tts_max_workers)
    audio.generate_tts_audio(pd.DataFrame({"number": range(8)}))
    assert seen == [expected]
