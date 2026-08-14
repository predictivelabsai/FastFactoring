# Agent operating model

## Topology

Use one controller, up to twelve read-only country scouts, and shared specialist gates. Parallelism stops before sending.

| Role | May do | Must not do | Output |
|---|---|---|---|
| GTM controller | Approve hypotheses, ICP, sample, priorities and KPIs | Send outreach or waive gates | Experiment card and decision log |
| Country scout | Research market, registries, sectors, associations, language and channel rules | Contact prospects or alter shared state | Country brief with cited primary sources |
| Data steward | Normalize, deduplicate, record provenance, generate cohorts | Invent missing data or scrape contrary to terms | Cohort plus QA report |
| Vertical researcher | Identify pains, events, terminology and personas | Make financing claims | Evidence-backed research hooks |
| Native-copy reviewer | Review meaning, register, idiom and unsubscribe text | Approve legal eligibility | Localized copy QA record |
| Compliance gate | Record entity type, lawful-basis rationale, policy version and exclusions | Give blanket EU approval | Eligible/blocked decision with reason |
| Outreach operator | Run preflight, enforce caps and invoke the single sender | Delegate sending to country agents | Immutable send/event records |
| Inbox triage | Detect replies, bounces and opt-outs; draft a response | Auto-send a substantive reply | Suppression event and human-ready draft |

## Worker packet

Every delegated task states:

1. one objective and one market;
2. allowed data and tools;
3. prohibited actions, especially sending and state mutation;
4. exact output schema and destination;
5. freshness and primary-source requirements;
6. acceptance checks and deadline.

Country output must include `country`, `locale`, `priority_verticals`, `personas`, `data_sources`, `channel_rules`, `approved_claims`, `blocked_claims`, `sample_candidate_companies`, `risks`, `sources`, and `as_of`. Sample companies are company-level research candidates only; scouts do not find personal contacts or create a send cohort.

## Concurrency rule

Country workers never write shared CSV or send state. They return immutable candidate artifacts. The data steward merges by `(country, reg_code)` and canonical domain. One outreach operator owns the global suppression store and send ledger. This avoids duplicate sends and races in the current outbound-master CSV model.

## Review gates

- Research gate: current primary sources and dated evidence.
- Data gate: active entity, registry identity, provenance, source terms, deduplication.
- Legal gate: entity class and country-specific electronic-marketing assessment.
- Copy gate: native review, one CTA, claim boundary, sender identity, opt-out.
- Send gate: verified address, suppression check, local business hours, cap and idempotency.
