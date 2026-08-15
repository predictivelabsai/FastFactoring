"""Database-backed four-role RBAC, auth, and OIDC regressions."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from app_routes import auth
from app_routes._shared import ROLES, current_role
from utils import google_auth
from utils.access import AccessContext, path_allowed


class AuthenticationTests(unittest.TestCase):
    def request(self, session=None):
        return SimpleNamespace(
            session=session if session is not None else {}, cookies={},
            headers={"host": "factorio.co.uk", "x-forwarded-proto": "https"},
            url=SimpleNamespace(scheme="https", netloc="factorio.co.uk"),
        )

    def profile(self, email, role):
        return {"email": email, "name": "Test User", "status": "active",
                "is_verified": True, "role": role, "company_id": None,
                "investor_user_id": 2 if role == "investor" else None,
                "supplier_user_id": 3 if role == "supplier" else None,
                "payer_registration": "GB-PAYER" if role == "payer" else "",
                "is_synthetic": False}

    def test_rbac_has_exactly_four_roles_and_no_admin_demo(self):
        self.assertEqual(ROLES, ("investor", "supplier", "payer", "admin"))
        self.assertEqual(set(auth.DEMO_SESSION), {"investor", "supplier", "payer"})
        self.assertNotIn("admin", auth.DEMO_SESSION)

    def test_only_named_identity_can_hold_admin_role(self):
        outsider = self.request({"uid": "admin@factorio.co.uk"})
        owner = self.request({"uid": auth.ADMIN_EMAIL})
        with patch("utils.access._profile", side_effect=[
            self.profile("admin@factorio.co.uk", "admin"),
            self.profile(auth.ADMIN_EMAIL, "admin"),
        ]):
            self.assertEqual(current_role(outsider), "pending")
            self.assertEqual(current_role(owner), "admin")

    def test_local_admin_password_login_creates_identity_only_session(self):
        account = {"email": auth.ADMIN_EMAIL, "name": "Julian Kaljuvee"}
        request = self.request({"csrf_token": "csrf"})
        with patch.object(auth.accounts, "authenticate", return_value=account):
            response = auth.login_post(request, auth.ADMIN_EMAIL, "test-only-password", "csrf")
        self.assertEqual(response.status_code, 303)
        self.assertEqual(request.session["uid"], auth.ADMIN_EMAIL)
        self.assertNotIn("role", request.session)
        self.assertIn("csrf_token", request.session)

    def test_public_registration_cannot_assign_admin(self):
        request = self.request({"csrf_token": "csrf"})
        with patch.object(auth.accounts, "register", return_value=(False, "not allowed")) as register:
            response = auth.register_post(request, "A User", "a@example.com",
                                          "long-enough-password", "admin", "", "csrf")
        self.assertIsNotNone(response)
        register.assert_called_once_with("a@example.com", "long-enough-password",
                                         "A User", "admin", "")

    def test_role_paths_are_backend_authorized(self):
        supplier = AccessContext(email="s@example.com", actual_role="supplier",
                                 effective_role="supplier", status="active", is_verified=True)
        self.assertTrue(path_allowed(supplier, "/app/supplier"))
        self.assertFalse(path_allowed(supplier, "/app/admin/team"))
        self.assertFalse(path_allowed(supplier, "/app/portfolio"))

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

    def test_google_callback_uses_account_profile_and_rotates_session(self):
        request = self.request({"google_oauth_state": "state"})
        account = {"email": auth.ADMIN_EMAIL, "name": "Julian Kaljuvee",
                   "role": "admin", "status": "active"}
        with patch.object(auth.google_auth, "exchange",
                          return_value={"email": auth.ADMIN_EMAIL, "name": "Julian Kaljuvee"}), \
             patch.object(auth.accounts, "google_account", return_value=account):
            response = auth.google_callback(request, code="code", state="state")
        self.assertEqual(response.status_code, 303)
        self.assertEqual(request.session["uid"], auth.ADMIN_EMAIL)
        self.assertNotIn("role", request.session)


if __name__ == "__main__":
    unittest.main()
