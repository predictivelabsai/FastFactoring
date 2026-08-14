"""Internationalisation catalogue, negotiation, and formatting regressions."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from fasthtml.common import Div, Input, P

from scripts.update_i18n import source_strings
from utils.i18n import (
    DEFAULT_ENABLED_LANGS, LANG_META, catalog, detect_language, format_currency,
    format_date, localize_tree, preserve, safe_return_path, t,
)
from utils.money import AVAILABLE_CURRENCIES, convert_amount, fmt_money


class InternationalisationTests(unittest.TestCase):
    def test_default_cohort_matches_fastclinic_and_disables_legacy_locales(self):
        self.assertEqual(
            DEFAULT_ENABLED_LANGS,
            ("en", "et", "de", "fr", "sv", "lv", "no", "da", "pl", "nl", "fi", "lt"),
        )
        self.assertNotIn("ru", DEFAULT_ENABLED_LANGS)
        self.assertNotIn("uz", DEFAULT_ENABLED_LANGS)
        self.assertIn("ru", LANG_META)
        self.assertIn("uz", LANG_META)

    def test_every_active_catalog_exactly_covers_source_copy(self):
        expected = source_strings()
        for lang in DEFAULT_ENABLED_LANGS[1:]:
            with self.subTest(lang=lang):
                translations = catalog(lang)
                self.assertEqual(set(translations), expected)
                self.assertTrue(all(value.strip() for value in translations.values()))

    def test_every_active_language_translates_primary_copy(self):
        source = t("hero_eyebrow", "en")
        for lang in DEFAULT_ENABLED_LANGS[1:]:
            with self.subTest(lang=lang):
                self.assertNotEqual(t("hero_eyebrow", lang), source)

    def test_browser_quality_and_region_are_respected(self):
        request = SimpleNamespace(headers={"accept-language": "en-US;q=0.4, et-EE;q=0.9, de;q=0.7"})
        self.assertEqual(detect_language(request, DEFAULT_ENABLED_LANGS), "et")

    def test_safe_return_path_rejects_open_redirects(self):
        self.assertEqual(safe_return_path("/pricing?plan=pro"), "/pricing?plan=pro")
        for target in ("https://example.com", "//example.com", "/%2fexample.com", "/\\example.com"):
            with self.subTest(target=target):
                self.assertEqual(safe_return_path(target), "/")

    def test_tree_localisation_preserves_marked_source_values(self):
        source_value = "Bespoke debtor name"
        tree = Div(P("Languages"), P(source_value), P(preserve("Languages")),
                   Input(placeholder="Display currency"))
        rendered = str(localize_tree(tree, "de"))
        self.assertIn(t("Languages", "de"), rendered)
        self.assertIn(source_value, rendered)
        self.assertIn(">Languages<", rendered)

    def test_locale_formatters_and_admin_currency_choices(self):
        self.assertEqual(AVAILABLE_CURRENCIES, ("USD", "EUR", "GBP"))
        self.assertEqual(format_currency(1234.5, "EUR", "de", 2), "1\u00a0234,50\u00a0€")
        self.assertEqual(format_date("2026-08-14", "de"), "14.08.2026")
        self.assertEqual(fmt_money(12_600, "USD"), "$1")
        self.assertEqual(fmt_money(13_700, "EUR"), "€1")
        self.assertEqual(fmt_money(16_000, "GBP"), "£1")
        self.assertEqual(convert_amount(25_200, "USD"), (2.0, "USD"))


if __name__ == "__main__":
    unittest.main()
