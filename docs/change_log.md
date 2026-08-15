# Change Log

## 2026-08-15 — v2.0.1

- Fixed FastFactoring and Factorio authentication branding, the admin top bar, and reliable admin preview switching and exit.
- Bound Supplier, Investor, and Payer demo actions to synthetic records, including the Factorio Supplier company scope.
- Resolved investor identities from each request across marketplace, portfolio, statements, auctions, and auto-invest views.
- Added an isolated real-Chrome suite covering registration, verification, password reset, Team governance, all role previews, and Factorio demos.

## 2026-08-15 — v2.0.0

- Replaced session-carried roles with database-backed access profiles, exact Supplier, Investor, Payer, and sole-admin authorization, plus record-level supplier, investor, and payer scopes.
- Added audited admin role preview with fixed synthetic personas, a persistent preview banner, and safeguards against real-record or external side effects.
- Added public non-admin registration, verification and password reset tokens, Google onboarding for every public role, and Factorio-only one-click demo accounts.
- Added Governance Team invitations and role management, including payer-company linkage, and refreshed all 11 enabled language catalogues.
- Applied the additive access-control migration to DATABASE_URL_PROD and added Postmark/public-URL production configuration.
- Migrated and table-by-table verified all 33 legacy Factorio tables and 791 synthetic rows on DATABASE_URL_PROD; removed the remaining legacy marketplace-brand documents and references.

## 2026-08-15 — v1.1.1

- Added trusted dual-brand Google OAuth callback selection for FastFactoring and Factorio, with host-header fallback protection.
- Added a database-independent production health endpoint for Coolify deployment checks.

## 2026-08-14 — v1.1.0

- Repositioned FastFactoring as the open-source platform while keeping Factorio as the standalone reference demo and application brand.
- Added admin-controlled availability for 12 production languages, with Russian and Uzbek retained but disabled by default, and refreshed 562 UI strings in every active catalogue.
- Added four-role RBAC, the single named administrator, test-admin authentication, Google SSO, and admin-controlled EUR, GBP, or USD display currency.
- Added DATABASE_URL_PROD migration tooling and a documented synthetic-data migration and verification plan; production migration remains an explicit operator action.
- Added a sourced multi-country GTM plan plus framework-agnostic prospecting and guarded-outreach skills under agents/skills; live outreach remains blocked pending sender and transactional suppression controls.

## 2026-07-27 — v1.0.0

- Established the Factorio AI Platform Demo as the initial versioned baseline.
- Added a repository release skill that applies Semantic Versioning and requires every release bump to update this change log in the same commit.
- Kept documentation-only, screenshot, evaluation, and archive commits from creating artificial release churn.

## 2026-07-26 — Borrower transactional email skills

- Added Factorio-branded Markdown templates under `email/templates/` for paused bank connections and optional QuickBooks, Xero, or Sage connections.
- Added a Customer Service agent skill that renders personalized, HTTPS-linked drafts from the checked-in templates without claiming delivery.
- Added an Admin preview at `/app/mail/templates`. Postmark sending remains disabled until a server token, verified sender, lifecycle approval controls, and delivery webhooks are configured.

## 2026-07-26 — Investor AI

- Specialized the Investor default chat as **Investor AI**, with portfolio-focused onboarding and suggested questions about performance, concentration, upcoming payments, and risk.
- Grounded answers in the selected investor's positions and saved Auto-invest preferences, including multi-turn chat history.
- Upgraded Auto-invest with conservative, balanced, and growth profiles plus grade, term, return, debtor-concentration, sector, and per-invoice limits. It ranks eligible invoices and explains each proposal without placing funds.
- Added eight Investor AI and Auto-invest scenarios to the xAI-judged agent evaluation suite, bringing coverage to 120 cases across 15 agents.
- Grounded each response in the currently selected investor's own positions and computed portfolio metrics, with saved multi-turn history passed into the conversation.

## 2026-07-26 — Full Agent Fleet evaluation suite

- Added 112 reviewed evaluation conversations: eight for each of 14 agents, covering domain quality, grounding, approvals, prompt injection, secrets, and multi-turn context.
- Added an evaluation-safe fleet mode that disables mutating tools while preserving read and safe draft tools.
- Added an xAI LLM judge for every case and exact result columns: `user_prompt`, `expected_answer`, `ai_answer`, `agent_type`, `results`.

