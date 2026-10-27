"""Tests for TTS-only text normalization in clean_text_for_tts."""

from core.tts_backend.tts_main import clean_text_for_tts


def test_clean_text_for_tts_separates_file_extensions_without_touching_numbers_or_periods():
    assert clean_text_for_tts("file agents.md hay claude.md,") == "file agents md hay claude md,"
    assert (
        clean_text_for_tts(
            "như codingstandards.md, config.yaml, config.yml, main.py, package.json, "
            "index.ts, App.tsx, app.js, notes.txt, skills.sh, pyproject.toml."
        )
        == "như codingstandards md, config yaml, config yml, main py, package json, "
        "index ts, App tsx, app js, notes txt, skills sh, pyproject toml."
    )
    assert (
        clean_text_for_tts("Tốc độ 1.4 ở bản v1.2.0 đã ổn định.")
        == "Tốc độ 1.4 ở bản v1.2.0 đã ổn định."
    )


def test_clean_text_for_tts_strips_leading_and_trailing_ellipsis_only():
    assert clean_text_for_tts("...khi có các ticket,") == "khi có các ticket,"
    assert clean_text_for_tts("thì prompt skill này sẽ thực sự...") == "thì prompt skill này sẽ thực sự"
    assert clean_text_for_tts("… rất hữu ích…") == "rất hữu ích"
    assert clean_text_for_tts("... ... rất hữu ích ... …") == "rất hữu ích"
    assert clean_text_for_tts(".. bắt đầu bằng hai chấm ..") == "bắt đầu bằng hai chấm"
    assert clean_text_for_tts(". . . khi có các ticket . . .") == "khi có các ticket"
    assert clean_text_for_tts("“...khi có các ticket,”") == "“khi có các ticket,”"
    assert clean_text_for_tts("“thì thực sự...”") == "“thì thực sự”"
    assert clean_text_for_tts("(...rất hữu ích...)") == "(rất hữu ích)"
    assert clean_text_for_tts("nói….") == "nói."
    assert clean_text_for_tts("nói…,") == "nói,"
    assert clean_text_for_tts("ờ ...!") == "ờ!"
    assert clean_text_for_tts("“ờ ...?”") == "“ờ?”"
    assert clean_text_for_tts("agents.md...") == "agents md"
    assert clean_text_for_tts("...agents.md...") == "agents md"
    assert clean_text_for_tts("kiểu như... thì") == "kiểu như... thì"
    assert clean_text_for_tts("...") == ""
    assert clean_text_for_tts("…") == ""
    assert clean_text_for_tts(". . .") == ""
    assert clean_text_for_tts("chạy được.") == "chạy được."
    assert clean_text_for_tts("phiên bản 1.4") == "phiên bản 1.4"
    assert clean_text_for_tts("v1.2.0") == "v1.2.0"


def test_tts_main_creates_silence_when_ellipsis_only_line_becomes_empty(monkeypatch, tmp_path):
    from core.tts_backend import tts_main as tts_module

    monkeypatch.setattr(
        tts_module,
        "load_key",
        lambda *a, **kw: (_ for _ in ()).throw(AssertionError("TTS backend must not be called")),
    )
    out = tmp_path / "ellipsis_only.wav"
    tts_module.tts_main("... … ...", str(out), 1, None)
    assert out.exists()

