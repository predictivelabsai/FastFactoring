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


def load_agent_prompt(slug: str, name: str, description: str) -> str:
    """Load the latest Admin override, then a dedicated file, then the worker template."""
    if not slug.replace("_", "").isalnum():
        raise ValueError("Invalid agent slug")
    try:
        from db import fetch_one
        row = fetch_one(
            """SELECT content FROM factorio.agent_prompt_versions
               WHERE agent_slug=%s ORDER BY id DESC LIMIT 1""",
            (slug,),
        )
        if row and row.get("content"):
            return row["content"]
    except Exception:
        pass
    dedicated = PROMPTS_DIR / f"agent_{slug}.md"
    if dedicated.exists():
        return dedicated.read_text(encoding="utf-8").strip()
    return load_prompt("agent_worker.md").format(name=name, description=description)
