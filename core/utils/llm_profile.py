"""Custom (F7): resolve the active LLM profile for the Translate stage (docs/adr/0001-llm-profiles.md).

`api.profile` names an entry of `llm_profiles`; empty or missing means the custom profile,
which is the upstream `api:` section read exactly as before.
"""

import os
from dataclasses import dataclass
from typing import Callable, Optional

from core.utils.config_errors import ConfigError
from core.utils.config_utils import load_key, load_key_or

CUSTOM_PROFILE = ""


class LLMProfileError(ConfigError, ValueError):
    """The active profile cannot be used as configured."""


class LLMAuthError(ConfigError, RuntimeError):
    """The provider refused the credential (401/403); the message carries the profile's hint."""


@dataclass(frozen=True)
class LLMProfile:
    name: str  # CUSTOM_PROFILE for the upstream `api:` section
    provider: str
    model: str
    base_url: str
    normalize_base_url: bool  # False when the URL is built here and must reach the client unchanged
    credential: Callable[[], str]  # called per request, so a provider may refresh short-lived tokens
    llm_support_json: bool
    reasoning_effort: Optional[str]  # None: the parameter is not sent
    max_workers: Optional[int]  # None: the general max_workers applies
    auth_error_hint: Optional[str] = None  # appended to 401/403 errors of the provider


@dataclass(frozen=True)
class ProviderSettings:
    """What a provider resolves for a named profile."""
    base_url: str
    normalize_base_url: bool
    credential: Callable[[], str]
    llm_support_json: Optional[bool] = None  # None: the profile's override, else api.llm_support_json
    auth_error_hint: Optional[str] = None


def _custom_key():
    from core.utils.ask_gpt import get_api_key  # upstream lookup, including keyless local servers
    return get_api_key()


def _custom_profile():
    return LLMProfile(
        name=CUSTOM_PROFILE,
        provider="custom",
        model=load_key("api.model"),
        base_url=load_key("api.base_url"),
        normalize_base_url=True,
        credential=_custom_key,
        llm_support_json=bool(load_key("api.llm_support_json")),
        reasoning_effort=None,
        max_workers=None,
    )


def _profile_key(name, entry):
    def credential():
        env = entry.get("api_key_env")
        key = (os.environ.get(env) if env else None) or entry.get("api_key")
        if key:
            return key
        places = ([f"environment variable {env}"] if env else []) + [f"llm_profiles.{name}.api_key in config.yaml"]
        raise LLMProfileError(f"LLM profile '{name}' has no API key: set {' or '.join(places)}")
    return credential


def _api_key_provider(default_base_url=None):
    def resolve(name, entry):
        base_url = entry.get("base_url") or default_base_url
        if not base_url:
            raise LLMProfileError(f"LLM profile '{name}' needs base_url (llm_profiles.{name}.base_url)")
        return ProviderSettings(base_url=base_url, normalize_base_url=True, credential=_profile_key(name, entry))
    return resolve


def _vertex_provider(name, entry):
    """Custom (F8): Gemini through the OpenAI-compatible endpoint of Vertex, authenticated by the shared Google credential."""
    from core.utils import google_credentials
    location = str(load_key_or("vertex.location_llm", "global") or "global").strip()
    host = "aiplatform.googleapis.com" if location == "global" else f"{location}-aiplatform.googleapis.com"
    return ProviderSettings(
        # built here, never normalized: normalize_base_url rewrites any URL containing "ark"
        base_url=f"https://{host}/v1/projects/{google_credentials.project()}/locations/{location}/endpoints/openapi",
        normalize_base_url=False,
        credential=google_credentials.access_token,
        llm_support_json=True,
        auth_error_hint=(f"the Google credential needs roles/aiplatform.user and "
                         f"roles/serviceusage.serviceUsageConsumer on the project; {google_credentials.SETUP_HINT}"),
    )


# provider -> resolve(name, entry) giving the ProviderSettings of the profile
PROVIDERS = {
    "openrouter": _api_key_provider("https://openrouter.ai/api/v1"),
    "vertex": _vertex_provider,
}


def _named_profile(name, entry):
    provider = entry.get("provider")
    if not provider:
        raise LLMProfileError(f"LLM profile '{name}' needs provider (llm_profiles.{name}.provider)")
    if not entry.get("model"):
        raise LLMProfileError(f"LLM profile '{name}' needs model (llm_profiles.{name}.model)")
    settings = PROVIDERS.get(provider, _api_key_provider())(name, entry)
    json_default = settings.llm_support_json  # a provider may set its own default
    if json_default is None:
        json_default = load_key("api.llm_support_json")
    return LLMProfile(
        name=name,
        provider=provider,
        model=entry["model"],
        base_url=settings.base_url,
        normalize_base_url=settings.normalize_base_url,
        credential=settings.credential,
        llm_support_json=bool(entry.get("llm_support_json", json_default)),
        reasoning_effort=entry.get("reasoning_effort") or None,
        max_workers=entry.get("max_workers"),
        auth_error_hint=settings.auth_error_hint,
    )


def describe(name):
    """(provider, model) of a profile as written in config.yaml, without resolving it; None when not declared."""
    if name == CUSTOM_PROFILE:
        return "custom", load_key("api.model")
    entry = (load_key_or("llm_profiles", None) or {}).get(name)
    if entry is None:
        return None
    return entry.get("provider") or "?", entry.get("model") or "?"


def _active_entry():
    """(name, llm_profiles entry) named by api.profile; the entry is None for the custom profile."""
    name = load_key_or("api.profile", CUSTOM_PROFILE) or CUSTOM_PROFILE
    if name == CUSTOM_PROFILE:
        return name, None
    profiles = load_key_or("llm_profiles", None) or {}
    if name not in profiles:
        available = ", ".join(profiles) or "none"
        raise LLMProfileError(f"api.profile '{name}' is not in llm_profiles (available: {available})")
    return name, profiles[name] or {}


def active_profile():
    """The profile named by api.profile, or the custom profile when it is empty or missing."""
    name, entry = _active_entry()
    return _custom_profile() if entry is None else _named_profile(name, entry)


def llm_max_workers():
    """Thread count for every parallel Translate-stage step: the active profile's, else the general max_workers.

    Read from the entry, not the resolved profile, so no credential is loaded for a thread count."""
    _, entry = _active_entry()
    return (entry or {}).get("max_workers") or load_key("max_workers")
