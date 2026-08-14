---
name: fastfactoring-gtm-orchestrator
description: Plan, prioritize, and govern FastFactoring go-to-market programmes across supported language markets. Use when choosing countries or verticals, defining ICPs and campaign experiments, assigning country research agents, setting funnel KPIs, or deciding whether a market is ready for prospecting or outreach. Do not use this skill to send messages or promise financing.
---

# FastFactoring GTM Orchestrator

## Purpose

Turn a market-growth request into an evidence-backed, measurable rollout. Keep the two offers distinct:

- **FastFactoring** is open-source invoice-finance infrastructure for factors, banks, platforms, and self-hosting operators.
- **Factorio** is the standalone reference product and live demo. Treat demo data and financing outcomes as illustrative unless an approved funding partner says otherwise.

Read [market-playbook.md](references/market-playbook.md) before prioritizing markets. Read [agent-operating-model.md](references/agent-operating-model.md) before delegating work and [country-agents.md](references/country-agents.md) when one or more country scouts are required.

## Workflow

1. Confirm the objective, buyer motion, markets, timeframe, and whether the task is research, pipeline creation, or an approved campaign.
2. Inventory enabled product locales. Exclude disabled locales even when translations remain in code. As of the baseline plan, RU and UZ are disabled.
3. Select one motion per experiment:
   - infrastructure buyer: factor, bank, broker, ERP/accounting platform, vertical SaaS;
   - SME design partner: supplier with recurring B2B invoices and 30–120 day terms;
   - payer-led programme: larger buyer with a fragmented supplier base.
4. Create an experiment card with hypothesis, ICP, market, offer, channel, owner, sample, success metric, stop rule, and claim/legal gate.
5. Assign read-only country scouts using the packet in [agent-operating-model.md](references/agent-operating-model.md). Scouts may research and draft; they may not send or mutate shared suppression state.
6. Use the repository-local `fastfactoring-sme-prospecting` skill to build a provenance-preserving cohort.
7. Require approval of market, entity eligibility, copy, and claims before handing the cohort to the repository-local `fastfactoring-outreach` skill.
8. Review weekly by stage: sourced, eligible, verified, contacted, positive reply, meeting, qualified opportunity, design partner, deployment.

## Decision Rules

- Start with the UK for market learning, then run low-volume Baltic pilots where first-party datasets provide an execution advantage.
- Do not rank markets by factoring turnover alone. Weight language readiness, lawful channel access, data quality, partner readiness, and sales capacity.
- Never state or imply that FastFactoring itself supplies credit, guarantees approval, or offers a particular advance rate.
- Use discovery or waitlist language for SME campaigns until territory-specific funding and regulatory arrangements are approved.
- Pause a cohort when complaints, hard bounces, or opt-outs exceed its stop rule; diagnose before resuming.

## Required Output

Return a short executive recommendation, country/vertical priority table, experiment cards, agent assignments, funnel targets, risks, dependencies, and next review date. State what evidence is observed versus inferred. Link every time-sensitive market or legal claim to a current primary source.
