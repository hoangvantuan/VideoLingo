"""Custom (F7): resolve the active LLM profile for the Translate stage (docs/adr/0001-llm-profiles.md).

`api.profile` names an entry of `llm_profiles`; empty or missing means the custom profile,
which is the upstream `api:` section read exactly as before.
"""

import os
from dataclasses import dataclass
from typing import Callable, Optional

from core.utils.config_utils import load_key, load_key_or

CUSTOM_PROFILE = ""


class LLMProfileError(ValueError):
    """The active profile cannot be used as configured."""


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
        return dict(base_url=base_url, normalize_base_url=True, credential=_profile_key(name, entry))
    return resolve


# provider -> resolve(name, entry) giving base_url, normalize_base_url and credential
PROVIDERS = {
    "openrouter": _api_key_provider("https://openrouter.ai/api/v1"),
}


def _named_profile(name, entry):
    provider = entry.get("provider")
    if not provider:
        raise LLMProfileError(f"LLM profile '{name}' needs provider (llm_profiles.{name}.provider)")
    if not entry.get("model"):
        raise LLMProfileError(f"LLM profile '{name}' needs model (llm_profiles.{name}.model)")
    resolve = PROVIDERS.get(provider, _api_key_provider())
    return LLMProfile(
        name=name,
        provider=provider,
        model=entry["model"],
        llm_support_json=bool(entry.get("llm_support_json", load_key("api.llm_support_json"))),
        reasoning_effort=entry.get("reasoning_effort") or None,
        max_workers=entry.get("max_workers"),
        **resolve(name, entry),
    )


def active_profile():
    """The profile named by api.profile, or the custom profile when it is empty or missing."""
    name = load_key_or("api.profile", CUSTOM_PROFILE) or CUSTOM_PROFILE
    if name == CUSTOM_PROFILE:
        return _custom_profile()
    profiles = load_key_or("llm_profiles", None) or {}
    if name not in profiles:
        available = ", ".join(profiles) or "none"
        raise LLMProfileError(f"api.profile '{name}' is not in llm_profiles (available: {available})")
    return _named_profile(name, profiles[name])
