"""Compose Factorio demo screenshots into an animated GIF.

Usage:
    python -m scripts.make_gif            # landing-tour GIF (screenshots/)
    python -m scripts.make_gif --home     # home-page hero GIF from the
                                          # user-guide role screenshots (docs/img/)
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "screenshots"
IMG = ROOT / "docs" / "img"
OUT_GIF = ROOT / "docs" / "fastfactoring-reference.gif"
OUT_HOME = ROOT / "docs" / "fastfactoring-reference-home.gif"

FRAMES = [
    ("01-home-en.png",              2800),
    ("07-dashboard-en.png",         2400),
    ("08-marketplace-en.png",       3200),
    ("09-marketplace-detail-en.png", 3200),
    ("10-portfolio-en.png",         3200),
    ("locale-et-home.png",          2800),
    ("locale-de-marketplace.png",   2800),
    ("locale-fr-home.png",          2800),
]

# Home-page hero tour — the SAME role screenshots the user guide uses
# (docs/img/role-*.png), curated into a product story: investor journey →
# AI → back office.
HOME_FRAMES = [
    ("role-investor-chat.png",        2900),   # AI Assistant central chat (Agents)
    ("role-investor-dashboard.png",   2500),   # investor
    ("role-investor-marketplace.png", 2600),
    ("role-investor-portfolio.png",   2600),
    ("role-supplier-pdf.png",         2900),   # supplier + invoice PDF viewer
    ("role-payer-pdf.png",            2900),   # payer + invoice PDF viewer
    ("role-admin-console.png",        2500),   # admin back office
    ("role-admin-crm.png",            2700),   # sales pipeline
    ("role-admin-scoring.png",        2600),
    ("role-admin-accounting.png",     2500),
]

TARGET_W = 1200
TARGET_H = 820
BG = (247, 246, 241)  # parchment (#F7F6F1)


def load_frame(path: Path, target_w: int, target_h: int) -> Image.Image:
    img = Image.open(path).convert("RGB")
    ratio = target_w / img.width
    img = img.resize((target_w, int(img.height * ratio)), Image.LANCZOS)
    if img.height > target_h:
        img = img.crop((0, 0, target_w, target_h))
    else:
        canvas = Image.new("RGB", (target_w, target_h), BG)
        canvas.paste(img, (0, 0))
        img = canvas
    return img


def build(frame_list, shots_dir: Path, out: Path, target_w: int, target_h: int) -> None:
    frames: list[Image.Image] = []
    durations: list[int] = []
    for fname, dur in frame_list:
        p = shots_dir / fname
        if not p.exists():
            print(f"  skip (missing): {p}")
            continue
        frames.append(load_frame(p, target_w, target_h))
        durations.append(dur)
        print(f"  added {fname}  ({dur} ms)")
    if not frames:
        raise SystemExit(f"No frames found in {shots_dir}.")
    out.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(out, save_all=True, append_images=frames[1:], optimize=True,
                   duration=durations, loop=0, disposal=2)
    print(f"\nWrote {out}  ({out.stat().st_size / 1024:.1f} KB, {len(frames)} frames)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--home", action="store_true", help="Build the home-page hero GIF")
    args = ap.parse_args()
    if args.home:
        # role screenshots are 1440x900 → natural 1200x750 (no letterbox)
        build(HOME_FRAMES, IMG, OUT_HOME, 1200, 750)
    else:
        build(FRAMES, SHOTS, OUT_GIF, TARGET_W, TARGET_H)


if __name__ == "__main__":
    main()
