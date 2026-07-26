"""Runtime loader for editable Factorio AI prompts."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"


@lru_cache(maxsize=32)
def load_prompt(name: str) -> str:
    path = PROMPTS_DIR / name
    if path.parent != PROMPTS_DIR or path.suffix != ".md":
        raise ValueError(f"Invalid prompt name: {name}")
    return path.read_text(encoding="utf-8").strip()
