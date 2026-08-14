# Approval and policy records

## Country policy record

```yaml
policy_id: UK-CORP-EMAIL-2026-08-v1
country: UK
approved_channels: [corporate_email]
approved_entity_types: [limited_company, llp, public_body]
blocked_entity_types: [sole_trader, ordinary_partnership, unknown]
legal_basis: documented_legitimate_interests_assessment
source_snapshot:
  - url: https://...
    checked_at: YYYY-MM-DD
consent_evidence_required: false
privacy_pattern_id: UK-ARTICLE14-SHORT-v1
legal_reviewer: name_or_roster_id
native_reviewer: name_or_roster_id
approved_at: YYYY-MM-DDTHH:MM:SSZ
expires_at: YYYY-MM-DDTHH:MM:SSZ
```

Unknown reviewer IDs, expired records, or missing source snapshots block the market. Maintain an approved reviewer roster outside the skill; the skill does not invent or self-approve reviewers.

## Campaign approval artifact

```yaml
approval_id: APR-UK-MFG-001
campaign_id: UK-MFG-001
experiment_id: UK-MFG-001
policy_id: UK-CORP-EMAIL-2026-08-v1
cohort_sha256: ...
copy_bundle_sha256: ...
suppression_snapshot_id: ...
consent_evidence_snapshot_id: ... # mandatory for consent-based campaigns
consent_evidence_snapshot_sha256: ... # mandatory for consent-based campaigns
sender_config_id: ...
territory_funder_status: discovery_only
territory_funder_approval_reference: legal_or_partner_record_id
territory_funder_expires_at: YYYY-MM-DDTHH:MM:SSZ
approved_motion: sme_design_partner
approved_claims: [software_only, discovery_interview]
approved_contact_count: 20
daily_cap: 20
send_window: 09:00-16:00 Europe/London
retention_schedule_id: FF-RETENTION-v1
legal_reviewer: ...
native_reviewer: ...
user_approval_reference: ...
approved_at: ...
expires_at: ...
```

Store approval artifacts in an access-controlled, append-only location configured by the operator. Preflight must verify every referenced hash/ID and the expiry. Do not invent a path when no campaign state store is configured.

## Recipient consent artifact

Consent-based campaigns require an immutable snapshot in which every approved recipient has a current record:

```yaml
consent_id: CONSENT-DE-0001
person_id: ...
email: ...
controller: ...
campaign_purpose: FastFactoring infrastructure discovery
consent_text: exact text shown to the person
consent_scope: [email, named_purpose]
collection_source: form_or_event_record
collected_at: YYYY-MM-DDTHH:MM:SSZ
proof_artifact_sha256: ...
policy_version: FF-OUTREACH-2026-08-14-v1
withdrawn_at: null
verified_at: YYYY-MM-DDTHH:MM:SSZ
verifier: approved_reviewer_id
```

The campaign approval references the snapshot ID and hash. Preflight must prove a one-to-one match between every intended recipient and an unwithdrawn, purpose-specific consent record. Missing or mismatched evidence blocks the recipient.

## Technical launch gate

Live outreach remains blocked until the sender has:

- an atomic suppression check plus unique `(campaign_id, person_id, touch)` constraint;
- hard terminal-event blocking for reply, bounce, complaint, opt-out and do-not-contact;
- localized reply/opt-out detection for the campaign locale;
- a configured sender identity, credential preflight and approved domain-health limits;
- current mailbox-level verification that rejects guessed, MX-only and catch-all results.

## Territory/funder status

Every country must be one of `software_only`, `discovery_only`, `partner_referral_approved`, or `application_flow_approved`, with the approving legal/funding-partner reference and expiry. In the first two states, messages may not solicit finance applications or quote financing outcomes.
