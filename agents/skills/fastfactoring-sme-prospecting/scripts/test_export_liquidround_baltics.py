#!/usr/bin/env python3
"""Focused tests for deterministic Baltic cohort normalization."""
from __future__ import annotations

import unittest
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from export_liquidround_baltics import (
    canonical_domain,
    canonical_entity_id,
    classify,
    latest_financial,
    load_suppressions,
    preliminary_score,
)


class ExportTests(unittest.TestCase):
    def test_latest_financial_uses_newest_year(self):
        company = {"financials": [{"year": 2022, "sales_revenue": 9}, {"year": 2024, "sales_revenue": 12}]}
        self.assertEqual(latest_financial(company), (12.0, 2024))

    def test_logistics_beats_broad_industrials(self):
        company = {"sector": "industrials", "sub_sector": "Freight forwarding"}
        primary, labels, _, method = classify(company, {"logistics", "manufacturing"})
        self.assertEqual(primary, "logistics")
        self.assertEqual(labels, ["logistics"])
        self.assertEqual(method, "sub_sector")

    def test_industry_code_beats_conflicting_source_label(self):
        company = {"emtak": "5510", "sector": "healthcare", "sub_sector": "Dental practice"}
        primary, labels, _, method = classify(company, {"hospitality", "medical_healthcare"})
        self.assertEqual(primary, "hospitality")
        self.assertEqual(labels, ["hospitality", "medical_healthcare"])
        self.assertEqual(method, "industry_code")

    def test_latvian_activity_is_classified(self):
        company = {"sub_sector": "General", "activity_description": "kravu pārvadājumi un noliktavu pakalpojumi"}
        primary, _, _, method = classify(company, {"logistics", "manufacturing"})
        self.assertEqual(primary, "logistics")
        self.assertEqual(method, "activity_description")

    def test_latvian_composite_label_defers_to_activity(self):
        company = {"sub_sector": "Logistics & Industry", "activity_description": "metālapstrāde un detaļu ražošana"}
        primary, _, _, method = classify(company, {"logistics", "manufacturing"})
        self.assertEqual(primary, "manufacturing")
        self.assertEqual(method, "activity_description")

    def test_broad_industrials_is_not_manufacturing(self):
        primary, _, _, _ = classify({"sector": "industrials", "sub_sector": "General"}, {"manufacturing"})
        self.assertIsNone(primary)

    def test_directory_domain_is_not_treated_as_company_domain(self):
        self.assertEqual(canonical_domain("https://kreedix.ee/example"), "")

    def test_suppression_ids_are_canonicalized(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "suppressions.csv"
            path.write_text("legal_entity_id\nEE:123-456\n", encoding="utf-8")
            ids, metadata = load_suppressions(path)
        self.assertEqual(ids, {"EE:123456"})
        self.assertEqual(metadata["valid_ids"], 1)

    def test_bad_suppression_headers_fail_closed(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "suppressions.csv"
            path.write_text("company\nExample\n", encoding="utf-8")
            with self.assertRaises(SystemExit):
                load_suppressions(path)

    def test_financial_age_changes_score_and_score_is_capped(self):
        recent, _ = preliminary_score(2_000_000, 2025, 20, "example.com", "industry_code", as_of_year=2026)
        stale, _ = preliminary_score(2_000_000, 2023, 20, "example.com", "industry_code", as_of_year=2026)
        self.assertGreater(recent, stale)
        self.assertLessEqual(recent, 50)

    def test_entity_id_normalization(self):
        self.assertEqual(canonical_entity_id("ee:123-456"), "EE:123456")

    def test_cli_artifacts_hash_gate_and_no_clobber(self):
        script = Path(__file__).with_name("export_liquidround_baltics.py")
        with TemporaryDirectory() as directory:
            root = Path(directory)
            records = [
                {"name": "Older Logistics OÜ", "reg_code": "123", "emtak": "4941", "sub_sector": "Dental practice", "financials": [{"year": 2023, "sales_revenue": 1_500_000}]},
                {"name": "Newer Logistics OÜ", "reg_code": "123", "emtak": "4941", "sub_sector": "Dental practice", "financials": [{"year": 2025, "sales_revenue": 2_000_000}]},
                {"name": "Hotel OÜ", "reg_code": "456", "emtak": "5510", "sub_sector": "Other healthcare", "financials": [{"year": 2025, "sales_revenue": 2_500_000}]},
            ]
            (root / "ee_companies.json").write_text(json.dumps(records), encoding="utf-8")
            output = root / "cohort.csv"
            command = [
                sys.executable, str(script), "--data-dir", str(root), "--countries", "EE",
                "--verticals", "healthcare,hospitality,logistics", "--min-revenue", "1000000",
                "--max-revenue", "50000000", "--min-revenue-year", "2023",
                "--source-retrieved-at", "2026-01-01", "--allow-unverified-snapshot",
                "--output", str(output),
            ]
            first = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(first.returncode, 0, first.stderr)
            qa = json.loads((root / "cohort.qa.json").read_text())
            with output.open(newline="", encoding="utf-8") as handle:
                cohort = list(csv.DictReader(handle))
            self.assertEqual(len(cohort), 2)
            self.assertTrue(all(row["eligibility_status"] == "research_only" for row in cohort))
            self.assertTrue(all(row["classification_status"] == "conflict_requires_review" for row in cohort))
            self.assertEqual(qa["duplicate_review_rows"], 1)
            self.assertEqual(qa["inputs"][0]["source_retrieved_at"], "2026-01-01")
            self.assertIn("upstream source licence verification for commercial outreach", qa["promotion_blockers"])
            self.assertEqual(qa["output_sha256"], hashlib.sha256(output.read_bytes()).hexdigest())
            self.assertEqual(qa["classification_review_sha256"], hashlib.sha256((root / "cohort.classification-review.csv").read_bytes()).hexdigest())
            self.assertEqual(qa["duplicate_review_sha256"], hashlib.sha256((root / "cohort.duplicate-review.csv").read_bytes()).hexdigest())
            no_clobber = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertNotEqual(no_clobber.returncode, 0)
            self.assertIn("already exists", no_clobber.stderr)
            refused = subprocess.run(
                [item for item in command if item != "--allow-unverified-snapshot"][:-2] + ["--output", str(root / "refused.csv")],
                capture_output=True, text=True, check=False,
            )
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn("hash mismatch", refused.stderr.lower())


if __name__ == "__main__":
    unittest.main()
