"""Vertex LLM profile seen through ask_gpt, with a fake OpenAI client and a fake Google credential (custom fork, F8)."""

import importlib
import textwrap
from types import SimpleNamespace

import pytest

from core.utils import config_utils, google_credentials

ask_gpt_module = importlib.import_module("core.utils.ask_gpt")  # core.utils re-exports the function under the same name


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


class FakeCredential:
    """Stands in for google.auth credentials: `valid` turns False when the token expires."""

    def __init__(self):
        self.valid = False
        self.token = None
        self.refreshes = 0

    def refresh(self, request):
        self.refreshes += 1
        self.token = f"token-{self.refreshes}"
        self.valid = True


CONFIG = """
    api:
      profile: '{profile}'
      key: 'custom-key'
      base_url: 'https://api.example.com'
      model: 'custom-model'
      llm_support_json: false
    max_workers: 4
    llm_profiles:
      gemini-lite:
        provider: vertex
        model: 'google/gemini-3.5-flash-lite'
      gemini-flash:
        provider: vertex
        model: 'google/gemini-3.8-flash'
        reasoning_effort: low
    vertex:
      project: '{project}'
      location_llm: '{location}'
"""


@pytest.fixture
def setup(tmp_path, monkeypatch):
    FakeOpenAI.clients = []
    monkeypatch.setattr(ask_gpt_module, "OpenAI", FakeOpenAI)
    monkeypatch.setattr(ask_gpt_module, "GPT_LOG_FOLDER", str(tmp_path / "gpt_log"))
    monkeypatch.setattr("core.utils.decorator.time.sleep", lambda *_: None)
    config = tmp_path / "config.yaml"
    monkeypatch.setattr(config_utils, "CONFIG_PATH", str(config))
    google_credentials.reset()
    credential = FakeCredential()
    monkeypatch.setattr(google_credentials, "_load_default", lambda: (credential, "sa-project"))
    yield lambda profile="gemini-lite", project="my-project", location="global": (
        config.write_text(textwrap.dedent(CONFIG.format(profile=profile, project=project, location=location)),
                          encoding="utf-8"),
        credential,
    )[1]
    google_credentials.reset()


def ask(prompt="hello", resp_type="json"):
    result = ask_gpt_module.ask_gpt(prompt, resp_type=resp_type)
    client = FakeOpenAI.clients[-1]
    return result, client.kwargs, client.requests[-1]


def test_vertex_profile_calls_the_openai_endpoint_of_the_project_with_a_bearer_token(setup):
    setup()
    result, client, request = ask()
    assert result == {"ok": 1}
    assert client == {
        "api_key": "token-1",  # the OpenAI client sends it as "Authorization: Bearer token-1"
        "base_url": "https://aiplatform.googleapis.com/v1/projects/my-project/locations/global/endpoints/openapi",
    }
    assert request["model"] == "google/gemini-3.5-flash-lite"


def test_project_containing_ark_is_not_rewritten_by_base_url_normalization(setup):
    setup(project="park-412")
    _, client, _ = ask()
    assert client["base_url"] == "https://aiplatform.googleapis.com/v1/projects/park-412/locations/global/endpoints/openapi"


def test_regional_location_uses_the_regional_host(setup):
    setup(location="us-central1")
    _, client, _ = ask()
    assert client["base_url"] == (
        "https://us-central1-aiplatform.googleapis.com/v1/projects/my-project/locations/us-central1/endpoints/openapi")


def test_expired_token_is_refreshed_between_two_calls(setup):
    credential = setup()
    _, first, _ = ask("one")
    _, again, _ = ask("two")
    credential.valid = False  # the hour is up
    _, refreshed, _ = ask("three")
    assert (first["api_key"], again["api_key"], refreshed["api_key"]) == ("token-1", "token-1", "token-2")


def test_json_mode_is_on_for_vertex_even_when_api_turns_it_off(setup):
    setup()
    _, _, request = ask()
    assert request["response_format"] == {"type": "json_object"}
    assert "reasoning_effort" not in request


def test_reasoning_effort_of_the_profile_is_sent(setup):
    setup(profile="gemini-flash")
    _, _, request = ask()
    assert request["model"] == "google/gemini-3.8-flash"
    assert request["reasoning_effort"] == "low"


def test_empty_project_falls_back_to_the_project_of_the_credential(setup):
    setup(project="")
    _, client, _ = ask()
    assert "/projects/sa-project/" in client["base_url"]


