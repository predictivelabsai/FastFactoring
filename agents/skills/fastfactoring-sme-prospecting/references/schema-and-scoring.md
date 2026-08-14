# Prospect schema and scoring

## Canonical company fields

| Group | Fields |
|---|---|
| Identity | `country`, `reg_code`, `legal_name`, `legal_form`, `active_status`, `canonical_domain` |
| Classification | `industry_code`, `industry_label`, `normalized_vertical`, `sub_vertical` |
| Scale | `revenue`, `revenue_currency`, `revenue_year`, `employees`, `employees_year` |
| Qualification | `b2b_evidence`, `invoice_terms_signal`, `growth_signal`, `fit_score`, `fit_reasons` |
| Governance | `source_name`, `source_url`, `source_licence`, `source_checked_at`, `record_hash` |
| Eligibility | `entity_class`, `lawful_basis`, `policy_version`, `eligibility_status`, `eligibility_reason` |

Contacts belong in a separate minimized table keyed to company identity. Store role, source, verification status/date, and suppression state. Do not put a named contact into a campaign merely because a company is eligible.

## Vertical normalization

Retain original codes. Normalize only when evidence supports the mapping:

- `medical_healthcare`: clinics serving organizations, medical devices, diagnostics, care providers, pharma/medical wholesale, outsourced healthcare services;
- `hospitality`: hotels, accommodation groups, catering, food-service suppliers, facilities and hospitality technology;
- `manufacturing`, `wholesale`, `construction`, `logistics`, `business_services`, `food_agriculture`, `energy`.

Separate likely **suppliers** from likely **payers**. A large retailer or hotel group may be a payer-led programme prospect rather than an SME factoring prospect.

## Company fit score (100)

- Invoice fit, 30: recurring B2B invoices, payment terms, debtor quality evidence.
- Vertical fit, 20: approved invoice-heavy vertical and clear supplier/payer role.
- Scale fit, 20: target employee/revenue band, neither micro-consumer nor enterprise-only.
- Timing signal, 15: contract win, expansion, hiring, new site, stock build, tender award, seasonality.
- Data confidence, 15: active registry record, recent financials, source provenance, canonical domain.

Cap at 50 if a whole category is unknown. Reachability is a separate field; it does not inflate company fit.

## Required identity rule

`legal_entity_id = upper(country) + ':' + normalized(reg_code)`

Use this key across imports. Domain is a secondary clustering signal because groups and brands can share domains. Never deduplicate on company name alone.
