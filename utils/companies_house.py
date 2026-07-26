"""Small Companies House client for supplier-registration assistance."""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request

from utils.config import settings

_BASE = "https://api.company-information.service.gov.uk"


def _get(path: str, params: dict | None = None) -> dict:
    key = settings().ch_api_key
    if not key:
        raise RuntimeError("CH_API_KEY is not configured")
    query = f"?{urllib.parse.urlencode(params)}" if params else ""
    auth = base64.b64encode(f"{key}:".encode()).decode()
    req = urllib.request.Request(
        f"{_BASE}{path}{query}",
        headers={"Authorization": f"Basic {auth}", "Accept": "application/json",
                 "User-Agent": "Factorio/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {}
        raise RuntimeError(f"Companies House returned HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise RuntimeError("Companies House lookup is temporarily unavailable") from exc


def _address(value: dict) -> str:
    keys = ("premises", "address_line_1", "address_line_2", "locality",
            "region", "postal_code", "country")
    return ", ".join(str(value.get(key)).strip() for key in keys if value.get(key))


def enrich_supplier(company_name: str, company_number: str = "") -> dict:
    """Resolve a UK company profile and active directors by number or name."""
    number = "".join(ch for ch in str(company_number or "").upper() if ch.isalnum())
    if not number and company_name:
        results = _get("/search/companies", {"q": company_name, "items_per_page": 5}).get("items", [])
        wanted = " ".join(company_name.upper().split())
        exact = [item for item in results
                 if " ".join(str(item.get("title", "")).upper().split()) == wanted]
        candidates = exact or [item for item in results if item.get("company_status") == "active"] or results
        number = str((candidates[0] if candidates else {}).get("company_number") or "")
    if not number:
        return {}
    profile = _get(f"/company/{urllib.parse.quote(number)}")
    if not profile:
        return {}
    officers = _get(f"/company/{urllib.parse.quote(number)}/officers",
                    {"items_per_page": 50}).get("items", [])
    directors = [
        {"name": str(item.get("name") or ""), "appointed_on": item.get("appointed_on")}
        for item in officers
        if item.get("officer_role") in {"director", "corporate-director"}
        and not item.get("resigned_on")
    ][:5]
    return {
        "company_name": profile.get("company_name") or company_name,
        "company_number": profile.get("company_number") or number,
        "company_status": profile.get("company_status") or "",
        "registered_address": _address(profile.get("registered_office_address") or {}),
        "directors": directors,
    }