def test_missing_project_points_to_google_cloud_setup(setup, monkeypatch):
    setup(project="")
    monkeypatch.setattr(google_credentials, "_load_default", lambda: (FakeCredential(), None))
    with pytest.raises(RuntimeError) as error:
        ask_gpt_module.ask_gpt("hello", resp_type="json")
    assert "vertex.project" in str(error.value)
    assert "Setup Google Cloud" in str(error.value)
    assert FakeOpenAI.clients == []


@pytest.mark.parametrize("status, error_class", [(401, "AuthenticationError"), (403, "PermissionDeniedError")])
def test_credential_without_permission_points_to_google_cloud_setup(setup, monkeypatch, status, error_class):
    import httpx
    import openai
    setup()
    response = httpx.Response(status, request=httpx.Request("POST", "https://aiplatform.googleapis.com"))
    denied = getattr(openai, error_class)("Permission 'aiplatform.endpoints.predict' denied", response=response, body=None)
    monkeypatch.setattr(FakeOpenAI, "_create", lambda self, **params: (_ for _ in ()).throw(denied))
    with pytest.raises(Exception) as error:
        ask_gpt_module.ask_gpt("hello", resp_type="json")
    assert "aiplatform.endpoints.predict" in str(error.value)
    assert "Setup Google Cloud" in str(error.value)


def test_permission_error_of_other_profiles_is_unchanged(setup, monkeypatch):
    import httpx
    import openai
    setup(profile="")
    response = httpx.Response(401, request=httpx.Request("POST", "https://api.example.com"))
    denied = openai.AuthenticationError("bad key", response=response, body=None)
    monkeypatch.setattr(FakeOpenAI, "_create", lambda self, **params: (_ for _ in ()).throw(denied))
    with pytest.raises(openai.AuthenticationError) as error:
        ask_gpt_module.ask_gpt("hello", resp_type="json")
    assert "Setup Google Cloud" not in str(error.value)


def test_missing_credential_points_to_google_cloud_setup(setup, monkeypatch):
    import google.auth.exceptions
    setup()

    def no_credential():
        raise google.auth.exceptions.DefaultCredentialsError("Could not automatically determine credentials")

    monkeypatch.setattr(google_credentials, "_load_default", no_credential)
    with pytest.raises(RuntimeError) as error:
        ask_gpt_module.ask_gpt("hello", resp_type="json")
    assert "GOOGLE_APPLICATION_CREDENTIALS" in str(error.value)
    assert "Setup Google Cloud" in str(error.value)
    assert FakeOpenAI.clients == []


def test_auth_hint_names_both_roles_of_the_setup(setup, monkeypatch):
    import httpx
    import openai
    setup()
    response = httpx.Response(403, request=httpx.Request("POST", "https://aiplatform.googleapis.com"))
    denied = openai.PermissionDeniedError("denied", response=response, body=None)
    monkeypatch.setattr(FakeOpenAI, "_create", lambda self, **params: (_ for _ in ()).throw(denied))
    with pytest.raises(Exception) as error:
        ask_gpt_module.ask_gpt("hello", resp_type="json")
    assert "roles/aiplatform.user" in str(error.value)
    assert "roles/serviceusage.serviceUsageConsumer" in str(error.value)


@pytest.mark.parametrize("failure", ["no_credential", "no_project", "denied"])
def test_google_config_errors_are_not_retried(setup, monkeypatch, failure):
    import google.auth.exceptions
    import httpx
    import openai
    sleeps = []
    monkeypatch.setattr("core.utils.decorator.time.sleep", sleeps.append)
    setup(project="" if failure == "no_project" else "my-project")
    if failure == "no_credential":
        def no_credential():
            raise google.auth.exceptions.DefaultCredentialsError("Could not automatically determine credentials")
        monkeypatch.setattr(google_credentials, "_load_default", no_credential)
    elif failure == "no_project":
        monkeypatch.setattr(google_credentials, "_load_default", lambda: (FakeCredential(), None))
    else:
        response = httpx.Response(403, request=httpx.Request("POST", "https://aiplatform.googleapis.com"))
        denied = openai.PermissionDeniedError("denied", response=response, body=None)
        monkeypatch.setattr(FakeOpenAI, "_create", lambda self, **params: (_ for _ in ()).throw(denied))
    with pytest.raises(RuntimeError):
        ask_gpt_module.ask_gpt("hello", resp_type="json")
    assert sleeps == []