## 2026-07-26 — Marketing agents, skills editor, and grouped navigation

- Added dedicated **SEO & AI Search** and **Paid Marketing** specialists to the existing Admin Agent Fleet with read/draft-only tools and editable prompt files.
- Added an Admin Agent Skills editor for viewing, editing, versioning, and reverting every fleet agent's live instructions; database overrides survive deployments and saves are audited.
- Reorganized Investor and Admin navigation into logical role-scoped groups. Sections support persisted `>` minimize and `<` maximize controls and keep the active route visible.

## 2026-07-26 — Supplier bank and accounting connections

- Added Lloyds Bank to the Supplier Profile as a planned, consent-based Open Banking connection.
- Added clearly labelled hypothetical QuickBooks, Xero, and Sage accounting integration cards; no external account is represented as connected.

## 2026-07-26 — Site-wide favicon

- Added a green diamond Factorio favicon to marketing, authentication, application, and public shared-chat pages.

## 2026-07-26 — Supplier pre-approval and Companies House follow-up

- Invoice upload now presents a clear **You’re pre-approved!** message with the indicative financing offer.
- Added a follow-up form for contact email, optional phone, company number, registered address, and director confirmation before offer acceptance.
- Added Companies House enrichment through `CH_API_KEY`: missing UK registration data is resolved by number or company-name search, and active directors are retrieved to assist registration.
- Persisted the confirmed supplier contact and registry details with accepted invoice applications.

## 2026-07-26 — Descriptive financing PDF filenames

- Generated term sheets and financing contracts now use portable filenames containing the supplier slug, Factorio reference, generation date, and document type.

## 2026-07-26 — Global display currency

- Set USD as the platform default display currency instead of UZS.
- Added an Admin-only global setting for USD, GBP, EUR, or UZS. The persisted override applies to shared monetary views while leaving source invoice currencies unchanged.

## 2026-07-26 — Shareable chats and supplier profile

- Added **Copy** and **Share** controls to Factorio AI for every role. Share creates an immutable, read-only public snapshot with an unguessable URL and copies the link to the clipboard.
- Shared snapshots store bounded plain text rather than executable chat HTML.
- Added a supplier-only **My Profile** page with clearly synthetic company, contact, and settlement-bank details.

## 2026-07-26 — AI invoice extraction and financing origination

- Moved all Factorio AI system instructions out of Python into editable, versioned Markdown files under `prompts/`, loaded through `utils/prompts.py`.
- Added **Download PDF**, **Accept**, and **Change** controls to the chat term sheet. Suppliers can revise the amount paid today and financing period; accepted applications persist the revised terms.
- Reworked the supplier default into a single **Factorio AI** chat with paperclip upload; removed supplier Triage and Marketplace navigation.
- The chat now presents an indicative financing offer table (advance paid today, term and monthly-cost disclosure), with optional bank-statement upload and Open Banking follow-up.
- Accepted offers appear in **My applications** with a generated one-page synthetic financing agreement between Factorio Ltd and the extracted supplier.
- Added a supplier-facing invoice upload workflow at `/app/seller` for PDF, PNG, JPEG, JSON, and text documents.
- Added Grok/xAI extraction using `prompts/invoice_financing_extraction.md`, temperature-zero JSON output, evidence references, confidence, and review issues.
- Digital PDFs are converted to Markdown locally before extraction. A text-density check detects scanned/image-only PDFs and uses the slower xAI image-understanding path only as a fallback.
- Extracted fields include supplier and debtor identities, registration/tax references, invoice and PO numbers, dates, amount/currency, payment terms, bank account, IBAN, SWIFT, description, sector, and line items.
- Added a human review step. Confirming creates the invoice and open marketplace financing demand in one database transaction.
- Extended invoice storage with extraction/payment metadata while keeping legacy seeded invoices compatible.
- Added three synthetic JSON/PDF invoice pairs under `data/synthetic-invoices/` and a reproducible PDF generator.
- Fixed supplier navigation so **My applications** resolves to the working origination page.
- Updated and regenerated the English and Russian user guides.
