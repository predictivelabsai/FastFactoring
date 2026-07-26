"""Load and render checked-in Factorio transactional email templates."""

from __future__ import annotations

import re
from pathlib import Path

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "email" / "templates"
TEMPLATE_NAMES = {
    "bank_connection": "bank_connection_reminder.md",
    "accounting_connection": "accounting_connection_reminder.md",
}
_VARIABLE = re.compile(r"\{\{([a-z_]+)\}\}")


def load_email_template(kind: str) -> dict[str, str]:
    filename = TEMPLATE_NAMES.get(kind)
    if not filename:
        raise ValueError(f"Unknown transactional email template: {kind}")
    text = (TEMPLATES_DIR / filename).read_text(encoding="utf-8")
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        raise ValueError(f"Template {filename} needs YAML-style metadata")
    header, body = text[4:].split("\n---\n", 1)
    metadata = {}
    for line in header.splitlines():
        key, separator, value = line.partition(":")
        if separator:
            metadata[key.strip()] = value.strip()
    return {"name": kind, "body": body.strip(), **metadata}


def render_email_template(kind: str, *, first_name: str, resume_url: str,
                          support_email: str = "hello@factorio.co.uk") -> dict[str, str]:
    if not resume_url.startswith("https://"):
        raise ValueError("Transactional email resume_url must use HTTPS")
    values = {
        "first_name": first_name.strip()[:80] or "there",
        "resume_url": resume_url.strip()[:500],
        "support_email": support_email.strip()[:254],
    }
    template = load_email_template(kind)

    def replace(match):
        return values.get(match.group(1), match.group(0))

    return {
        "name": kind,
        "subject": _VARIABLE.sub(replace, template["subject"]),
        "preheader": _VARIABLE.sub(replace, template.get("preheader", "")),
        "body": _VARIABLE.sub(replace, template["body"]),
        "status": "draft_only_postmark_not_configured",
    }
