"""Key boxes of the sidebar with ${VAR} references, driven through Streamlit's AppTest (custom, #21)."""

import textwrap

import pytest
from streamlit.testing.v1 import AppTest

from core.utils import config_utils
from core.utils.config_utils import load_key

SECRET = "sk-test-0123456789"
VARS = ("VL_TEST_KEY", "VL_OTHER_KEY")


def _app():
    from core.st_utils.key_input import key_input

    key_input("API key", "api.key", widget_key="api_key")
    key_input("Other key", "whisper.mai_api_key", widget_key="mai_key")


@pytest.fixture
def config(tmp_path, monkeypatch):
    for var in VARS:  # set then delete: teardown also removes what loading .env put into os.environ
        monkeypatch.setenv(var, "")
        monkeypatch.delenv(var)
    path = tmp_path / "config.yaml"
    path.write_text(textwrap.dedent("""
        api:
          key: '${VL_TEST_KEY}'
        whisper:
          mai_api_key: 'plain-key'
    """), encoding="utf-8")
    (tmp_path / ".env").write_text(f"VL_TEST_KEY={SECRET}\n", encoding="utf-8")
    monkeypatch.setattr(config_utils, "CONFIG_PATH", str(path))
    return path


def run():
    return AppTest.from_function(_app).run()


def test_a_referenced_key_shows_its_variable_and_not_its_value(config):
    at = run()
    box = at.text_input(key="api_key")
    assert box.value == "" and SECRET not in str(box.placeholder)
    assert any("VL_TEST_KEY" in caption.value for caption in at.caption)
    assert all(SECRET not in str(element.value) for element in list(at.caption) + list(at.markdown))


def test_a_new_key_in_a_referenced_box_goes_to_dotenv(config):
    at = run()
    at.text_input(key="api_key").input("sk-new").run()
    assert not at.exception
    text = config.read_text(encoding="utf-8")
    assert "${VL_TEST_KEY}" in text and "sk-new" not in text
    assert "VL_TEST_KEY='sk-new'" in (config.parent / ".env").read_text(encoding="utf-8")
    assert load_key("api.key") == "sk-new"


def test_a_key_without_reference_is_masked_and_saved_as_before(config):
    at = run()
    box = at.text_input(key="mai_key")
    assert box.value == "plain-key" and box.proto.type == box.proto.PASSWORD
    box.input("other-plain").run()
    assert load_key("whisper.mai_api_key") == "other-plain"


def _tts_app():
    from core.st_utils.tts_settings import select_tts_method

    select_tts_method({"fish_audio": "Fish Audio"})


def test_a_referenced_tts_provider_key_goes_to_dotenv(config):
    config.write_text(config.read_text(encoding="utf-8")
                      + "tts_method: fish_audio\nfish_audio:\n  api_key: '${VL_TEST_KEY}'\n", encoding="utf-8")
    at = AppTest.from_function(_tts_app).run()
    box = at.text_input[0]
    assert box.value == "" and any("VL_TEST_KEY" in caption.value for caption in at.caption)
    box.input("sk-tts").run()
    assert not at.exception
    assert "${VL_TEST_KEY}" in config.read_text(encoding="utf-8")
    assert load_key("fish_audio.api_key") == "sk-tts"


def _editor_app():
    from core.st_utils import llm_profile_editor

    llm_profile_editor.render()


def editor_widget(at, label):
    return next(widget for widget in [*at.text_input, *at.selectbox, *at.button] if widget.label == label)


@pytest.fixture
def profile_config(config):
    config.write_text(config.read_text(encoding="utf-8") + textwrap.dedent("""
        llm_profiles:
          main:
            provider: openrouter
            model: 'old-model'
            api_key: '${VL_TEST_KEY}'
    """), encoding="utf-8")
    at = AppTest.from_function(_editor_app).run()
    at = at.toggle[0].set_value(True).run()
    return editor_widget(at, "Sửa profile").select("main").run()


def test_the_profile_editor_shows_the_variable_of_a_referenced_key(config, profile_config):
    at = profile_config
    assert editor_widget(at, "API key (dự phòng)").value == ""
    assert any("VL_TEST_KEY" in caption.value for caption in at.caption)


def test_saving_a_profile_keeps_its_referenced_key(config, profile_config):
    at = profile_config
    editor_widget(at, "Model").input("new-model")
    at = editor_widget(at, "💾 Lưu profile").click().run()
    assert not at.exception
    text = config.read_text(encoding="utf-8")
    assert "${VL_TEST_KEY}" in text and SECRET not in text
    assert load_key("llm_profiles.main.model") == "new-model"


def test_a_new_key_typed_in_the_profile_editor_goes_to_dotenv(config, profile_config):
    at = profile_config
    editor_widget(at, "API key (dự phòng)").input("sk-profile")
    at = editor_widget(at, "💾 Lưu profile").click().run()
    assert not at.exception
    assert "sk-profile" not in config.read_text(encoding="utf-8")
    assert load_key("llm_profiles.main.api_key") == "sk-profile"


def test_an_unset_variable_of_a_sibling_tts_method_does_not_break_the_key_box(config):
    config.write_text(config.read_text(encoding="utf-8") + textwrap.dedent("""
        tts_method: sf_fish_tts
        sf_fish_tts:
          api_key: 'plain-sf'
        sf_cosyvoice2:
          api_key: '${VL_OTHER_KEY}'
    """), encoding="utf-8")
    at = AppTest.from_function(_sf_app).run()
    assert not at.exception
    assert at.text_input[0].value == "plain-sf"


def _sf_app():
    from core.st_utils.tts_settings import select_tts_method

    select_tts_method({"sf_fish_tts": "Fish TTS", "sf_cosyvoice2": "CosyVoice2"})
