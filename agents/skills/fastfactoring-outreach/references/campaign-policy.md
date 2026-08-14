# Campaign policy

**Policy version:** `FF-OUTREACH-2026-08-14-v1`
**Review by:** 14 November 2026, or immediately after a legal, product, funding-partner, sender, or outbound-engine change.

## Required campaign fields

`campaign_id`, `experiment_id`, `country`, `locale`, `motion`, `vertical`, `sender_identity`, `entity_class`, `lawful_basis`, `policy_version`, `reviewers`, `daily_cap`, `send_window`, `retention_until`, `claims_gate`, and `stop_rules`.

## Hard send gates

All must be true:

- recipient is a verified current corporate business address;
- company and contact match the approved cohort and entity class;
- no suppression exists for person, address, domain, or legal entity;
- no terminal reply, bounce, complaint, opt-out, or do-not-contact event exists;
- local legal assessment and native copy review are recorded;
- message identifies the sender and contains a simple opt-out mechanism;
- send is inside recipient-local business hours and below market/day cap;
- idempotency key `campaign_id:person_id:touch` has never succeeded;
- the user explicitly approved live sending.

FastFactoring policy overrides a looser outbound-master default. A user approval cannot override a missing legal, suppression, verification, reviewer, configuration, or transactional-send control.

## UK baseline

Corporate subscribers may be approached under a documented UK B2B assessment, but sole traders and some partnerships require individual-subscriber treatment. UK GDPR still applies when a named business contact is processed. Always identify the sender and provide an opt-out. Re-check current ICO guidance before launch.

## International baseline

There is no blanket “EU B2B email” permission. GDPR/EEA legitimate-interest analysis does not replace national electronic-marketing rules. A country reviewer must document the local rule, entity class, regulator guidance, and opt-out language before a market is enabled.

For Germany and any consent-only route, evidence must record the exact recipient/address, controller and campaign purpose, consent text and scope, collection source, timestamp, policy version, proof artifact, withdrawal status, and verifier. The default cap remains zero without this record.

## Transparency and links

Required privacy information overrides the first-touch preference to omit links. Where counsel approves a layered notice, include a concise identity/purpose/source/rights statement and a direct privacy-notice link. If the approved notice cannot fit the copy constraint, lengthen the message or do not send.

## Working retention defaults

Apply a stricter jurisdiction or counsel decision when required:

- unapproved candidate/contact research: delete or refresh after 90 days;
- rejected enrichment artifacts: delete after 30 days unless needed for suppression or audit;
- campaign event and approval records: retain 24 months, minimized and access-controlled;
- reply content: retain 12 months unless moved to an active CRM opportunity;
- suppression: retain the minimum hashed/identifying value needed to honor the objection while outreach operates; review annually and never re-import around it.

Record the chosen schedule in every campaign. A reviewer must approve exceptions.

## Stop rules

Immediately stop an individual sequence on any reply, hard bounce, opt-out, complaint, or do-not-contact request. Pause the cohort if hard bounces exceed 3%, any spam complaint appears in a small pilot, duplicate sending is detected, or a localized opt-out cannot be recognized reliably.

A sample under 50 approved contacts is a learning pilot, not proof of repeatable conversion. Label targets as hypotheses and report uncertainty rather than declaring a winning market from a small cohort.
