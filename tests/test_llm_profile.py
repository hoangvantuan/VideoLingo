"""LLM profile chosen by api.profile, seen through ask_gpt with a fake OpenAI client (custom fork, F7)."""

import importlib
import textwrap
from types import SimpleNamespace

import pytest

from core.utils import config_utils

ask_gpt_module = importlib.import_module("core.utils.ask_gpt")  # core.utils re-exports the function under the same name

KEY_ENV = "VL_TEST_PROFILE_KEY"


class FakeOpenAI:
    clients = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.requests = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        FakeOpenAI.clients.append(self)

    def _create(self, **params):
        self.requests.append(params)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok": 1}'))])


@pytest.fixture
def setup(tmp_path, monkeypatch):
    FakeOpenAI.clients = []
    monkeypatch.setattr(ask_gpt_module, "OpenAI", FakeOpenAI)
    monkeypatch.setattr(ask_gpt_module, "GPT_LOG_FOLDER", str(tmp_path / "gpt_log"))
    monkeypatch.setattr("core.utils.decorator.time.sleep", lambda *_: None)
    monkeypatch.delenv(KEY_ENV, raising=False)
    config = tmp_path / "config.yaml"
    monkeypatch.setattr(config_utils, "CONFIG_PATH", str(config))

    def write(text):
        config.write_text(textwrap.dedent(text), encoding="utf-8")

    return write


def ask(resp_type="json", prompt="hello"):
    result = ask_gpt_module.ask_gpt(prompt, resp_type=resp_type)
    client = FakeOpenAI.clients[-1]
    return result, client.kwargs, client.requests[-1]


CUSTOM_ONLY = """
    api:
      key: 'custom-key'
      base_url: 'https://api.example.com'
      model: 'custom-model'
      llm_support_json: true
    max_workers: 4
"""


def test_config_without_profile_keys_sends_the_upstream_request(setup):
    setup(CUSTOM_ONLY)
    result, client, request = ask()
    assert result == {"ok": 1}
    assert client == {"api_key": "custom-key", "base_url": "https://api.example.com/v1"}
    assert request == {
        "model": "custom-model",
        "messages": [{"role": "user", "content": "hello"}],
        "timeout": 300,
        "response_format": {"type": "json_object"},
    }


WITH_PROFILES = """
    api:
      profile: '{profile}'
      key: 'custom-key'
      base_url: 'https://api.example.com'
      model: 'custom-model'
      llm_support_json: true
    max_workers: 4
    llm_profiles:
      openrouter-free:
        provider: openrouter
        model: 'vendor/free-model:free'
        api_key_env: VL_TEST_PROFILE_KEY
        api_key: 'config-key'
        llm_support_json: false
        max_workers: 1
      thinker:
        provider: openrouter
        model: 'vendor/thinker'
        base_url: 'https://proxy.example.com/v1'
        api_key: 'thinker-key'
        reasoning_effort: low
      keyless:
        provider: openrouter
        model: 'vendor/keyless'
        api_key_env: VL_TEST_PROFILE_KEY
"""


def test_named_profile_sends_its_model_endpoint_and_key(setup):
    setup(WITH_PROFILES.format(profile="openrouter-free"))
    _, client, request = ask()
    assert client == {"api_key": "config-key", "base_url": "https://openrouter.ai/api/v1"}
    assert request["model"] == "vendor/free-model:free"


def test_profile_key_from_environment_wins_over_config(setup, monkeypatch):
    setup(WITH_PROFILES.format(profile="openrouter-free"))
    monkeypatch.setenv(KEY_ENV, "env-key")
    _, client, _ = ask()
    assert client["api_key"] == "env-key"


def test_profile_overrides_json_mode_and_missing_override_uses_api_value(setup):
    setup(WITH_PROFILES.format(profile="openrouter-free"))
    _, _, request = ask()
    assert "response_format" not in request

    setup(WITH_PROFILES.format(profile="thinker"))
    _, client, request = ask(prompt="other")
    assert request["response_format"] == {"type": "json_object"}
    assert client["base_url"] == "https://proxy.example.com/v1"


def test_reasoning_effort_is_sent_only_when_the_profile_declares_it(setup):
    setup(WITH_PROFILES.format(profile="thinker"))
    _, _, request = ask()
    assert request["reasoning_effort"] == "low"

    setup(WITH_PROFILES.format(profile="openrouter-free"))
    _, _, request = ask(prompt="other")
    assert "reasoning_effort" not in request


def test_unknown_profile_error_names_it_and_lists_available_profiles(setup):
    setup(WITH_PROFILES.format(profile="nope"))
    with pytest.raises(ValueError) as error:
        ask_gpt_module.ask_gpt("hello", resp_type="json")
    assert "'nope'" in str(error.value)
    assert "openrouter-free" in str(error.value)
    assert FakeOpenAI.clients == []


def test_profile_without_key_says_where_to_put_it(setup):
    setup(WITH_PROFILES.format(profile="keyless"))
    with pytest.raises(ValueError) as error:
        ask_gpt_module.ask_gpt("hello", resp_type="json")
    message = str(error.value)
    assert "'keyless'" in message
    assert KEY_ENV in message
    assert "llm_profiles.keyless.api_key" in message
    assert FakeOpenAI.clients == []


def test_custom_profile_on_local_server_still_needs_no_key(setup):
    setup(CUSTOM_ONLY.replace("'custom-key'", "''").replace("https://api.example.com", "http://localhost:11434"))
    _, client, _ = ask()
    assert client == {"api_key": "not-needed", "base_url": "http://localhost:11434/v1"}


def test_empty_profile_name_uses_the_custom_profile_even_with_profiles_declared(setup):
    setup(WITH_PROFILES.format(profile=""))
    _, client, request = ask()
    assert client == {"api_key": "custom-key", "base_url": "https://api.example.com/v1"}
    assert request["model"] == "custom-model"
