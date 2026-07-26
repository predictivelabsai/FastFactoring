# Factorio AI Platform Demo — User Guide

**Generated 2026-07-26 · Live demo: https://factorio.co.uk**

> Demo notice: every company, invoice, offer, integration, investment, and AI response shown here is synthetic or illustrative. The platform does not guarantee funding, payment timing, or investment returns.

This guide is a browser-driven tour of the Factorio AI Platform demo. It follows the three primary roles and uses reviewed evaluation questions to demonstrate AI behavior.

![Factorio AI Platform demo](img/platform-demo/00-platform-demo.png)

---

# 1. Borrower / Supplier

## Start in Factorio AI

![Start in Factorio AI](img/platform-demo/01-supplier-ai-upload.png)

- The Supplier demo opens in one AI workspace—there is no marketplace or triage queue.
- Select the paperclip and upload a digital PDF, image, JSON, or text invoice.
- The demo uses synthetic invoices; digital PDFs are converted to Markdown before xAI extraction.

## Upload an invoice and receive an offer

![Upload an invoice and receive an offer](img/platform-demo/02-supplier-ai-offer.png)

- Factorio AI extracts supplier, debtor, invoice number, amount, dates, bank details, and payment terms.
- The response clearly says “You’re pre-approved!” and presents an indicative offer table.
- Download PDF, Accept, and Change remain visible; final terms are subject to verification.

## Change the amount or financing period

![Change the amount or financing period](img/platform-demo/03-supplier-change-terms.png)

- Open Change to request a lower amount paid today or a different period.
- The indicative fee updates from the requested amount and days.
- Add contact details and confirm registry information before acceptance.

## Profile, banking, and accounting connections

![Profile, banking, and accounting connections](img/platform-demo/04-supplier-profile-integrations.png)

- My Profile contains a hypothetical company identity and masked settlement bank information.
- Lloyds Bank is labelled as a planned Open Banking connection.
- QuickBooks, Xero, and Sage are clearly labelled hypothetical demo integrations.

## Track applications and contracts

![Track applications and contracts](img/platform-demo/05-supplier-applications.png)

- My Applications shows synthetic financing requests created from accepted invoices.
- Each accepted request can expose a one-page financing contract between Factorio Ltd and the extracted supplier.
- Downloaded PDFs use supplier, Factorio reference, date, and document-type slugs.

---

# 2. Investor

## Ask Investor AI about performance

![Ask Investor AI about performance](img/platform-demo/06-investor-ai-performance.png)

- Investor AI is grounded only in the selected demo investor’s positions and computed metrics.
- Eval question shown: “How are my investments performing?”
- Expected and realised returns are distinguished; the assistant does not guarantee outcomes.

## Ask about concentration and risk

![Ask about concentration and risk](img/platform-demo/07-investor-ai-concentration.png)

- Eval question shown: “Where is my portfolio most concentrated?”
- Debtor and sector exposure percentages are calculated deterministically before reaching the model.
- Copy and Share create portable session transcripts; shared links are read-only snapshots.

## Review the portfolio cockpit

![Review the portfolio cockpit](img/platform-demo/08-investor-portfolio.png)

- See account value, net annual return, active invested, expected outstanding, and realised results.
- Aging, payment habits, grades, due dates, and position status support deeper AI questions.
- Use the demo investor selector to compare isolated synthetic portfolios.

## Inspect available invoices

![Inspect available invoices](img/platform-demo/09-investor-marketplace.png)

- Browse synthetic open invoices by debtor, sector, risk grade, term, and estimated return.
- Funding progress and invoice economics support manual selection.
- Returns are estimates and invoice financing retains credit, fraud, dilution, concentration, and liquidity risk.

## Configure risk-aware Auto-invest

![Configure risk-aware Auto-invest](img/platform-demo/10-investor-autoinvest.png)

