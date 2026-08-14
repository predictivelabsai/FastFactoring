# Agent Resources

`agents/skills/` contains framework-agnostic operating skills for FastFactoring GTM, SME prospecting, and controlled outreach. Each skill follows the portable `SKILL.md` convention and keeps detailed guidance in adjacent `references/` and deterministic utilities in `scripts/`.

Agent runtimes may discover or load these files using their native mechanism. The repository copies intentionally omit vendor-specific manifests, SDK calls, and orchestration code. A country agent may research, classify, and draft, but only the central governed workflow may approve cohorts or operate a future sender.

The canonical editable copies also live in the shared skills repository. Keep behavior and safeguards synchronized when either copy changes.
