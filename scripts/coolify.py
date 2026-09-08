#!/usr/bin/env python3
"""Run this repository's deployment through the sibling FastDevOps control plane."""
from __future__ import annotations
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTROL = Path(os.getenv("FASTDEVOPS_DIR", ROOT.parent / "FastDevOps")).resolve()
if not (CONTROL / "cli.py").is_file():
    raise SystemExit("FastDevOps not found; set FASTDEVOPS_DIR to its checkout")
sys.path.insert(0, str(CONTROL))
from cli import catalog, load_local_env, main  # noqa: E402

for key, value in load_local_env(ROOT / ".env").items():
    if key in {"COOLIFY_API_TOKEN", "COOLIFY_BASE_URL"}:
        os.environ.setdefault(key, value)
service = next((name for name, spec in catalog().items() if spec.get("local_dir") == ROOT.name), None)
if not service:
    raise SystemExit(f"{ROOT.name} is not declared in FastDevOps")
if len(sys.argv) < 2:
    raise SystemExit("usage: coolify.py validate|doctor|status|provision|env|deploy [options]")
command, *options = sys.argv[1:]
sys.argv = [sys.argv[0], command, *([] if command == "validate" else [service]), *options]
main()
