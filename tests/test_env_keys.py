"""Keys in .env: config.yaml holds ${VAR} references, the values live in .env or the process environment (custom, #21)."""

import os
import stat
import textwrap

import pytest

from core.utils import config_utils, env_keys
from core.utils.config_errors import ConfigError
from core.utils.config_utils import load_key, load_key_or, update_key

SECRET = "sk-test-0123456789"
VARS = ("VL_TEST_KEY", "VL_OTHER_KEY", "GOOGLE_APPLICATION_CREDENTIALS")


@pytest.fixture
def config(tmp_path, monkeypatch):
    """A temporary config.yaml and the .env beside it; no test variable is set in the process."""
    for var in VARS:  # set then delete: teardown also removes what loading .env put into os.environ
        monkeypatch.setenv(var, "")
        monkeypatch.delenv(var)
    path = tmp_path / "config.yaml"
    path.write_text(textwrap.dedent("""
        # operator comment
        api:
          key: '${VL_TEST_KEY}'  # the LLM key
          base_url: 'https://llm.example.com'
        whisper:
          language: 'en'
          soniox_api_key: '${VL_OTHER_KEY:-}'
        llm_profiles:
          main:
            provider: openrouter
            api_key: '${VL_TEST_KEY}'
    """), encoding="utf-8")
    monkeypatch.setattr(config_utils, "CONFIG_PATH", str(path))
    return path


def write_env(config, text):
    (config.parent / ".env").write_text(textwrap.dedent(text), encoding="utf-8")


def test_a_reference_reads_the_value_from_dotenv_beside_config(config):
    write_env(config, f"VL_TEST_KEY={SECRET}\n")
    assert load_key("api.key") == SECRET
    assert load_key("llm_profiles")["main"]["api_key"] == SECRET


def test_the_process_environment_wins_over_dotenv(config, monkeypatch):
    write_env(config, f"VL_TEST_KEY={SECRET}\n")
    monkeypatch.setenv("VL_TEST_KEY", "from-process")
    assert load_key("api.key") == "from-process"


def test_a_missing_variable_names_the_variable_and_dotenv(config):
    with pytest.raises(ConfigError) as error:
        load_key("api.key")
    assert "VL_TEST_KEY" in str(error.value) and ".env" in str(error.value)
    with pytest.raises(ConfigError):  # load_key_or only hides keys missing from config.yaml
        load_key_or("api.key", "default")


def test_a_reference_with_a_default_reads_the_default_when_unset(config):
    assert load_key("whisper.soniox_api_key") == ""
    assert load_key("whisper")["language"] == "en"


def test_plain_values_are_unchanged(config):
    assert load_key("api.base_url") == "https://llm.example.com"


def read_env(config):
    from dotenv import dotenv_values
    return dotenv_values(config.parent / ".env")


def test_writing_the_value_a_reference_reads_keeps_the_reference(config):
    write_env(config, f"VL_TEST_KEY={SECRET}\n")
    update_key("api.key", load_key("api.key"))
    text = config.read_text(encoding="utf-8")
    assert "'${VL_TEST_KEY}'  # the LLM key" in text and SECRET not in text


def test_writing_a_new_key_over_a_reference_goes_to_dotenv_with_mode_600(config):
    update_key("api.key", "sk-new-'$quoted")
    assert SECRET not in config.read_text(encoding="utf-8")
    assert "sk-new" not in config.read_text(encoding="utf-8")
    assert load_key("api.key") == "sk-new-'$quoted"
    assert read_env(config)["VL_TEST_KEY"] == "sk-new-'$quoted"
    assert stat.S_IMODE(os.stat(config.parent / ".env").st_mode) == 0o600


def test_dotenv_keeps_its_other_lines_when_a_key_is_updated(config):
    write_env(config, "# my keys\nVL_OTHER_KEY=other\nVL_TEST_KEY=old\n")
    update_key("api.key", SECRET)
    assert read_env(config) == {"VL_OTHER_KEY": "other", "VL_TEST_KEY": SECRET}
    assert "# my keys" in (config.parent / ".env").read_text(encoding="utf-8")


def test_writing_a_whole_section_keeps_the_references_inside_it(config):
    write_env(config, f"VL_TEST_KEY={SECRET}\n")
    profiles = load_key("llm_profiles")
    profiles["main"]["model"] = "new-model"
    update_key("llm_profiles", profiles)
    text = config.read_text(encoding="utf-8")
    assert SECRET not in text and "${VL_TEST_KEY}" in text
    assert load_key("llm_profiles.main.model") == "new-model"


def test_a_new_reference_replaces_the_old_one(config):
    update_key("api.key", "${VL_OTHER_KEY:-}")
    assert load_key("api.key", resolve=False) == "${VL_OTHER_KEY:-}"


def test_a_plain_value_is_written_as_before(config):
    update_key("api.base_url", "https://other.example.com")
    assert load_key("api.base_url") == "https://other.example.com"
    assert not (config.parent / ".env").exists()


def test_config_fields_save_keeps_the_reference(config):
    from core.st_utils import config_fields
    config_fields.save("api.key", SECRET)
    assert SECRET not in config.read_text(encoding="utf-8")
    assert read_env(config)["VL_TEST_KEY"] == SECRET


def test_tts_save_settings_keeps_the_reference(config):
    from core.st_utils.tts_settings import save_settings
    config.write_text(config.read_text(encoding="utf-8") + "fish_audio:\n  api_key: '${VL_OTHER_KEY}'\n",
                      encoding="utf-8")
    save_settings({"fish_audio.api_key": SECRET, "openai_tts.api_key": "plain"})
    text = config.read_text(encoding="utf-8")
    assert SECRET not in text and "${VL_OTHER_KEY}" in text
    assert read_env(config)["VL_OTHER_KEY"] == SECRET
    assert load_key("openai_tts.api_key") == "plain"


def test_google_application_credentials_in_dotenv_is_set_before_google_auth_reads_it(config, monkeypatch):
    import google.auth
    from core.utils import google_credentials
    write_env(config, "GOOGLE_APPLICATION_CREDENTIALS=/keys/sa.json\n")
    seen = {}

    def default(scopes=None):
        seen["path"] = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        return type("Credential", (), {"valid": True, "token": "token"})(), "sa-project"

    monkeypatch.setattr(google.auth, "default", default)
    google_credentials.reset()
    try:
        assert google_credentials.access_token() == "token"
    finally:
        google_credentials.reset()
    assert seen["path"] == "/keys/sa.json"