- Choose conservative, balanced, or growth preferences plus grade, term, return, sector, debtor-concentration, and per-invoice limits.
- Investor AI ranks only eligible invoices and explains each proposed allocation.
- The preview does not place money; review or change preferences before execution.

## Reconcile investment activity

![Reconcile investment activity](img/platform-demo/11-investor-statement.png)

- The statement records investments and settlements with invoice and counterparty references.
- Filter by date, type, counterparty, invoice, and amount.
- Export CSV for external analysis or reconciliation.

---

# 3. Admin

## Operate the back office

![Operate the back office](img/platform-demo/12-admin-console.png)

- Admin sees platform KPIs, queues, exceptions, and operational navigation in one workspace.
- Navigation groups are collapsible and can be minimized to keep a complex toolset manageable.
- Global settings include the USD, GBP, EUR, or UZS display-currency override.

## Coordinate the Agent Fleet

![Coordinate the Agent Fleet](img/platform-demo/13-admin-agent-fleet.png)

- Fourteen specialists span orchestration, origination, decisioning, servicing, oversight, and growth.
- Agents use grounded tools and preserve approval gates for credit, communication, publishing, spend, and money movement.
- The activity feed makes agent operations auditable.

## Run marketing and SEO agents

![Run marketing and SEO agents](img/platform-demo/14-admin-seo-agent.png)

- Browser-driven eval question shown: “Build a supplier invoice-finance keyword cluster.”
- SEO & AI Search and Paid Marketing agents create research and drafts without silently publishing or activating spend.
- Campaign work should include audience, intent, evidence, measurement, guardrails, and explicit approval.

## Inspect and edit agent skills

![Inspect and edit agent skills](img/platform-demo/15-admin-skills-editor.png)

- Open Agent Skills to view each specialist’s current Markdown instructions.
- Admin can save a database-backed prompt version and review change history.
- Revert restores a selected earlier version while preserving an audit trail.

## Process and approve invoices

![Process and approve invoices](img/platform-demo/16-admin-processing.png)

- The processing queue supports verification, exceptions, risk review, and funding readiness.
- AI may recommend or draft; final financial and credit actions remain approval-gated.
- Synthetic data makes the workflow safe to explore in the platform demo.

## Reconcile accounting activity

![Reconcile accounting activity](img/platform-demo/17-admin-accounting.png)

- Accounting tools cover journal review, reconciliation, receivables, fees, reserves, and settlement evidence.
- Agents must not create balancing plugs or invent transactions.
- Use source records and approval history to resolve differences.

## Manage platform integrations

![Manage platform integrations](img/platform-demo/18-admin-integrations.png)

- Integration cards show demo connectivity for accounting, banking, communications, and document services.
- Connection status is demonstrative and must not be treated as a live third-party authorization.
- The invoice ingestion endpoint supports structured external demo data.

## Review the audit trail

![Review the audit trail](img/platform-demo/19-admin-audit.png)

- Audit records identify actor, action, entity, detail, and time.
- Use the log to inspect human and agent activity, approvals, and configuration changes.
- Prompt-version history and action logs support governance of the agentic platform.

## Prepare borrower transactional emails

![Prepare borrower transactional emails](img/platform-demo/20-admin-email-templates.png)

- Customer Service can render Factorio-branded bank-connection and accounting-connection reminders from checked-in Markdown templates.
- Each draft uses a personalized HTTPS resume link, support contact, and application-specific wording without sensitive bank or accounting credentials.
- Delivery is disabled in this demo until Postmark, a verified sender, approval/lifecycle triggers, audit records, and delivery webhooks are configured.

---

# Suggested demo script

1. Sign in as **Supplier**, upload a sample invoice, inspect the offer, and open My Profile.
2. Switch to **Investor**, ask the two evaluation questions shown above, then compare Portfolio and Auto-invest.
3. Switch to **Admin**, open Agent Fleet, run a specialist prompt, inspect Agent Skills, then review Processing, Accounting, Integrations, and Audit.

The demo credentials and one-click roles are available from the Sign in page. Use only synthetic information.