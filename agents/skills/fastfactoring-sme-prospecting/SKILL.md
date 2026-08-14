---
name: fastfactoring-sme-prospecting
description: Source, normalize, filter, score, and export invoice-heavy SME prospect cohorts for FastFactoring. Use when reusing LiquidRound Baltic company data, assessing a registry or company database, building vertical lists, deduplicating legal entities, or preparing a sourced cohort for outreach. This skill is read-only with respect to source databases and never sends messages.
---

# FastFactoring SME Prospecting

## Purpose

Produce auditable company cohorts without losing registry identity, financial recency, or provenance. Read [schema-and-scoring.md](references/schema-and-scoring.md) before exporting data.

## Workflow

1. Read repository instructions for every source repository. Never display or copy database credentials.
2. Inventory the source before querying: location, owner, licence/terms, schema, row count, countries, refresh date, and contact-data provenance.
3. Define the cohort explicitly: market, verticals, legal form, employee/revenue range, active status, financial year, and exclusions.
4. Prefer deterministic registry identifiers. Deduplicate by `(country, reg_code)`, then flag—not silently merge—duplicate canonical domains.
5. Preserve raw sector code and description alongside `normalized_vertical`. Do not infer a medical or hospitality classification from a company name alone.
6. Record unknowns as empty values with a reason. Never fabricate revenue, employee count, contact, consent, or legal eligibility.
7. Score company fit separately from contact reachability. A high-fit company with no verified contact remains unsendable.
8. Export an immutable cohort and QA summary. Hand only approved columns to the outreach system; keep personal data minimized.

## LiquidRound Adapter

For the local Baltic JSON files, run:

```bash
python scripts/export_liquidround_baltics.py \
  --data-dir /path/to/FastPE/data \
  --countries EE,LT,LV \
  --verticals healthcare,hospitality,manufacturing,wholesale,construction,logistics \
  --min-revenue 1000000 --max-revenue 50000000 \
  --min-revenue-year 2023 \
  --output /tmp/fastfactoring-baltics.csv
```

The adapter reads only local JSON and emits company-level data, a saved QA report, and a classification-review queue. It enforces audited snapshot hashes and a minimum financial year, accepts an optional suppression file, and keeps every row `research_only`. It does not export named contacts, call a database, or send outreach. Inspect the QA report and review queue before using the cohort. Run focused tests with `python scripts/test_export_liquidround_baltics.py`.

## Acceptance Checks

- Every row has country, legal name, registry code, source, and source timestamp or explicit unknown.
- Financial values include currency, period, and source; the newest available valid period is selected.
- Cohort filters and input file hashes are captured in the QA report.
- No sole trader or individual is marked outreach-eligible without a recorded country-specific decision.
- Suppressed entities remain suppressed after imports and merges.
- Output contains no passwords, API keys, private database URLs, or unnecessary personal data.

## Handoff

Return the cohort path, filter specification, input counts, selected counts by country/vertical, missing-data rates, duplicates, provenance limitations, and blocked rows. Use the repository-local `fastfactoring-gtm-orchestrator` skill to approve the experiment and `fastfactoring-outreach` only after legal and copy gates pass.
