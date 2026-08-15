"""Public branding dispatch and authenticated app-entry regressions."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from starlette.testclient import TestClient

from app import app
from utils.i18n import DEFAULT_ENABLED_LANGS


class PublicFlowTests(unittest.TestCase):
    def setUp(self):
        self.patchers = [
            patch("utils.i18n.enabled_languages", return_value=DEFAULT_ENABLED_LANGS),
            patch("landing.components.enabled_languages", return_value=DEFAULT_ENABLED_LANGS),
            patch("landing.fastfactoring.enabled_languages", return_value=DEFAULT_ENABLED_LANGS),
            patch("app_routes.shell.enabled_languages", return_value=DEFAULT_ENABLED_LANGS),
            patch("app_routes._shared.list_investors", return_value=[]),
        ]
        for patcher in self.patchers:
            patcher.start()
        self.client = TestClient(app, base_url="https://testserver")

    def tearDown(self):
        self.client.close()
        for patcher in reversed(self.patchers):
            patcher.stop()

    def test_product_routes_require_sign_in_and_demo_enters_app(self):
        response = self.client.get("/app", follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/login")

        response = self.client.get("/login/demo?who=investor", follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/app")
        self.assertEqual(self.client.get("/app").status_code, 200)

    def test_factorio_host_retains_reference_brand_and_login_flow(self):
        response = self.client.get("/", headers={"host": "factorio.co.uk"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("Factorio", response.text)
        self.assertIn('href="/login"', response.text)

    def test_health_probe_is_database_independent(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, "ok")

    def test_fastfactoring_page_negotiates_active_language(self):
        response = self.client.get(
            "/fastfactoring", headers={"accept-language": "de-DE,de;q=0.9"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("FastFactoring", response.text)
        self.assertIn('lang="de"', response.text)
        self.assertIn("https://factorio.co.uk/", response.text)


if __name__ == "__main__":
    unittest.main()
