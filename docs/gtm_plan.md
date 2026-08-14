# FastFactoring Go-to-Market Plan

**Version:** 1.0
**As of:** 14 August 2026
**Scope:** the 12 enabled product languages: English/UK, Estonian, German, French, Swedish, Latvian, Norwegian, Danish, Polish, Dutch, Finnish, and Lithuanian. Russian and Uzbek remain in the codebase but are disabled and excluded from GTM.

## Executive decision

Run two connected but distinct motions:

1. **FastFactoring** is the open-source invoice-finance infrastructure offer for factors, banks, private-credit funders, payer/anchor programmes, ERP and e-invoicing platforms, and self-hosting operators. Lead with auditability, local deployment, configurable workflows, transparent data models, and integration freedom.
2. **Factorio** remains the standalone reference product and live demo at [factorio.co.uk](https://factorio.co.uk). It demonstrates the supplier, payer, investor and administrator journeys and converts qualified interest into a product conversation.

FastFactoring must not be presented as a lender. Until a territory has an approved funding partner and regulatory model, SME outreach asks for discovery interviews, design-partner participation, or waitlist interest—not a finance application or promised funding.

The first 90 days should pair a **UK beachhead** with small **EE/LV/LT data-advantage pilots**. France, Poland, Germany, the Netherlands and Denmark follow through partner-led or consent-led routes. Sweden, Finland and Norway enter after a repeatable motion or a qualified local partner exists.

## Market opportunity and sequencing

The enabled-language markets represented approximately **€1.626tn of 2025 factoring turnover**, about 63.6% of Europe’s €2.558tn total. France (€439.4bn), Germany (€423.5bn), the UK (€364.4bn), the Netherlands (€165.4bn), and Poland (€123.0bn) are the largest. Denmark (+22.3%) and Latvia (+28.3%) showed strong year-on-year growth, although from smaller bases. Some Nordic figures are carried-forward estimates; re-check before external use. [EU Federation 2025 data](https://www.euf.eu.com/data-statistics/annual-factoring-data.html)

The UK is the best learning market, not merely the third-largest market. Government research reports almost £11bn in annual economic cost from late payments, £26bn outstanding at any time, and 1.5m affected firms. [Small Business Commissioner research](https://www.smallbusinesscommissioner.gov.uk/late-payments-research-2/) The British Business Bank reports roughly £22bn advanced through invoice finance and asset-based lending in 2025 while clearing-bank client counts continued to fall, strengthening the non-bank and software-enablement thesis. [Small Business Finance Markets 2026](https://www.british-business-bank.co.uk/sites/g/files/sovrnj166/files/2026-03/report-small-business-finance-markets-2026.pdf)

| Wave | Markets | Why now | Acquisition route |
|---|---|---|---|
| 1, days 0–90 | UK | Large, English-speaking market; measurable late-payment pain; Factorio domain | Carefully controlled corporate ABM, founder outreach, brokers, accountants, vertical bodies |
| 1B, days 0–90 | EE, LV, LT | Local-language product plus reusable company data | Research calls, warm introductions, associations, small corporate-email pilots where approved |
| 2, days 90–180 | FR | Largest factoring market; role-relevant professional B2B route | ASF, accountants, ERP partners, limited approved professional outreach |
| 2, days 90–180 | PL, DE, NL, DK | Large or fast-growing markets, but stricter electronic marketing | Partner, webinar, content, referral and explicit-consent capture |
| 3, days 181–365 | SE, FI, NO | Lower penetration may offer whitespace; flat/negative reported growth in parts | Factor, anchor, accountancy and trade-association partners |

## Ideal customer profiles

### 1. SME supplier / design partner

Mandatory company filters:

- active incorporated entity, trading for more than 18 months;
- normally €0.5m–€50m annual revenue, with €1m–€10m as the initial A band;
- 5–249 employees where known; unknown employee count lowers confidence but does not automatically exclude;
- more than 50% B2B or institutional revenue, recurring accepted invoices, and typical 30–120 day terms;
- evidence of at least five invoices per month and a growth, payroll, stock, contract or seasonality need;
- no insolvency, sanctions, shell/dormant status, consumer-credit use case, or disputed/contingent receivables.

Do not infer invoice suitability or debtor quality from sector alone. Confirm these during enrichment and discovery.

### 2. Payer / anchor programme

Target larger hotel, care, retail, healthcare, manufacturing, construction and food-service groups with fragmented SME supplier bases. Personas are CFO, treasury, procurement, accounts payable, supplier resilience and supplier-diversity leaders. The offer is an auditable early-payment workflow, not a promise to fund suppliers.

### 3. Infrastructure buyer and referrer

Target heads of factoring/product, credit and risk at banks, non-bank factors and private-credit funds; product/integration leaders at ERP, accounting, e-invoicing and vertical SaaS vendors; and commercial-finance brokers, accountants and trade bodies. Offer the open-source platform, Factorio reference flow, implementation, hosting, support and integrations.

## Vertical focus

| Priority | Vertical | Qualifying evidence | Avoid |
|---|---|---|---|
| A | Manufacturing, wholesale/distribution, transport/logistics, construction subcontractors | B2B trade credit, accepted invoices, repeat corporate debtors, stock/payroll cycle | Consumer retail or speculative/project-contingent claims |
| A | Staffing, facilities, IT and professional services | Monthly approved timesheets or recurring B2B invoices | Consumer consultancy or milestone disputes |
| B | Medical and healthcare | Devices, diagnostics, pharma distribution, care/staffing suppliers, clinics invoicing insurers, NHS/public bodies or groups | Patient data, consumer self-pay, disputed reimbursement claims |
| B | Hospitality | Hotel groups invoicing tour operators/corporates; events, catering, food-service and hospitality suppliers | Predominantly card/cash accommodation or restaurants |
| B | Food/agriculture and energy | Co-ops, processors, equipment, installers, O&M suppliers with large buyers | Commodity speculation or consumer energy debt |

UK survey data supports this selectivity: trade credit is reported by 77% of manufacturing, 76% of transport/storage and 57% of construction SMEs, versus 23% of health and 10% of accommodation/food businesses. Medical and hospitality campaigns must therefore use institutional/B2B subsegments rather than broad sector lists. [UK Small Business Survey 2024](https://www.gov.uk/government/statistics/small-business-survey-2024-businesses-with-employees/longitudinal-small-business-survey-2024-sme-employers-businesses-with-1-to-249-employees)

## Baltic company-data plan

The user’s Pehero repository is [FastPE](/home/julian/dev/fastco/FastPE), not `/home/julian/dev/plai/pehero`. Its canonical raw snapshots are byte-identical to LiquidRound’s copies:

| Country | Raw companies | Relevant data quality |
|---|---:|---|
| Estonia | 2,059 | 1,916 with financial history; strong phone/website coverage; EMTAK present |
| Lithuania | 2,325 | 2,303 with financial history; 2,176 websites; manager field is personal data and must not enter initial exports |
| Latvia | 38,694 | 38,112 employee values; no websites/phones; 36,377 `General` sub-sectors need activity-text reclassification |
| **Total** | **43,078** | Source universe, not an outreach list |

The live `pehero` database contains 25,831 partially loaded companies and 2.78m expanded monthly financial rows. About 2,392 records pass an initial €250k–€50m revenue, sector and non-`General` filter. The materialized database omits registry codes and raw provenance and contains modeled EBITDA; do not use modeled EBITDA as fact. Never run the existing destructive loaders for GTM extraction.

Designate FastPE’s raw JSON as the checksum-pinned source snapshot and stop maintaining two independent copies. Use `(country, reg_code)` as the legal-entity key. Preserve raw industry code/text, latest annual period, source URL/licence/retrieval date, active status and record hash. LiquidRound’s current buyer matcher selects `financials[0]` and uses substring matching; the GTM adapter instead selects the newest year and an explicit taxonomy.

Observed raw-data starting cohorts after recent-year and revenue filtering include 165 Estonian, 1,443 Lithuanian, and roughly 1,936 Latvian companies before active-status, invoice-fit, contact and legal checks. These are research cohorts only. Refresh Lithuania’s hospitality source before interpreting its current zero-result segment, and confirm EE/LT source terms before commercial reuse. The FastPE Latvian scraper claims the data.gov.lv data is CC0; verify that against the dataset metadata before commercial reuse.

Manual classification review is required across all three countries. Validation found examples where a company name/business appeared inconsistent with its source sector label; the exporter therefore marks every classification `source_label_unverified` and every row `research_only`. Neither the source sector nor a name-based guess is sufficient for campaign eligibility.

The validated adapter run with FY 2023+, €1m–€50m revenue and a 249-employee ceiling selected **1,733 research candidates**: EE 287, LT 596 and LV 850. It classified 591 logistics, 319 medical/healthcare, 263 manufacturing, 268 hospitality, 146 construction and 146 wholesale candidates. Of these, 755 have conflicting source classifications, 1,155 lack a usable organization domain and 295 lack employee counts; all still require classification, registry-active-status, invoice-fit, supplier/payer-role, contact and legal review. The saved QA report records exact filters, input/output/review hashes, deterministic duplicate handling, exclusions, shared domains and provenance limitations.

## Scoring and cohort acceptance

Score companies independently of contact reachability:

- invoice and debtor-fit evidence: 30;
- vertical role fit: 20;
- revenue/employee scale: 20;
- timing signal such as contract win, hiring, expansion, tender or seasonal stock: 15;
- active status, financial recency and provenance: 15.

Cap the score at 50 when an entire category is unknown. Every approved company row needs country, registry code, legal name, active status, original and normalized sector, latest annual revenue/year/currency, organization website where available, source metadata, fit reasons and exclusions checked. Named contacts live separately with source, role, verification date, lawful-basis decision and suppression state.

## Country outreach agents

Create twelve persistent **country scout/reviewer configurations**, one for each enabled locale. They research and draft but never send. A central data steward merges cohorts, a compliance gate decides eligibility, and one central outreach operator alone owns the suppression store and send ledger.

| Agent | First verticals | Permitted starting motion |
|---|---|---|
| UK / `en-GB` | Manufacturing, logistics, construction, wholesale, staffing; institutional medical second | Corporate ABM to Ltd/LLP/public bodies after PECR/UK GDPR gate; exclude sole traders and relevant partnerships |
| Estonia / `et` | Medical, industrial/logistics, hospitality | Legal-entity pilot after §103¹ review; generic/role contacts preferred |
| Latvia / `lv` | Logistics, manufacturing, construction, hospitality, medical | Research and partner first; generic legal mailbox only after local review |
| Lithuania / `lt` | Industrial/logistics, medical, B2B services; refresh hospitality | Legal-person pilot with clear opt-out after current §81 review |
| France / `fr` | Manufacturing, transport, construction, professional/medical suppliers | Role-relevant professional B2B after CNIL review; partner-supported |
| Germany / `de` | Manufacturing, logistics, wholesale; infrastructure buyers | No cold email; factor/integrator partnerships, events and consent capture |
| Poland / `pl` | Manufacturing, logistics, wholesale, construction | No cold email; partner, association, webinar and consent-led |
| Netherlands / `nl` | Trade/logistics, staffing, agriculture, infrastructure buyers | Consent/existing-customer channels; ERP/accountant partnerships |
| Denmark / `da` | Logistics, manufacturing, food, hospitality suppliers | Consent and partner-led only |
| Sweden / `sv` | Manufacturing, transport, B2B services | Partner-led; legal-person route only after current review and native opt-out QA |
| Finland / `fi` | Manufacturing, forestry/food, logistics, services | Legal-person route only after current Finlex review; partner first |
| Norway / `no` | Maritime/logistics, energy services, seafood, B2B services | Partner/inbound; named employee email normally consent-led |

Every agent packet must state one objective, permitted tools/data, prohibited actions, output schema, primary-source freshness, and acceptance tests. Its output is an immutable country brief or candidate artifact. No country agent writes a shared CSV, contacts a prospect, or approves itself.

## Outreach governance

The existing `outbound-master` offers useful dry-run, checkpoint, exclusion and one-message controls, but it is not ready for autonomous multi-country sending. Opt-out and out-of-office detection are English-only; terminal events do not hard-block every send path; idempotency is only per run/row; and shared CSV state is unsafe for concurrent writers.

Before live use:

1. centralize suppression by person, address, domain and legal entity;
2. hard-block prior reply, bounce, complaint, opt-out and do-not-contact events;
3. use an idempotency key of `campaign_id:person_id:touch`;
4. record legal entity class, lawful basis, policy version, source and retention date;
5. require current address verification, local business-hour scheduling and country caps;
6. localize reply/opt-out detection and obtain native copy review;
7. disable tracking pixels by default and draft substantive replies for human approval.

For the UK, ICO guidance distinguishes corporate subscribers from sole traders and some partnerships, while UK GDPR still applies to named work contacts. Sender identity and a valid opt-out are required. [ICO B2B marketing guidance](https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/business-to-business-marketing/) Across the EEA, legitimate interest can support direct marketing only after a balancing assessment and does not override national electronic-marketing law; objections to direct marketing are absolute. [GDPR Article 21](https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng/) Public registry data is not blanket outreach permission, and source/privacy information must be provided by first contact. [ICO lead-generation guidance](https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/direct-marketing-guidance/collect-information-and-generate-leads/)

Country scouts must re-check regulator guidance before every launch. Germany, Denmark, the Netherlands, Norway and Poland remain send-disabled by default. This is an operating policy, not legal advice; obtain local counsel before scaling any market.

Primary legal-source starting points are the [ICO’s UK B2B guidance](https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/business-to-business-marketing/), [CNIL’s French electronic prospecting guidance](https://cnil.fr/fr/la-prospection-commerciale-par-courrier-electronique-sms-mms-et-automate-dappel), Estonia’s [Electronic Communications Act §103¹](https://www.riigiteataja.ee/en/eli/516032022002/consolide), Finland’s [Information Society Code §§200–203](https://finlex.fi/en/legislation/translations/2014/eng/917), Sweden’s [Marketing Act §§19–20](https://www.riksdagen.se/sv/dokument-och-lagar/dokument/svensk-forfattningssamling/marknadsforingslag-2008486_sfs-2008-486/), Lithuania’s [Law on Electronic Communications §81](https://e-seimas.lrs.lt/rs/actualedition/TAIS.232036/yKSdaMhNHE/), Latvia’s [Information Society Services Law §9](https://likumi.lv/ta/en/id/96619-law-on-information-society-services), Germany’s [UWG §7](https://www.gesetze-im-internet.de/englisch_uwg/englisch_uwg.html), Denmark’s [Consumer Ombudsman guidance](https://www.forbrugerombudsmanden.dk/media/46522/2016-guidance-unsolicited-communications-with-specific-customers.pdf), the Netherlands’ [ACM spam guidance](https://www.acm.nl/nl/verkoop-aan-consumenten/reclame-en-verleiden/spam-voorkomen-uw-reclame), Norway’s [Datatilsynet newsletter guidance](https://www.datatilsynet.no/personvern-pa-ulike-omrader/kundehandtering-handel-og-medlemskap/nyhetsbrev-epostlister-og-sms/), and Poland’s [Electronic Communications Law Article 398](https://eli.gov.pl/api/acts/DU/2024/1221/text.html#Art.398). These links are research inputs, not pre-approval to send.

## Message and channel strategy

### SME discovery message

Use one observed business signal and one hypothesis: “You appear to invoice [institutional buyer type] on terms; we are building an open, auditable workflow around accepted invoices and would value 20 minutes on how you handle the gap today.” Link to Factorio only after interest or from a campaign landing page; never imply approval or quote an advance rate.

### Infrastructure message

Lead with open-source deployment, auditability, local hosting, configurable RBAC/languages/currencies and integration. Show Factorio as the production-shaped reference implementation. Monetization is hosted Factorio, implementation, integrations, support and managed operations—not closed-source lock-in.

### Partner channels

- UK: accountants/bookkeepers, commercial-finance brokers, Xero/QuickBooks/ERP ecosystems, UK Finance/IFABL, FSB, Make UK, Logistics UK, Build UK, UKHospitality and institutional medical supplier networks.
- Europe: EUF/FCI members and national factoring associations; Enterprise Europe Network local advisors; European Digital Innovation Hubs for open-source pilots and financing advice. [EUF members](https://www.euf.eu.com/) [Enterprise Europe Network](https://een.ec.europa.eu/about-enterprise-europe-network) [European Digital Innovation Hubs](https://digital-strategy.ec.europa.eu/en/policies/edihs)
- Product-led: publish an installable repository, synthetic demo data, security/architecture documentation, lender/integrator APIs, deployment guide, late-payment benchmark and vertical implementation guides.

## 12-month execution plan

### Days 0–30: evidence and controls

- Publish the company schema, sector taxonomy, provenance policy and global suppression model.
- Produce a 500-account UK validation set and 150-account Baltic validation set; these are research samples, not send queues.
- Complete 20 problem interviews across SMEs, factors/funders, payer programmes and referrers.
- Commission the 12-country channel/legal matrix and native terminology review.
- Create three UK landing variants: manufacturing/logistics, construction/services, and institutional medical suppliers.
- Instrument source → demo → interview/application → qualified opportunity → deployment/funding-partner handoff.

### Days 31–90: controlled UK and Baltic pilots

- Run founder-led UK pilots at no more than 20 new verified corporate contacts per business day.
- Limit approved Baltic email pilots to five new contacts per country/day; prefer warm partner introductions and calls.
- Conduct five partner conversations per week and secure three written pilot/referral commitments.
- Test one variable at a time: vertical, hook, persona, CTA or channel. Do not test legal compliance or claims.
- Stop immediately on a complaint, duplicate send, suppression failure or unverifiable localized opt-out.

### Days 91–180: prove repeatability

- Scale only the UK vertical that meets meeting and qualification thresholds.
- Launch France after native/legal approval; use partner-led campaigns for Poland, Germany, the Netherlands and Denmark.
- Start one payer/anchor supplier-resilience pilot.
- Publish two evidence-based case studies and an open-source deployment/integration guide.

### Days 181–365: partner-led expansion

- Enter Sweden, Finland and Norway only with a qualified local partner or repeatable inbound demand.
- Build a cross-border debtor/funder proposition through FCI/EUF networks.
- Convert repeated implementation work into documented modules and managed Factorio packages.

## Experiment portfolio and targets

| Experiment | Sample | 90-day success threshold | Stop rule |
|---|---:|---|---|
| UK manufacturing/logistics SME discovery | 150 | ≥10% positive reply; ≥8 qualified interviews; ≥2 design partners | Hard bounce >3%, any complaint, or no positive reply after 50 approved contacts |
| UK institutional medical suppliers | 75 | ≥6 interviews; validated invoice/debtor workflow | Any patient-data handling or predominantly consumer receivables |
| Baltic local-language discovery | 50/country | ≥5 interviews total and one partner/pilot lead per country | Translation/compliance gate failure or weak invoice evidence |
| UK factor/broker/accountant partners | 40 organizations | 15 meetings and three written referral/pilot commitments | No qualified interest after 20 researched organizations |
| Open-source integrator motion | 30 organizations | Five technical evaluations and two deployment proofs | Requests are only for licensed funding, not infrastructure |

Use thresholds as hypotheses, not forecasts. Re-baseline after the first 50 eligible contacts or 20 partner conversations.

## Measurement

North-star outcomes are **qualified deployed invoice volume**, **repeat supplier usage**, and **production deployments/partners**. GitHub stars and email volume are diagnostic, not commercial outcomes.

Weekly funnel: sourced → active/eligible → enriched → verified → approved → contacted → positive reply → meeting → qualified opportunity → design partner → deployment. Segment every rate by country, vertical, source, persona and experiment.

Guardrails:

- 100% registry/provenance coverage and lawful-basis decision before sending;
- 100% suppression checks and zero duplicate sends;
- complaint rate below 0.1%, hard bounce below 3%, opt-outs reviewed weekly;
- positive reply and qualified-meeting rates by cohort;
- application completion, approval/funder-handoff, time-to-cash and repeat usage where a licensed partner exists;
- partner-sourced pipeline, CAC payback, gross margin, concentration and loss/dilution only where FastFactoring has the relevant operational data and mandate.

## Reusable operating assets

Three framework-agnostic skills in `agents/skills/` implement the plan:

- `fastfactoring-gtm-orchestrator`: market selection, experiments, agent packets, approvals and KPIs;
- `fastfactoring-sme-prospecting`: safe Baltic import, registry identity, vertical filtering, scoring and provenance;
- `fastfactoring-outreach`: localized copy, claims, legal/send gates, suppression and human-approved operations.

No live outreach should begin until the outbound engine’s international reply detection, terminal-event blocks, central idempotency and suppression controls are implemented and tested.
