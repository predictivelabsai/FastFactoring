#!/usr/bin/env python3
"""Inventory, validate, and explicitly refresh FastFactoring locale catalogues.

Production reads checked-in JSON only. Translation is an explicit maintenance
operation that sends public English UI copy to the configured x.ai model:

    python -m scripts.update_i18n
    python -m scripts.update_i18n --translate
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import string
from pathlib import Path

from utils.ai import chat
from utils.i18n import DEFAULT_ENABLED_LANGS, DEFAULT_LANG, LOCALES_DIR, TRANSLATIONS


ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILES = tuple(sorted((ROOT / "landing").glob("*.py"))) + \
    tuple(sorted((ROOT / "app_routes").glob("*.py")))
UI_CALLS = {
    "A", "Button", "Eyebrow", "H1", "H2", "H3", "H4", "Heading", "Label",
    "Li", "NotStr", "Option", "P", "Span", "Strong", "Td", "Textarea", "Th", "Title",
    "_card", "_detail", "_field", "_stat_card",
}
TRANSLATABLE_ATTRIBUTES = {"placeholder", "title", "aria_label"}
DO_NOT_TRANSLATE = {
    "", "/", "—", "–", "×", "#", "F", "●", "✨", "＋", "⤢", "✕",
    "Factorio", "FastFactoring", "FastSME", "AI Assistant", "USD", "EUR", "GBP", "UZS",
}


def _literal(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.IfExp):
        return _literal(node.body) + _literal(node.orelse)
    return []


def source_strings() -> set[str]:
    strings = {entry[DEFAULT_LANG] for entry in TRANSLATIONS.values() if entry.get(DEFAULT_LANG)}
    for path in SOURCE_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id == "t" and node.args:
                for key in _literal(node.args[0]):
                    entry = TRANSLATIONS.get(key)
                    strings.add(entry.get(DEFAULT_LANG, key) if entry else key)
            elif node.func.id in UI_CALLS and node.args:
                strings.update(_literal(node.args[0]))
                for keyword in node.keywords:
                    if keyword.arg in TRANSLATABLE_ATTRIBUTES:
                        strings.update(_literal(keyword.value))
    return {
        value for value in strings
        if value.strip() and value not in DO_NOT_TRANSLATE
        and not value.startswith(("/", "#", "http://", "https://", "mailto:"))
    }


def read_catalog(lang: str) -> dict[str, str]:
    path = LOCALES_DIR / f"{lang}.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not all(isinstance(k, str) and isinstance(v, str)
                                            for k, v in data.items()):
        raise ValueError(f"{path} must contain a string-to-string JSON object")
    return data


def _fields(value: str) -> set[str]:
    try:
        return {name for _, name, _, _ in string.Formatter().parse(value) if name}
    except ValueError:
        return {"<invalid>"}


def _markup_signature(value: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    tags = tuple(re.findall(r"<[^>]+>", value))
    entities = tuple(re.findall(r"&(?:[A-Za-z][A-Za-z0-9]+|#\d+|#x[0-9A-Fa-f]+);", value))
    return tags, entities


def check_catalogs() -> bool:
    expected = source_strings()
    valid = True
    for lang in DEFAULT_ENABLED_LANGS:
        if lang == DEFAULT_LANG:
            continue
        locale = read_catalog(lang)
        missing = sorted(expected - locale.keys())
        stale = sorted(locale.keys() - expected)
        empty = sorted(key for key, value in locale.items() if not value.strip())
        invalid = sorted(
            key for key, value in locale.items()
            if _fields(key) != _fields(value) or _markup_signature(key) != _markup_signature(value)
        )
        if missing or stale or empty or invalid:
            valid = False
            print(f"{lang}: {len(missing)} missing, {len(stale)} stale, "
                  f"{len(empty)} empty, {len(invalid)} structure mismatches")
            for label, values in (("missing", missing), ("stale", stale),
                                  ("empty", empty), ("invalid", invalid)):
                for value in values[:8]:
                    print(f"  {label}: {value}")
        else:
            print(f"{lang}: {len(locale)} translations complete")
    return valid


def _parse_reply(reply: str, count: int) -> list[str]:
    text = reply.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n?|\n?```$", "", text)
    match = re.search(r"\[.*\]", text, re.DOTALL)
    values = json.loads(match.group(0) if match else text)
    if not isinstance(values, list) or len(values) != count or not all(isinstance(v, str) for v in values):
        raise ValueError("translator returned the wrong number of strings")
    return values


def _translate_batch(values: list[str], lang: str) -> list[str]:
    names = {
        "et": "Estonian", "de": "German", "fr": "French", "sv": "Swedish",
        "lv": "Latvian", "no": "Norwegian Bokmål", "da": "Danish",
        "pl": "Polish", "nl": "Dutch", "fi": "Finnish", "lt": "Lithuanian",
    }
    prompt = (
        f"Translate this JSON array of English UI copy for an invoice-financing platform "
        f"into {names[lang]}. Return only a JSON array with exactly {len(values)} strings in "
        "the same order. Preserve Factorio, FastSME, company names, email addresses, URLs, "
        "currency codes, format placeholders, HTML tags/entities, and punctuation structure."
    )
    failure: Exception | None = None
    translated: list[str] | None = None
    for _attempt in range(2):
        reply = chat(
            [{"role": "system", "content": prompt},
             {"role": "user", "content": json.dumps(values, ensure_ascii=False)}],
            temperature=0, max_tokens=12000,
        )
        try:
            translated = _parse_reply(reply, len(values))
            break
        except (ValueError, json.JSONDecodeError) as exc:
            failure = exc
    if translated is None:
        if len(values) <= 1:
            raise failure or ValueError("translation failed")
        midpoint = len(values) // 2
        return _translate_batch(values[:midpoint], lang) + _translate_batch(values[midpoint:], lang)
    for source, target in zip(values, translated, strict=True):
        if _fields(source) != _fields(target) or _markup_signature(source) != _markup_signature(target):
            raise ValueError(f"translation changed protected structure: {source!r}")
    return translated


def refresh_catalogs(batch_size: int) -> None:
    LOCALES_DIR.mkdir(parents=True, exist_ok=True)
    expected = source_strings()
    for lang in DEFAULT_ENABLED_LANGS:
        if lang == DEFAULT_LANG:
            continue
        current = read_catalog(lang)
        if lang == "fr" and not current:
            # Reuse the previous complete keyed French overlay during migration
            # to source-string catalogues; subsequent runs read JSON only.
            try:
                from utils.i18n_es_fr import EXTRA
                current = {
                    TRANSLATIONS[key][DEFAULT_LANG]: translated["fr"]
                    for key, translated in EXTRA.items()
                    if key in TRANSLATIONS and translated.get("fr")
                }
            except Exception:
                current = {}
        locale = {
            source: current[source] for source in expected
            if source in current and current[source].strip()
            and _fields(source) == _fields(current[source])
            and _markup_signature(source) == _markup_signature(current[source])
        }
        missing = sorted(expected - locale.keys())
        print(f"{lang}: translating {len(missing)} of {len(expected)} strings")
        path = LOCALES_DIR / f"{lang}.json"
        for offset in range(0, len(missing), batch_size):
            batch = missing[offset:offset + batch_size]
            translated = _translate_batch(batch, lang)
            locale.update(zip(batch, translated, strict=True))
            path.write_text(
                json.dumps(locale, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            print(f"  {min(offset + len(batch), len(missing))}/{len(missing)}")
        path.write_text(
            json.dumps(locale, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--translate", action="store_true")
    parser.add_argument("--batch", type=int, default=160)
    args = parser.parse_args()
    if args.translate:
        refresh_catalogs(max(1, args.batch))
    return 0 if check_catalogs() else 1


if __name__ == "__main__":
    raise SystemExit(main())
