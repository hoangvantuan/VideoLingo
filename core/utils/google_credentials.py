"""Shared Google credential for the Vertex providers (custom fork, see CUSTOM.md).

Reads Application Default Credentials (GOOGLE_APPLICATION_CREDENTIALS pointing at a
service-account key), refreshes the token when it expires, and is safe across threads.
"""

import threading

from core.utils.config_errors import ConfigError
from core.utils.config_utils import load_key_or

SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
SETUP_HINT = 'see "Setup Google Cloud" in CUSTOM.md'

_lock = threading.Lock()
_credential = None
_credential_project = None


class GoogleCredentialError(ConfigError, RuntimeError):
    """Google credential or project is missing or unusable."""


def _load_default():
    import google.auth
    return google.auth.default(scopes=SCOPES)


def _ensure_loaded():
    global _credential, _credential_project
    if _credential is None:
        import google.auth.exceptions
        try:
            _credential, _credential_project = _load_default()
        except google.auth.exceptions.DefaultCredentialsError as error:
            raise GoogleCredentialError(
                f"No Google credential found ({error}). Set GOOGLE_APPLICATION_CREDENTIALS to the "
                f"service-account key JSON; {SETUP_HINT}") from error
    return _credential


def access_token():
    """A valid OAuth access token, refreshed when it has expired."""
    with _lock:
        credential = _ensure_loaded()
        if not credential.valid:
            import google.auth.exceptions
            import google.auth.transport.requests
            try:
                credential.refresh(google.auth.transport.requests.Request())
            except google.auth.exceptions.RefreshError as error:
                raise GoogleCredentialError(f"Google credential could not be refreshed ({error}); {SETUP_HINT}") from error
        return credential.token


def auth_headers():
    return {"Authorization": f"Bearer {access_token()}"}


def project():
    """vertex.project from the config, else the project of the credential."""
    configured = str(load_key_or("vertex.project", "") or "").strip()
    if configured:
        return configured
    with _lock:
        _ensure_loaded()
        if _credential_project:
            return _credential_project
    raise GoogleCredentialError(f"Set vertex.project in config.yaml; {SETUP_HINT}")


def reset():
    """Forget the cached credential (tests, or after changing GOOGLE_APPLICATION_CREDENTIALS)."""
    global _credential, _credential_project
    with _lock:
        _credential = _credential_project = None
