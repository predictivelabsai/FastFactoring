#!/usr/bin/env python3
"""Bump Factorio's VERSION and prepend a matching change-log entry."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
VERSION_FILE = ROOT / "VERSION"
CHANGE_LOG = ROOT / "docs" / "change_log.md"


def parse_version(value: str) -> tuple[int, int, int]:
    parts = value.strip().split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise ValueError(f"VERSION must be MAJOR.MINOR.PATCH, got {value!r}")
    return tuple(map(int, parts))  # type: ignore[return-value]


def bump(current: tuple[int, int, int], level: str) -> tuple[int, int, int]:
    major, minor, patch = current
    if level == "major":
        return major + 1, 0, 0
    if level == "minor":
        return major, minor + 1, 0
    return major, minor, patch + 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("level", choices=("major", "minor", "patch"))
    parser.add_argument("--change", action="append", required=True,
                        help="Change-log bullet; repeat for multiple changes")
    args = parser.parse_args()

    if not VERSION_FILE.exists():
        raise SystemExit("VERSION is missing; establish the baseline explicitly first.")
    old = parse_version(VERSION_FILE.read_text(encoding="utf-8"))
    new = bump(old, args.level)
    old_text = ".".join(map(str, old))
    new_text = ".".join(map(str, new))

    log = CHANGE_LOG.read_text(encoding="utf-8")
    heading = f"## {date.today().isoformat()} — v{new_text}"
    if heading in log:
        raise SystemExit(f"{heading} already exists")
    marker = "# Change Log\n"
    if not log.startswith(marker):
        raise SystemExit("docs/change_log.md must start with '# Change Log'")
    bullets = "\n".join(f"- {item.strip()}" for item in args.change if item.strip())
    entry = f"\n{heading}\n\n{bullets}\n"

    VERSION_FILE.write_text(new_text + "\n", encoding="utf-8")
    CHANGE_LOG.write_text(marker + entry + log[len(marker):], encoding="utf-8")
    print(f"Factorio {old_text} -> {new_text}")


if __name__ == "__main__":
    main()
