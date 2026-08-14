---
name: fastfactoring-outreach
description: Prepare, review, and operate controlled FastFactoring B2B outreach in supported locales. Use for campaign briefs, localized cold-email sequences, compliance and claim gates, send preflight, suppression handling, or reply triage. This skill defaults to dry-run and draft-only; live sending requires explicit user approval and a single central sender.
---

# FastFactoring Outreach

## Safety Boundary

Read [campaign-policy.md](references/campaign-policy.md), [approval-schema.md](references/approval-schema.md), and [localization-and-replies.md](references/localization-and-replies.md). If an `outbound-master` capability is available in the active agent framework, reuse only its checkpoint model and guarded one-message sender; do not assume it is concurrency-safe or internationally complete.

Only one central outreach operator may write suppression or send state. Country agents may research, select hooks, and draft copy. Default every run to `DRY_RUN=1`. Never use personal credentials in a campaign artifact. FastFactoring's stricter gates override outbound-master: never invoke `send_one.py` without a valid approval artifact, never send to an MX-only/catch-all/guessed address, and never omit legally required first-contact transparency merely to avoid a link.

The current outbound-master implementation lacks transactional suppression/idempotency, localized terminal-event handling, and a configured FastFactoring sender. Treat live sending as technically blocked until those controls are implemented and tested; user approval alone does not clear a missing technical gate.

## Workflow

1. Require an approved GTM experiment and immutable, sourced cohort produced with the repository-local `fastfactoring-sme-prospecting` skill.
2. Confirm market locale, corporate entity class, approved channel, lawful-basis record, policy version, retention date, and country reviewer.
3. Minimize contacts. Verify each current corporate address immediately before approval; MX-only or guessed addresses are not sendable.
4. Check global person, address, domain, and legal-entity suppressions. Block any prior reply, bounce, opt-out, complaint, or do-not-contact state unless an explicit policy permits a transactional response.
5. Draft a five-touch sequence using the outbound-master cadence. Keep first-touch email under 80 words, use one CTA, omit links on touch one, and cite a recent sourced hook internally.
6. Have a native reviewer check meaning, tone, register, claims, and local opt-out wording. Translation alone is insufficient.
7. Run preflight and generate a review bundle. A future live send needs explicit user approval, a low country/day cap, local business hours, and a transactional idempotency key based on campaign, person, and touch. Until the runtime controls above exist, stop at the bundle.
8. On any reply, bounce, complaint, or opt-out, stop the sequence and update suppression before any further send. Draft substantive replies for human review.

## Claim Rules

- Say FastFactoring is open-source invoice-finance software and Factorio is its standalone reference implementation.
- Do not say FastFactoring provides funding, guarantees approval, reduces a specific cost, or advances a stated percentage.
- Until an approved funding partner exists for a territory, SME outreach must seek interviews, design partners, or waitlist interest—not finance applications.
- Do not process patient information, invoice contents, bank data, or other sensitive data during prospecting.

## Launch Limits

Start with one UK experiment at no more than 20 new contacts per business day. Baltic pilots default to no more than five per country per business day. Any higher cap requires evidence from deliverability, response, and complaint metrics plus explicit approval.

## Required Output

Return the campaign brief, localized drafts plus back-translation, citations for personalization hooks, eligibility and copy-review records, preflight result, exact proposed send count/time, and stop rules. If approval is absent, stop at a reviewable dry-run bundle.
