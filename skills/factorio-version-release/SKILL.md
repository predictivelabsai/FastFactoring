---
name: factorio-version-release
description: Version Factorio releases and keep docs/change_log.md synchronized. Use when completing a major product commit, shipping a feature or integration, making a breaking platform change, preparing a release, or when asked to bump, tag, publish, or report the Factorio version.
---

# Factorio Version Release

Treat the repository-root `VERSION` file as the single source of truth. Use
Semantic Versioning and update `docs/change_log.md` in the same commit.

## Choose the bump

- `major`: incompatible API, schema, authentication, role, or primary workflow change.
- `minor`: substantive backward-compatible product, AI-agent, integration, or workflow capability.
- `patch`: backward-compatible fix, security hardening, or intentionally released documentation correction.
- No bump: intermediate commits, generated artifacts, screenshots, formatting, tests, or archive moves that belong to an unreleased change.

Interpret “major commit” as a release-significant commit, not automatically a
SemVer major bump. Prefer `minor` for normal major product features.

## Release workflow

1. Inspect `git status`, recent commits, `VERSION`, and the top of
   `docs/change_log.md`.
2. Confirm the change is release-significant and select the bump using the rules
   above. Never infer a breaking `major` release from commit size alone.
3. Run:

   ```bash
   python skills/factorio-version-release/scripts/bump_version.py minor \
     --change "Added the borrower connection workflow." \
     --change "Added evaluated Customer Service email skills."
   ```

4. Review the generated `VERSION` and change-log entry. Rewrite change bullets
   if they are vague; describe user-visible behavior, migration/configuration
   impact, and approval or safety boundaries.
5. Run relevant tests and `git diff --check`.
6. Include `VERSION`, `docs/change_log.md`, implementation, and generated assets
   in one focused commit. Push only when the user requested or the active task
   already includes pushing.
7. Report the old and new versions plus verification performed.

## Guardrails

- Never edit old released entries to disguise history; add a new entry.
- Never bump more than once for multiple commits in the same unreleased feature.
- Never include secrets or environment values in the change log.
- Do not create a Git tag or external release unless explicitly requested.
- If `VERSION` is absent, establish `1.0.0` only for an explicit baseline;
  otherwise ask which baseline the user wants.
