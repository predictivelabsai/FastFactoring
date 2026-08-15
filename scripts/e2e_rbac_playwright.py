#!/usr/bin/env python3
"""Run the complete auth/RBAC journey in real Chrome against an isolated DB.

The managed mode creates a uniquely named temporary PostgreSQL database beside
``DATABASE_URL_PROD``, migrates and seeds it, starts the app, drives Chrome, and
drops only that temporary database in ``finally``. Credentials stay in process
environment variables and never appear in command arguments or artifacts.

    .venv/bin/python -m scripts.e2e_rbac_playwright --managed
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

import psycopg
from dotenv import load_dotenv
from playwright.sync_api import Browser, BrowserContext, Page, expect, sync_playwright
from psycopg import sql
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "playwright"
ADMIN_EMAIL = "kaljuvee@gmail.com"
TEMP_DB_PREFIX = "fastfactoring_e2e_"


def _database_url(base_url: str, database: str) -> str:
    parsed = urlsplit(base_url)
    return urlunsplit((parsed.scheme, parsed.netloc, f"/{database}", parsed.query, parsed.fragment))


def _database_name(url: str) -> str:
    name = urlsplit(url).path.lstrip("/")
    if not name:
        raise RuntimeError("database URL has no database name")
    return name


@contextmanager
def managed_database(base_url: str):
    database = TEMP_DB_PREFIX + secrets.token_hex(5)
    if not re.fullmatch(r"fastfactoring_e2e_[0-9a-f]{10}", database):
        raise RuntimeError("refusing unsafe temporary database name")
    with psycopg.connect(base_url, autocommit=True) as conn:
        createdb = conn.execute(
            "SELECT rolcreatedb FROM pg_roles WHERE rolname=current_user"
        ).fetchone()
        if not createdb or not createdb[0]:
            raise RuntimeError("configured PostgreSQL role cannot create an isolated E2E database")
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    test_url = _database_url(base_url, database)
    try:
        yield test_url
    finally:
        if not database.startswith(TEMP_DB_PREFIX):
            raise RuntimeError("refusing unsafe temporary database cleanup")
        with psycopg.connect(base_url, autocommit=True) as conn:
            conn.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()",
                (database,),
            )
            conn.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database)))


def _run(command: list[str], env: dict[str, str]) -> None:
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def _wait_for_server(port: int, process: subprocess.Popen, timeout: float = 35) -> None:
    deadline = time.monotonic() + timeout
    request = Request(f"http://127.0.0.1:{port}/healthz", headers={"Host": "fastfactoring.org"})
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"app process exited with code {process.returncode}")
        try:
            with urlopen(request, timeout=1) as response:
                if response.status == 200 and response.read() == b"ok":
                    return
        except Exception:
            time.sleep(0.2)
    raise RuntimeError("app did not become healthy")


def _db_one(url: str, query: str, params=()) -> dict | None:
    with psycopg.connect(url, row_factory=dict_row) as conn:
        return conn.execute(query, params).fetchone()


def _db_execute(url: str, query: str, params=()) -> None:
    with psycopg.connect(url) as conn:
        conn.execute(query, params)
        conn.commit()


def _replace_latest_token(url: str, email: str, purpose: str, raw_token: str) -> None:
    digest = hashlib.sha256(raw_token.encode()).hexdigest()
    with psycopg.connect(url) as conn:
        row = conn.execute(
            """SELECT id FROM factorio.auth_tokens
                 WHERE email=%s AND purpose=%s AND used_at IS NULL
                 ORDER BY created_at DESC LIMIT 1 FOR UPDATE""",
            (email, purpose),
        ).fetchone()
        if not row:
            raise AssertionError(f"missing {purpose} token for {email}")
        conn.execute("UPDATE factorio.auth_tokens SET token_hash=%s WHERE id=%s", (digest, row[0]))
        conn.commit()


def _shot(page: Page, name: str) -> None:
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)


def _assert_topbar(page: Page, role: str) -> None:
    top = page.locator(".ws-top")
    expect(top).to_contain_text(role)
    expect(top.get_by_role("link", name="Sign out")).to_be_visible()
    expect(top.get_by_role("link", name="Sign in")).to_have_count(0)


def _login(page: Page, base: str, email: str, password: str) -> None:
    page.goto(base + "/login", wait_until="networkidle")
    page.locator("input[name=email]").fill(email)
    page.locator("input[name=password]").fill(password)
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_url(re.compile(r".*/app(?:/.*)?$"))


def _logout(page: Page) -> None:
    page.locator(".ws-top").get_by_role("link", name="Sign out").click()
    page.wait_for_url(re.compile(r".*/$"))


def _new_context(browser: Browser, trace_name: str = "") -> BrowserContext:
    context = browser.new_context(viewport={"width": 1440, "height": 1000})
    if trace_name:
        context.tracing.start(screenshots=True, snapshots=True, sources=True)
        context._ff_trace_name = trace_name  # type: ignore[attr-defined]
    return context


def _close_context(context: BrowserContext) -> None:
    trace_name = getattr(context, "_ff_trace_name", "")
    if trace_name:
        context.tracing.stop(path=str(OUT / f"{trace_name}-trace.zip"))
    context.close()


def _public_flow(browser: Browser, fast: str, factorio: str) -> None:
    context = _new_context(browser)
    page = context.new_page()
    page.goto(fast, wait_until="networkidle")
    expect(page).to_have_title(re.compile(r"^FastFactoring"))
    expect(page.get_by_role("link", name="Demo", exact=True)).to_have_attribute(
        "href", "https://factorio.co.uk/"
    )
    expect(page.get_by_text("Open-source invoice factoring infrastructure")).to_be_visible()
    page.get_by_role("link", name="Sign in").click()
    expect(page.get_by_role("heading", name="Sign in to FastFactoring")).to_be_visible()
    expect(page).to_have_title("Sign in to FastFactoring · FastFactoring")
    expect(page.get_by_role("link", name="Continue with Google")).to_have_attribute("href", "/auth/google")
    page.get_by_role("link", name="Register").click()
    expect(page).to_have_title("Create your account · FastFactoring")
    options = page.locator("select[name=role] option").all_text_contents()
    assert options == ["Supplier", "Investor", "Payer"], options
    _shot(page, "01-fastfactoring-register")

    page.goto(factorio + "/login", wait_until="networkidle")
    expect(page.get_by_role("heading", name="Sign in to Factorio")).to_be_visible()
    expect(page).to_have_title("Sign in to Factorio · Factorio")
    expect(page.get_by_role("link", name="Continue with Google")).to_be_visible()
    expect(page.get_by_text("Synthetic demo accounts")).to_be_visible()
    _shot(page, "02-factorio-login")
    _close_context(context)


def _register_and_verify(
    browser: Browser, db_url: str, base: str, role: str, email: str, password: str
) -> None:
    context = _new_context(browser)
    page = context.new_page()
    page.goto(base + "/register", wait_until="networkidle")
    page.locator("input[name=name]").fill(role.title() + " Example")
    page.locator("input[name=email]").fill(email)
    page.locator("input[name=password]").fill(password)
    page.locator("select[name=role]").select_option(role)
    page.get_by_role("button", name="Create account").click()
    expect(page.get_by_text(re.compile(r"Account created|Check your email"))).to_be_visible()
    account = _db_one(db_url, "SELECT status,is_verified FROM factorio.app_users WHERE email=%s", (email,))
    assert account == {"status": "pending", "is_verified": False}, account
    token = f"verify-{role}-{secrets.token_urlsafe(16)}"
    _replace_latest_token(db_url, email, "verify", token)
    page.goto(base + "/auth/local/verify/" + token, wait_until="networkidle")
    page.wait_for_url(re.compile(r".*/app(?:/.*)?$"))
    _assert_topbar(page, role.title())
    forbidden = {
        "supplier": "/app/portfolio",
        "investor": "/app/payer",
        "payer": "/app/marketplace",
    }[role]
    response = page.goto(base + forbidden, wait_until="domcontentloaded")
    assert response and response.status == 403, (role, response.status if response else None)
    page.goto(base + "/app", wait_until="networkidle")
    _shot(page, f"03-{role}-verified")
    _logout(page)
    _close_context(context)


def _password_reset(browser: Browser, db_url: str, base: str, email: str, old: str, new: str) -> None:
    stale_context = _new_context(browser)
    stale = stale_context.new_page()
    _login(stale, base, email, old)

    reset_context = _new_context(browser)
    page = reset_context.new_page()
    page.goto(base + "/forgot-password", wait_until="networkidle")
    page.locator("input[name=email]").fill(email)
    page.get_by_role("button", name="Send reset link").click()
    expect(page.get_by_text("If an account exists, a reset link has been sent.")).to_be_visible()
    token = "reset-" + secrets.token_urlsafe(20)
    _replace_latest_token(db_url, email, "reset", token)
    page.goto(base + "/auth/local/reset/" + token)
    page.locator("input[name=password]").fill(new)
    page.get_by_role("button", name="Reset password").click()
    expect(page.get_by_text("Password reset. You can sign in now.")).to_be_visible()

    stale.goto(base + "/app", wait_until="domcontentloaded")
    expect(stale).to_have_url(base + "/login")
    _login(page, base, email, new)
    _assert_topbar(page, "Supplier")
    _shot(page, "04-password-reset")
    _close_context(stale_context)
    _close_context(reset_context)


def _upload_demand(page: Page, base: str, sample: str) -> dict:
    fixture = ROOT / "data" / "synthetic-invoices" / sample
    invoice = json.loads(fixture.read_text(encoding="utf-8"))["invoice_number"]
    page.goto(base + "/app", wait_until="networkidle")
    expect(page.get_by_role("heading", name="Upload an invoice to get a financing offer")).to_be_visible()
    page.locator("#cp-invoice-file").set_input_files(fixture)
    expect(page.get_by_role("heading", name="You’re pre-approved!")).to_be_visible(timeout=20_000)
    page.locator("#supplier-contact-email").fill("finance.e2e@example.test")
    page.get_by_role("button", name="Save details").click()
    expect(page.locator("#supplier-details-status")).to_contain_text("Details saved")
    page.get_by_role("button", name="Accept", exact=True).click()
    expect(page.get_by_text(re.compile(r"Your application is ready.*Financing demand", re.S))).to_be_visible()
    return {"invoice_number": invoice}


def _admin_flow(
    browser: Browser, db_url: str, fast: str, admin_password: str,
    payer_email: str, real_funding_id: int, synthetic_funding_id: int,
) -> None:
    context = _new_context(browser, "admin-rbac")
    page = context.new_page()
    _login(page, fast, ADMIN_EMAIL, admin_password)
    _assert_topbar(page, "Admin")
    top = page.locator(".ws-top")
    selector = top.locator("select[aria-label='Viewing as']")
    assert selector.locator("option").all_text_contents() == ["Admin", "Supplier", "Investor", "Payer"]

    page.goto(fast + "/app/admin/team", wait_until="networkidle")
    expect(page.get_by_role("heading", name="Team", exact=True)).to_be_visible()
    invite = page.locator("form[action='/app/admin/team/invite']")
    invited_email = "invited.e2e@example.test"
    invite.locator("input[name=email]").fill(invited_email)
    invite.locator("select[name=role]").select_option("investor")
    invite.get_by_role("button", name="Send invitation").click()
    expect(page.get_by_text(invited_email)).to_be_visible()
    assert _db_one(db_url, "SELECT role,status FROM factorio.team_invitations WHERE email=%s", (invited_email,))

    member = page.locator(
        f"form[action='/app/admin/team/role']:has(input[name=email][value='{payer_email}'])"
    )
    member.locator("select[name=role]").select_option("payer")
    member.get_by_role("button", name="Update").click()
    member = page.locator(
        f"form[action='/app/admin/team/role']:has(input[name=email][value='{payer_email}'])"
    )
    member.locator("input[name=payer_registration]").fill("E2E-PAYER-001")
    member.get_by_role("button", name="Update").click()
    profile = _db_one(db_url, "SELECT role,payer_registration FROM factorio.access_profiles WHERE email=%s", (payer_email,))
    assert profile == {"role": "payer", "payer_registration": "E2E-PAYER-001"}, profile
    _shot(page, "05-admin-team")

    # Supplier preview creates an isolated synthetic application.
    page.goto(fast + "/app", wait_until="networkidle")
    page.locator("select[aria-label='Viewing as']").select_option("supplier")
    expect(page.get_by_text(re.compile(r"Previewing Supplier .* synthetic demo data"))).to_be_visible()
    result = _upload_demand(page, fast, "hospitality-invoice.json")
    created = _db_one(db_url, "SELECT is_synthetic FROM factorio.invoices WHERE invoice_number=%s", (result["invoice_number"],))
    assert created == {"is_synthetic": True}, created
    _shot(page, "06-admin-preview-supplier")
    denied = page.goto(fast + "/app/admin/team", wait_until="domcontentloaded")
    assert denied and denied.status == 403
    page.goto(fast + "/app", wait_until="networkidle")
    page.get_by_role("button", name="Exit preview").click()

    # Investor preview cannot fund a real target, but can fund a synthetic one.
    page.locator("select[aria-label='Viewing as']").select_option("investor")
    expect(page.get_by_text(re.compile(r"Previewing Investor .* synthetic demo data"))).to_be_visible()
    page.goto(fast + f"/app/marketplace/{real_funding_id}", wait_until="networkidle")
    page.locator("input[name=amount]").fill("1")
    page.get_by_role("button", name="Invest", exact=True).click()
    assert not _db_one(
        db_url,
        """SELECT 1 FROM factorio.investments x JOIN factorio.users u ON u.id=x.investor_id
             WHERE x.funding_id=%s AND u.email='investor1@factorio.co.uk'""",
        (real_funding_id,),
    )
    page.goto(fast + f"/app/marketplace/{synthetic_funding_id}", wait_until="networkidle")
    page.locator("input[name=amount]").fill("1")
    page.get_by_role("button", name="Invest", exact=True).click()
    expect(page).to_have_url(re.compile(r".*/app/portfolio$"))
    target = _db_one(
        db_url,
        """SELECT i.is_synthetic FROM factorio.investments x
             JOIN factorio.invoice_funding f ON f.id=x.funding_id
             JOIN factorio.invoices i ON i.id=f.invoice_id
             JOIN factorio.users u ON u.id=x.investor_id
            WHERE x.funding_id=%s AND u.email='investor1@factorio.co.uk'""",
        (synthetic_funding_id,),
    )
    assert target == {"is_synthetic": True}, target
    _shot(page, "07-admin-preview-investor")
    page.goto(fast + "/app", wait_until="networkidle")
    page.get_by_role("button", name="Exit preview").click()

    # Payer preview confirms only an invoice in its fixed synthetic scope.
    page.locator("select[aria-label='Viewing as']").select_option("payer")
    expect(page.get_by_text(re.compile(r"Previewing Payer .* synthetic demo data"))).to_be_visible()
    page.goto(fast + "/app/payer", wait_until="networkidle")
    confirm = page.get_by_role("button", name="Confirm").first
    expect(confirm).to_be_visible()
    invoice_number = confirm.locator("xpath=ancestor::form/input[@name='invoice_number']").input_value()
    confirm.click()
    decision = _db_one(db_url, "SELECT payer_decision,is_synthetic FROM factorio.invoices WHERE invoice_number=%s", (invoice_number,))
    assert decision == {"payer_decision": "confirmed", "is_synthetic": True}, decision
    _shot(page, "08-admin-preview-payer")
    page.goto(fast + "/app", wait_until="networkidle")
    page.get_by_role("button", name="Exit preview").click()
    assert _db_one(db_url, "SELECT role FROM factorio.access_profiles WHERE email=%s", (ADMIN_EMAIL,)) == {"role": "admin"}
    _close_context(context)


def _factorio_demos(
    browser: Browser, db_url: str, factorio: str, real_funding_id: int, synthetic_funding_id: int
) -> None:
    # Supplier demo performs a real UI upload, but the resulting record remains synthetic.
    context = _new_context(browser)
    page = context.new_page()
    page.goto(factorio + "/login", wait_until="networkidle")
    page.locator("a[href='/login/demo?who=supplier']").click()
    page.wait_for_url(re.compile(r".*/app(?:/.*)?$"))
    _assert_topbar(page, "Supplier")
    result = _upload_demand(page, factorio, "logistics-invoice.json")
    assert _db_one(db_url, "SELECT is_synthetic FROM factorio.invoices WHERE invoice_number=%s", (result["invoice_number"],)) == {"is_synthetic": True}
    _shot(page, "09-factorio-supplier")
    _close_context(context)

    # Investor demo has the same target restriction as admin preview.
    context = _new_context(browser)
    page = context.new_page()
    page.goto(factorio + "/login", wait_until="networkidle")
    page.locator("a[href='/login/demo?who=investor']").click()
    page.goto(factorio + f"/app/marketplace/{real_funding_id}", wait_until="networkidle")
    page.locator("input[name=amount]").fill("1")
    page.get_by_role("button", name="Invest", exact=True).click()
    assert not _db_one(
        db_url,
        """SELECT 1 FROM factorio.investments x JOIN factorio.users u ON u.id=x.investor_id
             WHERE x.funding_id=%s AND u.email='investor1@factorio.co.uk'""",
        (real_funding_id,),
    )
    page.goto(factorio + f"/app/marketplace/{synthetic_funding_id}", wait_until="networkidle")
    _shot(page, "10-factorio-investor")
    _close_context(context)

    context = _new_context(browser)
    page = context.new_page()
    page.goto(factorio + "/login", wait_until="networkidle")
    page.locator("a[href='/login/demo?who=payer']").click()
    page.goto(factorio + "/app/payer", wait_until="networkidle")
    _assert_topbar(page, "Payer")
    expect(page.get_by_text(re.compile(r"Invoices where"))).to_be_visible()
    _shot(page, "11-factorio-payer")
    _close_context(context)


def _run_browser_suite(db_url: str, port: int, admin_password: str) -> dict:
    fast = f"http://fastfactoring.org:{port}"
    factorio = f"http://factorio.co.uk:{port}"
    accounts = {
        "supplier": ("supplier.e2e@example.test", "SupplierPass-2026"),
        "investor": ("investor.e2e@example.test", "InvestorPass-2026"),
        "payer": ("payer.e2e@example.test", "PayerPass-2026"),
    }
    targets = _db_one(
        db_url,
        """SELECT min(f.id) FILTER (WHERE i.is_synthetic) AS synthetic_id,
                  min(f.id) FILTER (WHERE NOT i.is_synthetic) AS real_id
             FROM factorio.invoice_funding f JOIN factorio.invoices i ON i.id=f.invoice_id
            WHERE f.funding_status='open' AND f.show_in_marketplace=TRUE
              AND f.amount_raised < f.funding_goal""",
    )
    if not targets or not targets["synthetic_id"] or not targets["real_id"]:
        raise AssertionError("E2E fixture needs open synthetic and real marketplace targets")

    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            channel="chrome",
            headless=True,
            args=[
                "--host-resolver-rules=MAP fastfactoring.org 127.0.0.1,MAP factorio.co.uk 127.0.0.1",
                "--no-proxy-server",
                "--disable-features=HttpsUpgrades",
            ],
        )
        _public_flow(browser, fast, factorio)
        for role, (email, password) in accounts.items():
            _register_and_verify(browser, db_url, fast, role, email, password)
        _password_reset(
            browser, db_url, fast, accounts["supplier"][0], accounts["supplier"][1],
            "SupplierReset-2026",
        )
        _admin_flow(
            browser, db_url, fast, admin_password, accounts["payer"][0],
            int(targets["real_id"]), int(targets["synthetic_id"]),
        )
        _factorio_demos(
            browser, db_url, factorio, int(targets["real_id"]), int(targets["synthetic_id"])
        )
        browser.close()
    result = {
        "status": "passed",
        "browser": "Google Chrome",
        "scenarios": 11,
        "screenshots": len(list(OUT.glob("*.png"))),
        "trace": "admin-rbac-trace.zip",
    }
    (OUT / "results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def _prepare_fixtures(db_url: str) -> None:
    # Seeded rows are the checked-in demo corpus. Keep one explicit non-synthetic
    # target to prove that preview/demo principals cannot mutate it.
    _db_execute(db_url, "UPDATE factorio.invoices SET is_synthetic=TRUE,payer_decision=''::text")
    row = _db_one(
        db_url,
        """SELECT i.id FROM factorio.invoices i JOIN factorio.invoice_funding f ON f.invoice_id=i.id
            WHERE f.funding_status='open' AND f.show_in_marketplace=TRUE
              AND f.amount_raised < f.funding_goal ORDER BY i.id LIMIT 1""",
    )
    if not row:
        raise AssertionError("seed produced no open marketplace invoice")
    _db_execute(db_url, "UPDATE factorio.invoices SET is_synthetic=FALSE WHERE id=%s", (row["id"],))
    # Give the real self-registered payer a deterministic scoped obligation.
    _db_execute(
        db_url,
        """UPDATE factorio.invoices SET debtor_registration='E2E-PAYER-001'
              WHERE id=(SELECT max(id) FROM factorio.invoices WHERE is_synthetic=TRUE)""",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--managed", action="store_true", help="create and destroy an isolated test database")
    parser.add_argument("--port", type=int, default=5091)
    args = parser.parse_args()
    if not args.managed:
        parser.error("use --managed; external databases are deliberately unsupported")

    load_dotenv(ROOT / ".env")
    base_url = os.environ.get("DATABASE_URL_PROD", "")
    if not base_url:
        raise RuntimeError("DATABASE_URL_PROD is required for managed E2E")
    admin_password = secrets.token_urlsafe(30)
    app_secret = secrets.token_urlsafe(48)
    OUT.mkdir(parents=True, exist_ok=True)
    for artifact in OUT.glob("*"):
        if artifact.is_file():
            artifact.unlink()

    with managed_database(base_url) as db_url:
        env = os.environ.copy()
        env.update({
            "DATABASE_URL_PROD": db_url,
            "DB_URL": "",
            "APP_ENV": "dev",
            "APP_SECRET": app_secret,
            "ADMIN_PASSWORD": admin_password,
            "PORT": str(args.port),
            "PUBLIC_URL": f"http://fastfactoring.org:{args.port}",
            "GOOGLE_REDIRECT_URI": f"http://fastfactoring.org:{args.port}/auth/google/callback",
            "POSTMARK_API_TOKEN": "",
            "INTEGRATION_WEBHOOK_TOKEN": "",
        })
        _run([sys.executable, "-m", "db.migrate"], env)
        _run([sys.executable, "-m", "db.migrate"], env)
        _run([sys.executable, "-m", "synthetic.generate", "--seed", "42", "--fresh"], env)
        _prepare_fixtures(db_url)
        server_log = (OUT / "server.log").open("w", encoding="utf-8")
        process = subprocess.Popen(
            [sys.executable, "main.py"], cwd=ROOT, env=env,
            stdout=server_log, stderr=subprocess.STDOUT, text=True,
        )
        try:
            _wait_for_server(args.port, process)
            result = _run_browser_suite(db_url, args.port, admin_password)
        finally:
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            server_log.close()
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
