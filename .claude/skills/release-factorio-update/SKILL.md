---
name: release-factorio-update
description: Complete a Factorio feature release from implementation through verification, change log, regenerated bilingual user guide, Coolify configuration/deployment, and stakeholder update email. Use when asked to ship, release, document, deploy, or announce a Factorio product update.
---

# Release a Factorio update

Run from the Factorio repository root.

## Workflow

1. Inspect `git status` and preserve unrelated user changes.
2. Implement and verify the feature locally. For database changes, keep `db/schema.sql` additive and run `python -m db.migrate`.
3. Add a dated entry to `docs/change_log.md` describing user-visible behavior, configuration, schema, and documentation changes.
4. Update `scripts/build_user_guide.py` and the applicable capture script. Run the app, recapture affected English and Russian screens, then run:

   ```bash
   .venv/bin/python -m scripts.build_user_guide
   ```

5. Confirm generated Markdown, HTML, PDF, and PPTX files open and contain the new feature.
6. Ensure every new environment variable appears in `.env.example`, `README.md`, and Coolify. Never copy a secret into git or logs.
7. Commit and push only when explicitly requested. Deploy using the `deploy-factorio` skill after the pushed commit exists.
8. Resolve the previous announcement audience from the Sent mailbox when available. Draft a concise “what’s new / how to try it” follow-up and attach the current English guide PDF. Send with `scripts/send_email.py`; report the confirmed Message-Id.

## Safety checks

- Do not claim Coolify was updated, production deployed, or email sent without confirmation.
- Treat invoice, bank, and recipient data as sensitive; use synthetic examples in documentation.
- Verify `factorio.co.uk` after deployment and exercise the changed role’s workflow.
