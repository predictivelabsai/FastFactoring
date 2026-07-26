"""Capture the live Factor AI Platform demo for the English user guide.

The browser journey uses synthetic demo roles and data. It deliberately asks
reviewed eval questions in Investor AI and the Admin Agent Fleet.

Usage:
    FF_URL=https://factorio.co.uk python -m scripts.capture_platform_demo_guide
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "img" / "platform-demo"
BASE_URL = os.environ.get("FF_URL", "https://factorio.co.uk").rstrip("/")
VIEWPORT = {"width": 1600, "height": 1000}
log = logging.getLogger("platform-guide")


def role(page: Page, name: str) -> None:
    page.context.add_cookies([
        {"name": "role", "value": name, "url": BASE_URL},
        {"name": "lang", "value": "en", "url": BASE_URL},
    ])


def visit(page: Page, path: str) -> None:
    page.goto(BASE_URL + path, wait_until="networkidle", timeout=60_000)
    page.wait_for_timeout(700)


def shot(page: Page, name: str, *, full: bool = False, locator: str | None = None) -> None:
    target = OUT / name
    if locator:
        page.locator(locator).screenshot(path=str(target))
    else:
        page.screenshot(path=str(target), full_page=full)
    log.info("saved %s", target.relative_to(ROOT))


def ask_copilot(page: Page, question: str) -> None:
    page.locator("#cp-input").fill(question)
    page.locator(".chat-send").click()
    page.wait_for_selector(".cp-msg.assistant:not(:has(.cp-tool))", timeout=120_000)
    page.wait_for_timeout(800)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(viewport=VIEWPORT, device_scale_factor=1)
        page = context.new_page()

        visit(page, "/")
        shot(page, "00-platform-demo.png")

        role(page, "supplier")
        visit(page, "/app")
        shot(page, "01-supplier-ai-upload.png")
        page.locator("#cp-invoice-file").set_input_files(
            str(ROOT / "data" / "synthetic-invoices" / "manufacturing-invoice.pdf")
        )
        page.wait_for_selector("text=You’re pre-approved!", timeout=120_000)
        page.wait_for_timeout(1000)
        shot(page, "02-supplier-ai-offer.png", locator=".chat")
        page.get_by_role("button", name="Change").click()
        shot(page, "03-supplier-change-terms.png", locator=".chat")
        visit(page, "/app/supplier/profile")
        shot(page, "04-supplier-profile-integrations.png", full=True)
        visit(page, "/app/supplier")
        shot(page, "05-supplier-applications.png", full=True)

        role(page, "investor")
        visit(page, "/app")
        ask_copilot(page, "How are my investments performing?")
        shot(page, "06-investor-ai-performance.png", locator=".chat")
        ask_copilot(page, "Where is my portfolio most concentrated?")
        shot(page, "07-investor-ai-concentration.png", locator=".chat")
        visit(page, "/app/portfolio")
        shot(page, "08-investor-portfolio.png", full=True)
        visit(page, "/app/marketplace")
        shot(page, "09-investor-marketplace.png", full=True)
        visit(page, "/app/auto-invest")
        shot(page, "10-investor-autoinvest.png", full=True)
        visit(page, "/app/statement")
        shot(page, "11-investor-statement.png", full=True)

        role(page, "admin")
        visit(page, "/app/admin")
        shot(page, "12-admin-console.png", full=True)
        visit(page, "/app/admin/agents")
        shot(page, "13-admin-agent-fleet.png", full=True)
        page.get_by_text("SEO & AI Search", exact=True).first.click()
        page.locator("#ag-input").fill(
            "Build a supplier invoice-finance keyword cluster."
        )
        page.get_by_role("button", name="Run").click()
        page.wait_for_selector(".ag-msg.assistant:not(:has(.ag-tool))", timeout=180_000)
        page.wait_for_timeout(1000)
        shot(page, "14-admin-seo-agent.png", locator=".ag-wrap")
        visit(page, "/app/admin/agents/skills")
        shot(page, "15-admin-skills-editor.png", full=True)
        visit(page, "/app/admin/processing")
        shot(page, "16-admin-processing.png", full=True)
        visit(page, "/app/admin/accounting")
        shot(page, "17-admin-accounting.png", full=True)
        visit(page, "/app/admin/integrations")
        shot(page, "18-admin-integrations.png", full=True)
        visit(page, "/app/admin/audit")
        shot(page, "19-admin-audit.png", full=True)
        visit(page, "/app/mail/templates")
        shot(page, "20-admin-email-templates.png", full=True)

        browser.close()
    log.info("captured %d guide screenshots from %s", len(list(OUT.glob("*.png"))), BASE_URL)


if __name__ == "__main__":
    main()
