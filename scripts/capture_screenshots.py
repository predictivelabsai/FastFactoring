"""Capture a tour of the Factorio reference app into ./screenshots.

Drives a real browser via Playwright against a locally-running
Factorio/FastFactoring server (default http://localhost:5055). Produces a
deterministic set of frames for make_gif.py and make_pdf.py.

Usage:
    # server already running on :5055
    python -m scripts.capture_screenshots
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

log = logging.getLogger("capture")

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "screenshots"

BASE_URL = os.environ.get("FF_URL", "http://localhost:5055")
VIEWPORT = {"width": 1440, "height": 900}

ACTIVE_LANGS = ("en", "et", "de", "fr", "sv", "lv", "no", "da", "pl", "nl", "fi", "lt")

TOUR_EN = [
    ("01-home-en.png",              "/factorio",            True),
    ("02-for-sellers-en.png",       "/for-sellers",         True),
    ("03-for-investors-en.png",     "/for-investors",       True),
    ("04-how-it-works-en.png",      "/how-it-works",        True),
    ("05-pricing-en.png",           "/pricing",             True),
    ("06-contact-en.png",           "/contact",             True),
    ("07-dashboard-en.png",         "/app",                 True),
    ("08-marketplace-en.png",       "/app/marketplace",     True),
    ("09-marketplace-detail-en.png", None,                  True),
    ("10-portfolio-en.png",         "/app/portfolio",       True),
]

def _set_lang(page, lang: str) -> None:
    page.goto(f"{BASE_URL}/set-lang?lang={lang}&next=/factorio", wait_until="load")


def _find_first_invest_link(page) -> str | None:
    return page.evaluate("""
        () => {
            const a = document.querySelector('a[href*="/app/marketplace/"]');
            return a ? a.getAttribute('href') : null;
        }
    """)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    SHOTS.mkdir(exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport=VIEWPORT, device_scale_factor=1)
        page = ctx.new_page()

        # Establish the same authenticated investor session users get from the
        # landing-page sign-in flow before capturing product routes.
        page.goto(BASE_URL + "/login/demo?who=investor", wait_until="load")

        tours = [("en", TOUR_EN)] + [
            (lang, [(f"locale-{lang}-home.png", "/factorio", True),
                    (f"locale-{lang}-marketplace.png", "/app/marketplace", True)])
            for lang in ACTIVE_LANGS[1:]
        ]
        for lang, tour in tours:
            _set_lang(page, lang)

            for fname, path, full_page in tour:
                if path is None:
                    page.goto(BASE_URL + "/app/marketplace", wait_until="networkidle", timeout=30_000)
                    href = _find_first_invest_link(page)
                    if href:
                        path = href
                    else:
                        log.warning("no marketplace detail link found, skipping %s", fname)
                        continue

                url = BASE_URL + path
                log.info("[%s] %s", lang, url)
                try:
                    page.goto(url, wait_until="networkidle", timeout=30_000)
                except Exception as e:
                    log.warning("goto failed %s: %s — retrying", url, e)
                    page.goto(url, wait_until="load", timeout=30_000)

                out = SHOTS / fname
                page.screenshot(path=str(out), full_page=full_page)
                log.info("  saved %s", out.relative_to(ROOT))

        browser.close()
    log.info("done — captured frames in %s", SHOTS)


if __name__ == "__main__":
    main()
