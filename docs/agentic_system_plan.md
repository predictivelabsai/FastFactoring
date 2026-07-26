# Factorio Agentic System Plan

## Current-State Review

Factorio has strong workflow coverage but limited agent depth.

- **Investor:** dashboard, marketplace, auctions, secondary market, portfolio,
  statement/export, auto-invest, triage, and reporting assistant.
- **Admin:** onboarding, invoice processing, risk, scoring/calibration, funding,
  collections, accounting/reconciliation, compliance, integrations, reporting,
  audit, CRM, drive, documents, mail, and a 12-agent fleet.
- **Agent gap:** specialist names currently share only six read tools and four
  write tools. Runs are streamed but not durable, scheduled, resumable, or
  approval-aware. The global kill switch and audit log are useful foundations.

## Product Model

Keep one role-aware **Factorio AI** conversation. Agents should be specialists
behind the chat, not separate chat products. Every response may contain an
explanation, data table, proposed action, downloadable artifact, and guarded
action buttons.

Introduce persistent `agent_runs`, `agent_steps`, `agent_artifacts`,
`agent_approvals`, `agent_schedules`, and `agent_memory` records. Tools must use
typed inputs/outputs, idempotency keys, role scopes, timeouts, and audit events.

### Action Policy

1. **Read/analyse:** run immediately.
2. **Draft/simulate:** run immediately; never send or publish.
3. **Internal reversible change:** show a confirmation card.
4. **Money, credit, external communication, ad spend, publishing:** require
   explicit approval with before/after values.
5. **Irreversible or regulated action:** require named approver and audit reason.

## Investor AI

| Agent | Questions and actions |
|---|---|
| Portfolio Analyst | “What changed this month?”, returns, cash flows, concentration, late invoices, downloadable investor update |
| Opportunity Scout | “Find five B-grade invoices under 60 days”, compare offers, explain debtor and sector risk |
| Allocation Agent | Propose diversified allocations, simulate yield/default cases, draft auto-invest rule changes |
| Risk Monitor | Watch debtor, sector, maturity and arrears thresholds; explain alerts and scenario impact |
| Liquidity Agent | Review secondary listings, propose sales, estimate discount and cash timing |
| Reporting Agent | Statements, realized/unrealized return explanations, exports and scheduled summaries |

Investment, bid, secondary-sale, and auto-invest mutations always require
confirmation. The assistant must show source data and assumptions.

## Admin Operations Agents

Turn each existing pod into real tools:

- **Origination:** KYC checklist, Companies House verification, duplicate checks,
  missing-document requests, facility proposal.
- **Decisioning:** score explanation, policy checks, pricing/advance simulation,
  concentration limits, exception memo.
- **Funding:** pre-disbursement checklist, bank-detail match, approval pack,
  disbursement proposal.
- **Servicing:** payment matching, reconciliation proposal, dunning drafts,
  dispute timeline, write-off recommendation.
- **Oversight:** AML/KYC gaps, policy breaches, audit summaries, portfolio stress
  tests, board/regulatory packs.
- **Service and Sales:** inbox classification, reply drafts, pipeline next-best
  action, forecast and follow-up scheduling.

## Admin Growth & Marketing Suite

Adapt Tendly Marketing’s six groups and 32 tools into Factorio:

- **Marketing Strategy:** product context, positioning, personas, launch,
  pricing, referral and campaign planning.
- **SEO:** technical audit, Search Console insights, keyword/topic clusters,
  programmatic pages, schema markup, competitor pages, AI-search optimisation.
- **Paid Media:** Google, LinkedIn and Meta campaign planning; keyword/audience
  research; creative variants; budget and ROAS simulation; paused campaign
  creation; approval-gated activation and budget changes.
- **Content & Social:** landing copy, editing, case studies, investor/supplier
  newsletters, email sequences, LinkedIn/X posts, editorial calendar.
- **CRO & Experiments:** landing, signup, supplier application and investor
  onboarding audits; hypothesis backlog; A/B design and result interpretation.
- **Marketing Analytics:** GA4/Search Console/ad-platform dashboard, attribution,
  CAC by supplier/investor persona, funnel leakage, natural-language data chat,
  saved reports and anomaly alerts.

Initial Factorio routes: `/app/admin/growth`, `/seo`, `/paid-media`, `/content`,
`/experiments`, and `/marketing-analytics`. External publish/send/spend actions
remain disabled until connectors and approval policies are configured.

## Navigation and Collapse Behaviour

Replace the flat Tools list with persisted, role-scoped groups:

### Investor

- **Overview:** Dashboard, Portfolio, Statement
- **Invest:** Opportunities, Auctions, Secondary, Auto-invest
- **Intelligence:** Risk Monitor, Reports

### Admin

- **Overview:** Console, Global Settings
- **Origination:** Onboarding, Processing, Scoring, Risk, Funding
- **Servicing:** Collections, Accounting, Compliance, Reports
- **Growth & Marketing:** Growth, SEO, Paid Media, Content & Social, CRM, CRO,
  Marketing Analytics
- **Markets:** Opportunities, Auctions, Secondary, Portfolio
- **Workspace:** Drive, Docs, Mail
- **Automation & Governance:** Factorio AI, Agent Fleet, Integrations, Audit

Every nav group and Admin dashboard section becomes an accessible accordion.
Per the requested convention, `>` minimizes and `<` maximizes. Preserve state in
`localStorage` by role; keep the active route’s group open. Add “Collapse all”
and “Expand all”, keyboard controls, `aria-expanded`, and a mobile-safe default.

## Delivery Sequence

1. **Navigation foundation:** grouped accordions, arrows, persisted state, active
   group behaviour, responsive tests.
2. **Agent runtime:** durable runs/steps/artifacts, typed tool registry, approval
   cards, retries, cancellation, audit and kill switch.
3. **Investor agents:** read-only analysis first, then confirmed allocation,
   bidding, secondary and auto-invest actions.
4. **Admin operations:** implement tools pod by pod, beginning with origination,
   decisioning and collections.
5. **Marketing cockpit:** synthetic dashboards plus SEO/content/CRO tools;
   connect GA4 and Search Console before ad platforms.
6. **Paid media:** read-only reporting, draft campaigns, paused creation, then
   approval-gated activation/spend.
7. **Autonomy:** schedules, alerts and bounded policies only after replay tests,
   evaluation datasets and action-level rollback are in place.

## Definition of Done

- Every agent answer identifies data sources, assumptions, tools used, and
  proposed/completed actions.
- All external or financial actions have explicit approvals and idempotency.
- Runs survive refreshes and can be inspected, cancelled, retried, and shared.
- Role/data isolation, prompt-injection tests, tool authorization, audit
  completeness, and failure recovery are covered by automated tests.
- Marketing dashboards distinguish synthetic, draft, connected, paused, and live
  states; no demo screen implies real spend or publishing.
