# Role Guides & Back-Office — Plan and Status

The user guide is a **single document with four persona parts** (EN:
`fastfactoring_user_guide.md`, retained RU: `fastfactoring_user_guide_ru.md`), each part on its own
page behind a coloured separator, with screenshots from the live left-nav
cockpit. (The earlier per-role split files were retired in favour of this.)

| Part | Persona | Primary screens |
|---|---|---|
| **1** | **Investor** | dashboard · marketplace · detail · portfolio · statement · auto-invest · AI reports |
| **2** | **Supplier (seller)** | my applications · AI triage |
| **3** | **Payer (debtor)** | invoices to confirm · reverse factoring |
| **4** | **Admin (back office)** | console · onboarding · risk · funding · collections · reports · audit · CRM · Drive · Docs · Mail |

## Back-office coverage vs the 8 functional areas

| # | Functional area | Screen(s) | Status |
|---|---|---|---|
| 1 | Client & debtor onboarding / limits | Onboarding | **Built (demo)** — KYC status, facility limits, SoD |
| 2 | Invoice processing & verification | Funding pipeline / detail | **Built (demo)** — grade, advance, status |
| 3 | Funding & disbursements | Funding | **Built (demo)** — SoD-gated approve + audit |
| 4 | Collections & credit management | Funding → collections | **Built (demo)** — dunning stages |
| 5 | Risk management & underwriting | Risk + Credit scoring | **Built (production)** — multi-signal score, adverse-action reasons, back-testing (actual vs expected default) |
| 6 | Accounting & financial ops | Accounting (GL) + Reports | **Built (production)** — double-entry ledger, trial balance, reconciliation |
| 7 | Reporting & analytics | Reports + copilot | **Built (production)** — DSO, default, recovery, dilution, monthly/sector volume, grade performance + grounded AI |
| 8 | Compliance, legal & audit | Compliance + Audit log | **Built (production)** — KYC coverage, retention schedule, regulatory checklist, audit CSV export |

## Deliverables in this pass
- Four role guides (markdown + PDF) with cockpit screenshots.
- 20 role-scoped screenshots regenerated in the new left-nav shell (USD).
- Back-office screens confirmed rendering in the cockpit with the copilot.

## Next phases (per `enterprise_extension_plan.md`)
1. **Real auth** — accounts, login, sessions, SSO/MFA (replaces the demo role switcher).
2. **Accounting/GL** — ledger entries, bank reconciliation, VAT (area 6).
3. **Credit-scoring engine** — multi-signal score + actual-vs-expected back-testing (deepens area 5).
4. **Integrations** — accounting (QB/Xero/1C), open banking, bureaus, e-sign, collections.
5. **Persist** the workspace modules (CRM/Drive/Docs/Mail) and audit to Postgres tables.
6. **Bilingual role guides** — regenerate es/fr/uz/ru variants.
