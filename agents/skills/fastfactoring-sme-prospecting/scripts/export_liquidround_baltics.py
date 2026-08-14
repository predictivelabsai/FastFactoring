#!/usr/bin/env python3
"""Export a research-only Baltic company cohort from audited FastPE JSON snapshots."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

FILES = {"EE": "ee_companies.json", "LT": "lt_companies.json", "LV": "lv_companies.json"}
AUDITED_HASHES = {
    "EE": "0889db3025baa44a08b751c89fbf13330f20af6d39959da86082bf3f5098d1a0",
    "LT": "1cdd31c8ffddf9f8ab41ee3f6c481a779e91ec94e02f8fde6e2ad727560cbbb3",
    "LV": "7240ecb009919161985773e3596124f7679929459fd080d4794e0750951e343f",
}
TAXONOMY_VERSION = "fastfactoring-baltic-v1"
DIRECTORY_DOMAINS = {"kreedix.ee", "ssb.ee", "rekvizitai.vz.lt", "rekvizitai.lt"}
AMBIGUOUS_CLASSIFICATIONS = {"general", "logistics & industry", "consumer", "business services"}
VERTICAL_ORDER = (
    "medical_healthcare",
    "hospitality",
    "logistics",
    "construction",
    "wholesale",
    "manufacturing",
)
VERTICAL_TERMS = {
    "medical_healthcare": (
        "health", "medical", "clinic", "care", "pharma", "diagnostic", "dental", "veterinar",
        "medicīn", "veselīb", "ārstniec", "zobārstn", "aptiek", "farmac", "veterinār", "klīnik", "slimnīc",
    ),
    "hospitality": (
        "hospitality", "hotel", "accommodation", "catering", "restaurant", "food service", "spa", "tour operator",
        "viesnīc", "restorān", "ēdināšan", "izmitināšan", "tūris",
    ),
    "logistics": (
        "logistics", "transport", "freight", "warehous", "cargo", "haulage", "shipping",
        "loģistik", "noliktav", "pārvadāj", "kravu",
    ),
    "construction": ("construction", "building contractor", "civil engineering", "būvniecīb", "celtniecīb"),
    "wholesale": ("wholesale", "distribut", "vairumtirdz"),
    "manufacturing": ("manufactur", "production", "fabricated", "machinery", "ražošan", "metālapstrād", "mašīnbūv"),
}
NACE_PREFIXES = {
    "medical_healthcare": {"75", "86", "87", "88"},
    "hospitality": {"55", "56"},
    "logistics": {"49", "50", "51", "52", "53"},
    "construction": {"41", "42", "43"},
    "wholesale": {"46"},
    "manufacturing": {str(value) for value in range(10, 34)},
}
SOURCE_NOTES = {
    "EE": {"upstream": "https://ssb.ee", "licence": "unknown; verify source terms before commercial reuse"},
    "LT": {"upstream": "https://rekvizitai.vz.lt", "licence": "unknown; verify source terms before commercial reuse"},
    "LV": {"upstream": "https://data.gov.lv", "licence": "unverified; FastPE scraper docstring claims CC0"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--countries", default="EE,LT,LV")
    parser.add_argument("--verticals", default=",".join(VERTICAL_ORDER))
    parser.add_argument("--min-revenue", type=float, default=1_000_000)
    parser.add_argument("--max-revenue", type=float, default=50_000_000)
    parser.add_argument("--min-revenue-year", type=int, required=True, help="Explicit oldest accepted annual financial year")
    parser.add_argument("--min-employees", type=int)
    parser.add_argument("--max-employees", type=int, default=249)
    parser.add_argument("--suppression-file", type=Path, help="CSV containing legal_entity_id or country+reg_code")
    parser.add_argument("--source-retrieved-at", default="unknown", help="Documented snapshot retrieval date, or unknown")
    parser.add_argument("--allow-unverified-snapshot", action="store_true", help="Allow hash mismatch and flag it in QA")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--qa-output", type=Path)
    parser.add_argument("--classification-review-output", type=Path)
    parser.add_argument("--duplicate-review-output", type=Path)
    parser.add_argument("--overwrite", action="store_true", help="Replace existing output artifacts")
    return parser.parse_args()


def number(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if not value:
        return None
    match = re.search(r"-?[\d\s,.]+", str(value))
    if not match:
        return None
    token = match.group(0).replace(" ", "").replace(",", ".")
    try:
        return float(token)
    except ValueError:
        return None


def latest_financial(company: dict) -> tuple[float | None, int | None]:
    items = company.get("financials")
    if isinstance(items, dict):
        items = [items]
    valid: list[tuple[int, float]] = []
    for item in items or []:
        revenue = number(item.get("sales_revenue") if "sales_revenue" in item else item.get("revenue"))
        year = number(item.get("year"))
        if revenue is not None and year:
            valid.append((int(year), revenue))
    direct = number(company.get("sales_revenue"))
    direct_year = number(company.get("sales_year"))
    if direct is not None and direct_year:
        valid.append((int(direct_year), direct))
    if not valid:
        return None, None
    year, revenue = max(valid, key=lambda item: item[0])
    return revenue, year


def canonical_domain(value: object) -> str:
    parts = str(value or "").strip().split()
    if not parts:
        return ""
    parsed = urlparse(parts[0] if "://" in parts[0] else f"https://{parts[0]}")
    domain = (parsed.hostname or "").lower().removeprefix("www.")
    return "" if domain in DIRECTORY_DOMAINS else domain


def nace_prefix(company: dict) -> str:
    raw = re.sub(r"\D", "", str(company.get("emtak") or company.get("nace") or ""))
    if not raw:
        return ""
    return raw[:2]


def canonical_entity_id(value: str) -> str:
    if ":" not in value:
        return ""
    country, code = value.split(":", 1)
    country = re.sub(r"[^A-Z]", "", country.upper())
    code = re.sub(r"[^A-Z0-9]", "", code.upper())
    return f"{country}:{code}" if len(country) == 2 and code else ""


def classify(company: dict, allowed: set[str]) -> tuple[str | None, list[str], str, str]:
    """Return deterministic primary label, all labels, evidence, and method."""
    labels: list[str] = []
    evidence: list[str] = []
    prefix = nace_prefix(company)
    primary: str | None = None
    method = ""
    if prefix:
        for vertical in VERTICAL_ORDER:
            if prefix in NACE_PREFIXES[vertical]:
                if vertical in allowed:
                    labels.append(vertical)
                    evidence.append(f"industry_code:{company.get('emtak') or company.get('nace')}")
                    primary = vertical
                    method = "industry_code"
                    break
                return None, [], f"industry_code:{company.get('emtak') or company.get('nace')}", "industry_code_outside_scope"
        if not primary:
            # A present industry code is stronger than the scraped source label;
            # unknown codes go to review rather than falling through to a conflicting label.
            return None, [], f"industry_code:{company.get('emtak') or company.get('nace')}", "industry_code_unmapped"
    if not prefix or primary:
        # Specific classifications and original activity text are useful;
        # broad source sectors such as `industrials` and fallback `General` are not.
        candidates = (
            ("sub_sector", str(company.get("sub_sector") or "")),
            ("categories", json.dumps(company.get("categories") or "", ensure_ascii=False)),
            ("activity_description", str(company.get("activity_description") or "")),
        )
        for field, raw_text in candidates:
            text = raw_text.lower()
            if not text or text.strip().lower() in AMBIGUOUS_CLASSIFICATIONS:
                continue
            field_labels: list[str] = []
            for vertical in VERTICAL_ORDER:
                if vertical in allowed and any(term in text for term in VERTICAL_TERMS[vertical]):
                    if vertical not in labels:
                        labels.append(vertical)
                    field_labels.append(vertical)
            if field_labels:
                evidence.append(f"{field}:{raw_text}")
                if primary is None:
                    primary = field_labels[0]
                    method = field
    return primary, labels, " | ".join(evidence), method


def load_suppressions(path: Path | None) -> tuple[set[str], dict]:
    if not path:
        return set(), {"path": None, "sha256": None, "input_rows": 0, "valid_ids": 0, "invalid_rows": 0}
    suppressed: set[str] = set()
    raw_bytes = path.read_bytes()
    input_rows = 0
    invalid_rows = 0
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        headers = set(reader.fieldnames or [])
        if "legal_entity_id" not in headers and not {"country", "reg_code"}.issubset(headers):
            raise SystemExit("Suppression CSV must contain legal_entity_id or country and reg_code headers")
        for row in reader:
            input_rows += 1
            entity_id = canonical_entity_id(str(row.get("legal_entity_id") or "").strip())
            if not entity_id and row.get("country") and row.get("reg_code"):
                entity_id = canonical_entity_id(f"{row['country']}:{row['reg_code']}")
            if entity_id:
                suppressed.add(entity_id)
            else:
                invalid_rows += 1
    if input_rows and not suppressed:
        raise SystemExit("Suppression CSV contained rows but no valid legal entity IDs")
    return suppressed, {
        "path": str(path),
        "sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "input_rows": input_rows,
        "valid_ids": len(suppressed),
        "invalid_rows": invalid_rows,
    }


def preliminary_score(revenue: float, year: int, employees: float | None, domain: str, method: str, as_of_year: int | None = None) -> tuple[int, str]:
    score = 15 if 1_000_000 <= revenue <= 10_000_000 else 10
    reasons = ["revenue_A_band" if score == 15 else "revenue_B_band"]
    age = (as_of_year or datetime.now(timezone.utc).year) - year
    if age <= 1:
        score += 10
        reasons.append("financials_within_1_year")
    elif age == 2:
        score += 5
        reasons.append("financials_2_years_old")
    else:
        reasons.append(f"financials_{max(age, 0)}_years_old")
    score += 10 if method == "industry_code" else 5
    reasons.append(f"classification_{method or 'unknown'}")
    if employees is not None and 5 <= employees <= 249:
        score += 5
        reasons.append("employee_SME_band")
    if domain:
        score += 5
        reasons.append("organization_domain_unverified")
    # Invoice/debtor fit, active status, and contact verification remain unknown;
    # this preliminary score can never exceed the missing-data ceiling of 50.
    return min(score, 50), ";".join(reasons)


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def record_quality(company: dict) -> tuple[int, int, int, str]:
    revenue, year = latest_financial(company)
    completeness = sum(bool(company.get(key)) for key in ("website", "employees", "employees_text", "sector", "sub_sector", "activity_description"))
    digest = hashlib.sha256(json.dumps(company, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return int(year or 0), int(revenue is not None), completeness, digest


def main() -> int:
    args = parse_args()
    countries = {value.strip().upper() for value in args.countries.split(",") if value.strip()}
    unknown_countries = countries - FILES.keys()
    if unknown_countries:
        raise SystemExit(f"Unsupported countries: {', '.join(sorted(unknown_countries))}")
    aliases = {"healthcare": "medical_healthcare", "medical": "medical_healthcare"}
    verticals = {aliases.get(value.strip().lower(), value.strip().lower()) for value in args.verticals.split(",") if value.strip()}
    unknown_verticals = verticals - set(VERTICAL_ORDER)
    if unknown_verticals:
        raise SystemExit(f"Unsupported verticals: {', '.join(sorted(unknown_verticals))}")

    qa_path = args.qa_output or args.output.with_name(f"{args.output.stem}.qa.json")
    review_path = args.classification_review_output or args.output.with_name(f"{args.output.stem}.classification-review.csv")
    duplicate_path = args.duplicate_review_output or args.output.with_name(f"{args.output.stem}.duplicate-review.csv")
    for artifact in (args.output, qa_path, review_path, duplicate_path):
        if artifact.exists() and not args.overwrite:
            raise SystemExit(f"Output artifact already exists: {artifact}; choose a new path or pass --overwrite")

    suppressions, suppression_meta = load_suppressions(args.suppression_file)
    rows: list[dict] = []
    seen: set[str] = set()
    source_entity_ids: set[str] = set()
    duplicate_review: list[dict] = []
    exclusions: Counter[str] = Counter()
    inputs: list[dict] = []
    loaded = 0
    for country in sorted(countries):
        path = args.data_dir / FILES[country]
        raw_bytes = path.read_bytes()
        digest = hashlib.sha256(raw_bytes).hexdigest()
        verified = digest == AUDITED_HASHES[country]
        if not verified and not args.allow_unverified_snapshot:
            raise SystemExit(f"Snapshot hash mismatch for {country}; audit it or pass --allow-unverified-snapshot")
        companies = json.loads(raw_bytes)
        loaded += len(companies)
        inputs.append({
            "country": country,
            "path": str(path),
            "rows": len(companies),
            "sha256": digest,
            "expected_sha256": AUDITED_HASHES[country],
            "snapshot_verified": verified,
            "snapshot_file_mtime": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
            "source_retrieved_at": args.source_retrieved_at,
            **SOURCE_NOTES[country],
        })
        grouped: dict[str, list[dict]] = {}
        for company in companies:
            reg_code = str(company.get("reg_code") or "").strip()
            legal_name = str(company.get("name") or "").strip()
            if not reg_code or not legal_name:
                exclusions["missing_identity"] += 1
                continue
            entity_id = canonical_entity_id(f"{country}:{reg_code}")
            grouped.setdefault(entity_id, []).append(company)
            source_entity_ids.add(entity_id)
        for entity_id, records in grouped.items():
            ranked = sorted(records, key=record_quality, reverse=True)
            company = ranked[0]
            reg_code = str(company.get("reg_code") or "").strip()
            legal_name = str(company.get("name") or "").strip()
            if len(ranked) > 1:
                exclusions["duplicate_legal_entity_id"] += len(ranked) - 1
                selected_hash = hashlib.sha256(json.dumps(company, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
                for dropped in ranked[1:]:
                    duplicate_review.append({
                        "legal_entity_id": entity_id,
                        "selected_legal_name": legal_name,
                        "selected_record_hash": selected_hash,
                        "selected_quality": repr(record_quality(company)[:-1]),
                        "dropped_legal_name": str(dropped.get("name") or ""),
                        "dropped_record_hash": hashlib.sha256(json.dumps(dropped, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
                        "dropped_quality": repr(record_quality(dropped)[:-1]),
                        "review_reason": "duplicate registry ID with differing source records",
                    })
            if entity_id in seen:
                exclusions["cross_input_duplicate_legal_entity_id"] += 1
                continue
            seen.add(entity_id)
            if entity_id in suppressions:
                exclusions["suppressed"] += 1
                continue
            vertical, all_verticals, classification_evidence, method = classify(company, verticals)
            if not vertical:
                exclusions["no_supported_classification"] += 1
                continue
            revenue, revenue_year = latest_financial(company)
            if revenue is None or revenue_year is None:
                exclusions["missing_annual_revenue"] += 1
                continue
            if revenue_year < args.min_revenue_year:
                exclusions["stale_financial_year"] += 1
                continue
            if not args.min_revenue <= revenue <= args.max_revenue:
                exclusions["outside_revenue_band"] += 1
                continue
            employees = number(company.get("employees") or company.get("employees_text"))
            if args.min_employees is not None and (employees is None or employees < args.min_employees):
                exclusions["below_or_unknown_employee_floor"] += 1
                continue
            if employees is not None and args.max_employees is not None and employees > args.max_employees:
                exclusions["above_employee_ceiling"] += 1
                continue
            domain = canonical_domain(company.get("website"))
            score, fit_reasons = preliminary_score(revenue, revenue_year, employees, domain, method)
            rows.append({
                "legal_entity_id": entity_id,
                "country": country,
                "reg_code": reg_code,
                "legal_name": legal_name,
                "legal_form": "unknown",
                "entity_class": "unknown_requires_review",
                "canonical_domain": domain,
                "domain_shared": "",
                "raw_industry_code": str(company.get("emtak") or company.get("nace") or ""),
                "raw_sector": str(company.get("sector") or ""),
                "raw_sub_sector": str(company.get("sub_sector") or ""),
                "raw_categories": json.dumps(company.get("categories") or "", ensure_ascii=False),
                "raw_activity_description": str(company.get("activity_description") or ""),
                "normalized_vertical": vertical,
                "candidate_verticals": ";".join(all_verticals),
                "classification_method": method,
                "classification_evidence": classification_evidence,
                "classification_status": "conflict_requires_review" if len(all_verticals) > 1 else "source_label_unverified",
                "revenue": f"{revenue:.2f}",
                "revenue_currency": "EUR",
                "revenue_year": revenue_year,
                "employees": int(employees) if employees is not None else "",
                "preliminary_fit_score": score,
                "fit_reasons": fit_reasons,
                "invoice_fit": "unknown_requires_enrichment",
                "supplier_or_payer": "unknown_requires_enrichment",
                "reachability": "unverified",
                "source_name": "Baltic company JSON snapshot",
                "source_repository": str(args.data_dir.parent),
                "source_input_file": str(path),
                "source_upstream": SOURCE_NOTES[country]["upstream"],
                "source_licence": SOURCE_NOTES[country]["licence"],
                "source_retrieved_at": args.source_retrieved_at,
                "snapshot_file_mtime": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
                "source_record_hash": hashlib.sha256(json.dumps(company, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
                "active_status": "unknown_requires_registry_check",
                "eligibility_status": "research_only",
                "eligibility_reason": "active status, classification, invoice fit, entity class, contact and legal basis not approved",
            })

    domain_counts = Counter(row["canonical_domain"] for row in rows if row["canonical_domain"])
    for row in rows:
        row["domain_shared"] = "true" if row["canonical_domain"] and domain_counts[row["canonical_domain"]] > 1 else "false"
    rows.sort(key=lambda row: (row["country"], -int(row["preliminary_fit_score"]), row["legal_entity_id"]))
    fields = list(rows[0]) if rows else ["legal_entity_id", "country", "reg_code", "legal_name"]
    write_csv(args.output, rows, fields)
    output_hash = hashlib.sha256(args.output.read_bytes()).hexdigest()

    review_fields = ["legal_entity_id", "country", "legal_name", "raw_industry_code", "raw_sector", "raw_sub_sector", "raw_activity_description", "normalized_vertical", "candidate_verticals", "classification_method", "classification_evidence", "classification_status"]
    write_csv(review_path, [{field: row.get(field, "") for field in review_fields} for row in rows], review_fields)
    review_hash = hashlib.sha256(review_path.read_bytes()).hexdigest()
    duplicate_fields = ["legal_entity_id", "selected_legal_name", "selected_record_hash", "selected_quality", "dropped_legal_name", "dropped_record_hash", "dropped_quality", "review_reason"]
    write_csv(duplicate_path, duplicate_review, duplicate_fields)
    duplicate_hash = hashlib.sha256(duplicate_path.read_bytes()).hexdigest()

    missing_domain = sum(not row["canonical_domain"] for row in rows)
    missing_employees = sum(row["employees"] == "" for row in rows)
    shared_domains = {domain: count for domain, count in domain_counts.items() if count > 1}
    report = {
        "schema_version": 1,
        "taxonomy_version": TAXONOMY_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "filters": {
            "countries": sorted(countries),
            "verticals": [value for value in VERTICAL_ORDER if value in verticals],
            "min_revenue": args.min_revenue,
            "max_revenue": args.max_revenue,
            "min_revenue_year": args.min_revenue_year,
            "min_employees": args.min_employees,
            "max_employees": args.max_employees,
            "source_retrieved_at": args.source_retrieved_at,
        },
        "loaded": loaded,
        "selected": len(rows),
        "selected_by_country": dict(sorted(Counter(row["country"] for row in rows).items())),
        "selected_by_vertical": dict(sorted(Counter(row["normalized_vertical"] for row in rows).items())),
        "selected_by_classification_status": dict(sorted(Counter(row["classification_status"] for row in rows).items())),
        "exclusions": dict(sorted(exclusions.items())),
        "missing_data": {"canonical_domain": missing_domain, "employees": missing_employees},
        "shared_domains": shared_domains,
        "suppression": {
            **suppression_meta,
            "matched_ids": len(suppressions & source_entity_ids),
            "unmatched_ids": sorted(suppressions - source_entity_ids),
        },
        "inputs": inputs,
        "output": str(args.output),
        "output_sha256": output_hash,
        "classification_review_output": str(review_path),
        "classification_review_sha256": review_hash,
        "duplicate_review_output": str(duplicate_path),
        "duplicate_review_sha256": duplicate_hash,
        "duplicate_review_rows": len(duplicate_review),
        "provenance_limitations": [
            "source retrieval date is unknown unless explicitly documented",
            "EE and LT commercial reuse terms require verification",
            "LV CC0 status is an unverified claim in the source scraper",
            "active status and source classifications require independent registry checks",
        ],
        "promotion_blockers": [
            "active status", "classification review", "invoice/debtor fit", "supplier/payer role",
            "entity class and lawful basis", "organization contact verification", "suppression and copy gates",
            "upstream source licence verification for commercial outreach",
        ],
    }
    qa_path.parent.mkdir(parents=True, exist_ok=True)
    qa_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
