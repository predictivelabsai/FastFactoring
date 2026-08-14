# FastFactoring market playbook

## Baseline market sequence

| Wave | Markets | Rationale | Default motion |
|---|---|---|---|
| 1 | UK | English operation, mature invoice-finance market, visible late-payment pain | SME discovery plus infrastructure partners |
| 1B | Estonia, Latvia, Lithuania | Local language support and reusable registry datasets | Narrow SME design-partner pilots |
| 2 | Germany, France, Netherlands, Poland | Large factoring markets; greater localization and legal-review load | Partner and platform first |
| 3 | Finland, Sweden, Norway, Denmark | Cohesive Nordic cluster but smaller volumes | Associations, accountants, ERP and factor partnerships |

Re-score quarterly. Country scouts must update time-sensitive evidence rather than treating this baseline as permanent.

## ICPs

### SME supplier

- Registered B2B company, normally 10–249 employees and €1m–€50m revenue.
- Repeat invoices to creditworthy business or public-sector debtors.
- Payment terms normally 30–120 days and a working-capital need tied to growth, contracts, stock, payroll, or seasonality.
- Finance director, owner-manager, controller, or accounts-receivable lead is identifiable.

Prioritize medical and healthcare suppliers, hospitality suppliers and multi-site operators, manufacturing, wholesale, construction, logistics, business services, food, agriculture, and energy. Exclude consumer-only businesses, inactive or insolvent entities, disputed receivables, sanctioned entities, and personal medical data.

### Payer-led programme

Target hotel, care, retail, healthcare, manufacturing, food-service, and construction groups with many SME suppliers. Personas are CFO, treasury, procurement, and supplier-finance leadership.

### Infrastructure buyer

Target factors, banks, invoice-finance brokers, ERP/accounting platforms, embedded-finance providers, vertical SaaS vendors, and public development institutions. Lead with open source, auditability, self-hosting, configurable workflows, and Factorio as the reference implementation.

## Positioning boundaries

FastFactoring is software. Factorio demonstrates a product flow. Until an approved finance provider and territory policy exist, use “explore,” “prototype,” “design partner,” or “deploy the platform”—not “get funded,” “guaranteed approval,” or numeric financing promises.

## Experiment card

```yaml
id: UK-MED-001
hypothesis: UK medical distributors with long NHS or group-buyer terms will discuss an invoice-finance workflow.
motion: sme_design_partner
market: UK
locale: en-GB
icp: 10-249 employees; B2B; active company; repeat invoices
offer: 20-minute cash-flow workflow interview and Factorio demo
channel: corporate email
sample: 50
success: 5 positive replies and 3 interviews
stop: hard_bounce_gt_3pct_or_complaint_gt_0
claims_gate: discovery_only
owner: central_gtm_controller
```

## Funnel vocabulary

Use one definition in every country: sourced → eligible → enriched → verified → approved → contacted → positive reply → meeting → qualified opportunity → design partner → deployment. Report both counts and conversion rates, segmented by country, vertical, source, persona, and experiment.
