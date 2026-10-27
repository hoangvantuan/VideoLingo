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
