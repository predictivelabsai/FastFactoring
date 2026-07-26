"""Capture the 12 core guide screens (public site + investor app) into docs/img/.

Produces docs/img/<lang>-<name>.png at 1440x900 for the user guide. App pages
use an investor cookie so they have data; money now renders in the display
currency (USD). Pair with scripts/capture_ai_screens.py for the AI screens.

    FF_URL=http://localhost:5079 FF_INVESTOR=30 python -m scripts.capture_guide
"""

from __future__ import annotations

import os
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "docs" / "img"
BASE = os.environ.get("FF_URL", "http://localhost:5079")
INVESTOR = os.environ.get("FF_INVESTOR", "30")
VIEWPORT = {"width": 1440, "height": 900}

# (name, path or None for the marketplace-detail resolver)
SCREENS = [
    ("01-landing", "/"),
    ("02-for-sellers", "/for-sellers"),
    ("03-for-investors", "/for-investors"),
    ("04-how-it-works", "/how-it-works"),
    ("05-pricing", "/pricing"),
    ("06-contact", "/contact"),
    ("07-dashboard", "/app"),
    ("08-marketplace", "/app/marketplace"),
    ("09-marketplace-detail", None),
    ("10-portfolio", "/app/portfolio"),
    ("11-statement", "/app/statement"),
    ("12-auto-invest", "/app/auto-invest"),
    ("19-invoice-upload", "/app/seller"),
]


def _cookies(lang: str):
    c = [{"name": "lang", "value": lang, "url": BASE},
         {"name": "role", "value": "investor", "url": BASE}]
    if INVESTOR:
        c.append({"name": "investor", "value": INVESTOR, "url": BASE})
    return c


def main() -> None:
    IMG.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for lang in ("en", "ru"):
            ctx = browser.new_context(viewport=VIEWPORT, device_scale_factor=1)
            ctx.add_cookies(_cookies(lang))
            page = ctx.new_page()
            for name, path in SCREENS:
                if name == "19-invoice-upload":
                    ctx.add_cookies([{"name": "role", "value": "supplier", "url": BASE}])
                if path is None:  # resolve first invoice detail
                    page.goto(BASE + "/app/marketplace", wait_until="networkidle", timeout=30_000)
                    href = page.evaluate(
                        "() => { const a=document.querySelector('a[href*=\"/app/marketplace/\"]');"
                        " return a ? a.getAttribute('href') : null; }")
                    if not href:
                        print(f"[{lang}] {name}: no detail link, skipping")
                        continue
                    path = href
                try:
                    page.goto(BASE + path, wait_until="networkidle", timeout=30_000)
                except Exception:
                    page.goto(BASE + path, wait_until="load", timeout=30_000)
                page.wait_for_timeout(400)
                out = IMG / f"{lang}-{name}.png"
                page.screenshot(path=str(out), full_page=False)
                print(f"[{lang}] {out.relative_to(ROOT)}")
            ctx.close()
        browser.close()
    print("done")


if __name__ == "__main__":
    main()
