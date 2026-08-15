"""Four-role RBAC, sole-admin, local login, and Google OIDC regressions."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from app_routes import auth
from app_routes._shared import ROLES, current_role
from utils import google_auth


class AuthenticationTests(unittest.TestCase):
    def request(self, session=None):
        return SimpleNamespace(
            session=session or {}, cookies={},
            headers={"host": "factorio.co.uk", "x-forwarded-proto": "https"},
            url=SimpleNamespace(scheme="https", netloc="factorio.co.uk"),
        )

    def test_rbac_has_exactly_four_roles_and_no_admin_demo(self):
        self.assertEqual(ROLES, ("investor", "supplier", "payer", "admin"))
        self.assertEqual(set(auth.DEMO_SESSION), {"investor", "supplier", "payer"})
        self.assertNotIn("admin", auth.DEMO_SESSION)

    def test_only_named_identity_can_hold_admin_role(self):
        outsider = self.request({"uid": "admin@factorio.co.uk", "role": "admin"})
        owner = self.request({"uid": auth.ADMIN_EMAIL, "role": "admin"})
        self.assertEqual(current_role(outsider), "investor")
        self.assertEqual(current_role(owner), "admin")

    def test_local_admin_password_login_creates_admin_session(self):
        salt, password_hash = auth._hash("test-only-password")
        row = {"email": auth.ADMIN_EMAIL, "name": "Julian Kaljuvee", "role": "admin",
               "salt": salt, "pw_hash": password_hash}
        request = self.request()
        with patch.object(auth, "seed_users", return_value=0), \
             patch.object(auth, "_HAS_DB", True), \
             patch.object(auth, "fetch_one", return_value=row, create=True):
            response = auth.login_post(request, auth.ADMIN_EMAIL, "test-only-password")
        self.assertEqual(response.status_code, 303)
        self.assertEqual(request.session["uid"], auth.ADMIN_EMAIL)
        self.assertEqual(request.session["role"], "admin")

    def test_google_authorize_url_uses_code_flow_minimal_scopes_and_state(self):
        config = SimpleNamespace(
            google_client_id="client-id", google_client_secret="secret",
            google_redirect_uri="https://factorio.co.uk/auth/google/callback",
            google_redirect_hosts="fastfactoring.org,factorio.co.uk",
            google_allowed_domains="", google_allowed_emails="",
        )
        with patch.object(google_auth, "settings", return_value=config):
            url = google_auth.authorize_url(self.request(), "random-state")
        query = parse_qs(urlsplit(url).query)
        self.assertEqual(query["response_type"], ["code"])
        self.assertEqual(query["scope"], ["openid email profile"])
        self.assertEqual(query["state"], ["random-state"])
        self.assertEqual(query["redirect_uri"], ["https://factorio.co.uk/auth/google/callback"])

    def test_google_redirect_tracks_each_allowed_public_brand_host(self):
        config = SimpleNamespace(
            google_client_id="client-id", google_client_secret="secret",
            google_redirect_uri="https://fastfactoring.org/auth/google/callback",
            google_redirect_hosts="fastfactoring.org,factorio.co.uk",
            google_allowed_domains="", google_allowed_emails="",
        )
        with patch.object(google_auth, "settings", return_value=config):
            factorio = google_auth.callback_uri(self.request())
            fastfactoring_request = self.request()
            fastfactoring_request.headers["host"] = "fastfactoring.org"
            fastfactoring_request.url.netloc = "fastfactoring.org"
            fastfactoring = google_auth.callback_uri(fastfactoring_request)
        self.assertEqual(factorio, "https://factorio.co.uk/auth/google/callback")
        self.assertEqual(fastfactoring, "https://fastfactoring.org/auth/google/callback")

    def test_google_redirect_rejects_untrusted_host_header(self):
        config = SimpleNamespace(
            google_client_id="client-id", google_client_secret="secret",
            google_redirect_uri="https://fastfactoring.org/auth/google/callback",
            google_redirect_hosts="fastfactoring.org,factorio.co.uk",
            google_allowed_domains="", google_allowed_emails="",
        )
        request = self.request()
        request.headers["host"] = "attacker.example"
        with patch.object(google_auth, "settings", return_value=config):
            callback = google_auth.callback_uri(request)
        self.assertEqual(callback, "https://fastfactoring.org/auth/google/callback")

    def test_google_callback_maps_only_named_identity_to_admin(self):
        request = self.request({"google_oauth_state": "state"})
        with patch.object(auth.google_auth, "exchange",
                          return_value={"email": auth.ADMIN_EMAIL, "name": "Julian Kaljuvee"}):
            response = auth.google_callback(request, code="code", state="state")
        self.assertEqual(response.status_code, 303)
        self.assertEqual(request.session["role"], "admin")


if __name__ == "__main__":
    unittest.main()
