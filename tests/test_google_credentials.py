"""Contracts of the shared Google credential (custom fork, F8/F9)."""

import threading
import unittest
from unittest.mock import patch

from core.utils import google_credentials


class FakeCredential:
    """Stands in for google.auth credentials: `valid` turns False when the token expires."""

    def __init__(self, valid=False):
        self.valid = valid
        self.token = "token-0" if valid else None
        self.refreshes = 0

    def refresh(self, request):
        self.refreshes += 1
        self.token = f"token-{self.refreshes}"
        self.valid = True


def config(values):
    return lambda key, default=None: values.get(key, default)


class GoogleCredentialTests(unittest.TestCase):
    def setUp(self):
        google_credentials.reset()
        self.addCleanup(google_credentials.reset)

    def use(self, credential, project="sa-project", values=None):
        loader = patch.object(google_credentials, "_load_default", return_value=(credential, project))
        settings = patch.object(google_credentials, "load_key_or", side_effect=config(values or {}))
        self.loader = loader.start()
        settings.start()
        self.addCleanup(loader.stop)
        self.addCleanup(settings.stop)

    def test_token_is_fetched_once_and_refreshed_when_it_expires(self):
        credential = FakeCredential()
        self.use(credential)
        self.assertEqual(google_credentials.access_token(), "token-1")
        self.assertEqual(google_credentials.access_token(), "token-1")
        credential.valid = False  # expired
        self.assertEqual(google_credentials.auth_headers(), {"Authorization": "Bearer token-2"})
        self.assertEqual(self.loader.call_count, 1)

    def test_cloud_platform_scope_is_requested(self):
        with patch("google.auth.default", return_value=(FakeCredential(), "p")) as default:
            google_credentials._load_default()
        self.assertEqual(default.call_args.kwargs["scopes"], ["https://www.googleapis.com/auth/cloud-platform"])

    def test_threads_share_one_refresh(self):
        credential = FakeCredential()
        self.use(credential)
        tokens = []
        threads = [threading.Thread(target=lambda: tokens.append(google_credentials.access_token()))
                   for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(tokens, ["token-1"] * 8)
        self.assertEqual(credential.refreshes, 1)

    def test_configured_project_wins_over_the_credential_project(self):
        self.use(FakeCredential(), project="sa-project", values={"vertex.project": "videolingo-512414"})
        self.assertEqual(google_credentials.project(), "videolingo-512414")

    def test_credential_project_is_the_fallback(self):
        self.use(FakeCredential(), project="sa-project", values={"vertex.project": ""})
        self.assertEqual(google_credentials.project(), "sa-project")

    def test_missing_project_points_to_the_setup_section(self):
        self.use(FakeCredential(), project=None)
        with self.assertRaisesRegex(google_credentials.GoogleCredentialError, "Setup Google Cloud"):
            google_credentials.project()

    def test_missing_credential_points_to_the_setup_section(self):
        import google.auth.exceptions
        with patch("google.auth.default", side_effect=google.auth.exceptions.DefaultCredentialsError("none")):
            with self.assertRaisesRegex(google_credentials.GoogleCredentialError,
                                        "GOOGLE_APPLICATION_CREDENTIALS.*Setup Google Cloud"):
                google_credentials.access_token()

    def test_failed_refresh_is_reported_clearly(self):
        import google.auth.exceptions

        class Broken(FakeCredential):
            def refresh(self, request):
                raise google.auth.exceptions.RefreshError("invalid_grant")

        self.use(Broken())
        with self.assertRaisesRegex(google_credentials.GoogleCredentialError, "invalid_grant"):
            google_credentials.access_token()


if __name__ == "__main__":
    unittest.main()
