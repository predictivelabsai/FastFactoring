# Country scout configurations

These are research and localization roles, not independent senders. Apply the worker packet and gates in `agent-operating-model.md` to every assignment.

| Agent ID | Locale | Initial sectors | Default channel posture |
|---|---|---|---|
| `ff-scout-uk` | `en-GB` | Manufacturing, logistics, construction, wholesale, staffing, institutional medical | Corporate ABM only after UK entity/PECR gate; exclude sole traders and affected partnerships |
| `ff-scout-ee` | `et-EE` | Medical, industrial/logistics, hospitality | Legal-entity research/pilot after current national review |
| `ff-scout-lv` | `lv-LV` | Logistics, manufacturing, construction, hospitality, medical | Partner/research first; legal mailbox only after local review |
| `ff-scout-lt` | `lt-LT` | Industrial/logistics, medical, B2B services | Legal-person pilot only after current national review |
| `ff-scout-fr` | `fr-FR` | Manufacturing, transport, construction, professional/medical suppliers | Role-relevant professional B2B plus partner route after CNIL review |
| `ff-scout-de` | `de-DE` | Manufacturing, logistics, wholesale, infrastructure buyers | Send-disabled; partner, event and consent capture |
| `ff-scout-pl` | `pl-PL` | Manufacturing, logistics, wholesale, construction | Send-disabled; partner, webinar and consent capture |
| `ff-scout-nl` | `nl-NL` | Trade/logistics, staffing, agriculture, infrastructure buyers | Send-disabled; ERP/accountant partnership and inbound |
| `ff-scout-da` | `da-DK` | Logistics, manufacturing, food, hospitality suppliers | Send-disabled; consent and partner-led |
| `ff-scout-sv` | `sv-SE` | Manufacturing, transport, B2B services | Partner first; legal-person route only after current review |
| `ff-scout-fi` | `fi-FI` | Manufacturing, forestry/food, logistics, services | Partner first; legal-person route only after current review |
| `ff-scout-no` | `nb-NO` | Maritime/logistics, energy services, seafood, B2B services | Send-disabled for named contacts; partner/inbound |

## Assignment template

```yaml
agent_id: ff-scout-uk
objective: Validate 50 incorporated manufacturing suppliers for a discovery experiment.
allowed: [official_sources, company_websites, approved_company_dataset]
prohibited: [sending, credential_use, shared_state_writes, personal_data_export]
output: country_brief_and_immutable_candidate_artifact
as_of: YYYY-MM-DD
acceptance:
  - primary sources linked
  - source and inference distinguished
  - legal entity IDs preserved
  - invoice fit marked observed_or_unknown
  - no prospect contacted
```

For multi-country work, run scouts in parallel only through the artifact stage. The controller compares outputs, the data steward merges them, and the central gates determine whether any later outreach is permissible.
