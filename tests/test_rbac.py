"""Role preview, scope, and Team governance security regressions."""

from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app_routes import depth
from app_routes import marketplace
from app_routes import origination
from app_routes import team
from app_routes import integrations
from app_routes._shared import current_investor, role_preview
from app_routes.shell import _topbar
from utils.access import AccessContext, _CONTEXT, context_for, preview_request_allowed


class RbacTests(unittest.TestCase):
    def request(self, email="kaljuvee@gmail.com"):
        return SimpleNamespace(
            session={"uid": email, "csrf_token": "token"}, cookies={},
            headers={"referer": "/app"},
        )

    def test_admin_preview_changes_effective_role_without_changing_identity(self):
        req = self.request()
        ctx = AccessContext(email="kaljuvee@gmail.com", name="Julian",
                            actual_role="admin", effective_role="admin", status="active", is_verified=True)
        with patch("app_routes._shared.context_for", return_value=ctx), \
             patch("app_routes._shared.audit") as audit:
            response = role_preview(req, "supplier", "token")
        self.assertEqual(response.status_code, 303)
        self.assertEqual(req.session["uid"], "kaljuvee@gmail.com")
        self.assertEqual(req.session["preview_role"], "supplier")
        audit.assert_called_once()

    def test_admin_topbar_renders_all_four_preview_choices(self):
        ctx = AccessContext(email="kaljuvee@gmail.com", name="Julian",
                            actual_role="admin", effective_role="admin", status="active",
                            is_verified=True, csrf_token="token")
        marker = _CONTEXT.set(ctx)
        try:
            rendered = str(_topbar("en", "admin", None, [], "/app"))
        finally:
            _CONTEXT.reset(marker)
        for label in ("Admin", "Supplier", "Investor", "Payer"):
            self.assertIn(f">{label}<", rendered)
        self.assertIn('aria-label="Viewing as"', rendered)

    def test_supplier_recent_demands_are_scoped_for_two_suppliers(self):
        records = {
            11: {"invoice_number": "SUPPLIER-A-ONLY", "debtor_name": "A Debtor",
                 "amount": 100, "currency": "GBP", "funding_id": 1},
            22: {"invoice_number": "SUPPLIER-B-ONLY", "debtor_name": "B Debtor",
                 "amount": 200, "currency": "EUR", "funding_id": 2},
        }

        def render_for(supplier_id: int, synthetic: bool = False) -> str:
            ctx = AccessContext(email=f"supplier-{supplier_id}@example.test",
                                actual_role="supplier", effective_role="supplier",
                                status="active", is_verified=True,
                                supplier_user_id=supplier_id, is_synthetic=synthetic)

            def scoped_fetch(query, params):
                self.assertIn("WHERE i.seller_id=%(seller)s", query)
                self.assertEqual(params, {"seller": supplier_id})
                self.assertEqual("i.is_synthetic=TRUE" in query, synthetic)
                return [records[params["seller"]]]

            with patch("utils.access.context_for", return_value=ctx), \
                 patch.object(origination, "fetch_all", side_effect=scoped_fetch), \
                 patch.object(origination, "current_subrole", return_value="ops"), \
                 patch.object(origination, "app_page",
                              side_effect=lambda title, *content, **kwargs: (title, *content)):
                return "".join(map(str, origination._page(self.request(ctx.email))))

        supplier_a = render_for(11)
        supplier_b = render_for(22, synthetic=True)
        self.assertIn("SUPPLIER-A-ONLY", supplier_a)
        self.assertNotIn("SUPPLIER-B-ONLY", supplier_a)
        self.assertIn("SUPPLIER-B-ONLY", supplier_b)
        self.assertNotIn("SUPPLIER-A-ONLY", supplier_b)

    def test_non_admin_cannot_start_preview(self):
        req = self.request("supplier@example.com")
        ctx = AccessContext(email="supplier@example.com", actual_role="supplier",
                            effective_role="supplier", status="active", is_verified=True)
        with patch("app_routes._shared.context_for", return_value=ctx):
            response = role_preview(req, "investor", "token")
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("preview_role", req.session)

    def test_investor_cookie_cannot_cross_account_scope(self):
        req = self.request("investor@example.com")
        req.cookies["investor"] = "99"
        ctx = AccessContext(email="investor@example.com", actual_role="investor",
                            effective_role="investor", status="active", is_verified=True, investor_user_id=7)
        investors = [{"id": 7, "email": "owner@example.com"},
                     {"id": 99, "email": "other@example.com"}]
        with patch("app_routes._shared.context_for", return_value=ctx):
            selected = current_investor(req, investors)
        self.assertEqual(selected["id"], 7)

    def test_team_mutations_require_native_admin_and_csrf(self):
        req = self.request("supplier@example.com")
        ctx = AccessContext(email="supplier@example.com", actual_role="supplier",
                            effective_role="supplier", status="active", is_verified=True)
        with patch("app_routes.team.context_for", return_value=ctx), \
             patch.object(team.accounts, "create_invitation") as create:
            response = team.invite_member(req, "new@example.com", "supplier", "token")
        self.assertEqual(response.status_code, 403)
        create.assert_not_called()

    def test_preview_admin_cannot_mutate_team(self):
        req = self.request()
        ctx = AccessContext(email="kaljuvee@gmail.com", actual_role="admin",
                            effective_role="payer", status="active", is_verified=True, preview=True)
        with patch("app_routes.team.context_for", return_value=ctx), \
             patch.object(team.accounts, "update_member_role") as update:
            response = team.change_member_role(req, "user@example.com", "investor", "", "token")
        self.assertEqual(response.status_code, 403)
        update.assert_not_called()

    def test_preview_blocks_investor_financial_writes(self):
        ctx = AccessContext(email="kaljuvee@gmail.com", actual_role="admin",
                            effective_role="investor", status="active", is_verified=True,
                            preview=True, is_synthetic=True)
        self.assertFalse(preview_request_allowed(
            ctx, "/app/marketplace/auctions/bid", "POST"))
        self.assertFalse(preview_request_allowed(ctx, "/app/auto-invest", "POST"))
        self.assertTrue(preview_request_allowed(ctx, "/app/role-preview", "POST"))
        self.assertTrue(preview_request_allowed(ctx, "/app/preview-exit", "POST"))
        self.assertTrue(preview_request_allowed(ctx, "/app/chat/share", "POST"))

    def test_session_version_change_revokes_existing_session(self):
        req = self.request("investor@example.com")
        req.session["session_version"] = 3
        row = {"email": "investor@example.com", "name": "Investor", "status": "active",
               "is_verified": True, "session_version": 4, "role": "investor",
               "company_id": None, "investor_user_id": 7, "supplier_user_id": None,
               "payer_registration": "", "is_synthetic": False}
        with patch("utils.access._profile", return_value=row):
            ctx = context_for(req)
        self.assertFalse(ctx.authenticated)
        self.assertEqual(ctx.status, "revoked")

    def test_secondary_purchase_locks_claim_and_transfer_in_one_transaction(self):
        statements = []

        class Cursor:
            rowcount = 1

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def execute(self, sql, params):
                statements.append((" ".join(sql.split()), params))
                self.rowcount = 1

            def fetchone(self):
                return (5, 11)

        class Transaction:
            def __enter__(self):
                statements.append(("BEGIN", ()))

            def __exit__(self, *_args):
                statements.append(("COMMIT", ()))
                return False

        class Connection:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def transaction(self):
                return Transaction()

            def cursor(self):
                return Cursor()

        req = self.request("buyer@example.com")
        req.session["csrf_token"] = "token"
        buyer = {"id": 7, "email": "buyer@example.com"}
        ctx = AccessContext(email="buyer@example.com", actual_role="investor",
                            effective_role="investor", status="active", is_verified=True)
        with patch.object(depth, "_HAS_DB", True), \
             patch.object(depth, "list_investors", return_value=[buyer]), \
             patch.object(depth, "current_investor", return_value=buyer), \
             patch("utils.access.context_for", return_value=ctx), \
             patch.object(depth, "connect", return_value=Connection()):
            response = depth.secondary_buy(req, listing_id=3, csrf="token")
        self.assertEqual(response.status_code, 303)
        sql = "\n".join(statement for statement, _ in statements)
        self.assertIn("FOR UPDATE", sql)
        self.assertIn("secondary_market SET status='sold'", sql)
        self.assertIn("investments SET investor_id", sql)
        self.assertEqual([statement for statement, _ in statements].count("BEGIN"), 1)

    def test_hidden_marketplace_id_is_not_available_to_detail_or_invest(self):
        detail_sql = []

        def hidden_detail(sql, params):
            detail_sql.append(" ".join(sql.split()))
            return []

        req = self.request("buyer@example.com")
        with patch.object(marketplace, "_HAS_DB", True), \
             patch.object(marketplace, "list_investors", return_value=[]), \
             patch.object(marketplace, "current_investor", return_value=None), \
             patch.object(marketplace, "current_role", return_value="investor"), \
             patch.object(marketplace, "fetch_all", side_effect=hidden_detail), \
             patch.object(marketplace, "app_page", return_value="not-found"):
            self.assertEqual(marketplace.marketplace_detail(req, 999), "not-found")
        self.assertIn("funding_status = 'open'", detail_sql[0])
        self.assertIn("show_in_marketplace = TRUE", detail_sql[0])

        statements = []

        class Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def execute(self, sql, params):
                statements.append(" ".join(sql.split()))

            def fetchone(self):
                return None

        class Connection:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def cursor(self):
                return Cursor()

            def rollback(self):
                pass

        investor = {"id": 7, "email": "buyer@example.com"}
        ctx = AccessContext(email="buyer@example.com", actual_role="investor",
                            effective_role="investor", status="active", is_verified=True)
        with patch.object(marketplace, "context_for", ctx, create=True), \
             patch("utils.access.context_for", return_value=ctx), \
             patch.object(marketplace, "list_investors", return_value=[investor]), \
             patch.object(marketplace, "current_investor", return_value=investor), \
             patch.object(marketplace, "connect", return_value=Connection()), \
             patch("utils.access.audit"):
            marketplace.marketplace_invest(req, funding_id=999, amount=100, csrf="token")
        self.assertIn("funding_status='open'", statements[0])
        self.assertIn("show_in_marketplace=TRUE", statements[0])
        self.assertEqual(len(statements), 1)

    def test_hidden_marketplace_id_cannot_receive_auction_bid(self):
        statements = []

        class Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def execute(self, sql, params):
                statements.append(" ".join(sql.split()))

            def fetchone(self):
                return None

        class Transaction:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        class Connection(Transaction):
            def transaction(self):
                return Transaction()

            def cursor(self):
                return Cursor()

        investor = {"id": 7, "email": "buyer@example.com"}
        req = self.request("buyer@example.com")
        ctx = AccessContext(email="buyer@example.com", actual_role="investor",
                            effective_role="investor", status="active", is_verified=True)
        with patch.object(depth, "_HAS_DB", True), \
             patch.object(depth, "_ensure"), \
             patch.object(depth, "list_investors", return_value=[investor]), \
             patch.object(depth, "current_investor", return_value=investor), \
             patch("utils.access.context_for", return_value=ctx), \
             patch.object(depth, "connect", return_value=Connection()):
            asyncio.run(depth.auctions_bid(req, funding_id=999, bid_fee_pct=1, bid_advance_pct=80))
        self.assertIn("funding_status='open'", statements[0])
        self.assertIn("show_in_marketplace=TRUE", statements[0])
        self.assertEqual(len(statements), 1)


class WebhookSecurityTests(unittest.IsolatedAsyncioTestCase):
    async def test_invoice_webhook_is_disabled_without_a_secret(self):
        req = SimpleNamespace(headers={}, json=self._json)
        config = SimpleNamespace(integration_webhook_token="")
        with patch("utils.config.settings", return_value=config):
            response = await integrations.ingest_invoice(req)
        self.assertEqual(response.status_code, 503)

    async def _json(self):
        return {"amount": 100, "supplier_email": "supplier@example.com"}


if __name__ == "__main__":
    unittest.main()
