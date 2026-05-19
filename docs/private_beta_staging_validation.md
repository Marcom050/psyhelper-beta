# Private beta staging validation (go/no-go)

## Purpose
Define the minimum validation bar before inviting the first trusted therapist into controlled private beta, based on a documented staging rehearsal using synthetic tenant data only.

## Synthetic data safety rules (required)
- Do not use real therapist names unless the tester explicitly consents.
- Do not use real patient/client names.
- Do not use real clinical histories.
- Do not use real phone numbers, addresses, or fiscal/legal identifiers.
- Use clearly fake emails/domains whenever possible.
- Use synthetic clinical notes only.
- Prefix all rehearsal records with clear synthetic markers (for example `STAGING_SYNTH_`, `TEST_THERAPIST_`, `TEST_CLIENT_`).
- Never reuse production-like secrets in rehearsal data.
- Delete/retention handling remains governed workflow; no automatic hard-delete flows.

## Preconditions before first invite
- Deployment completed for Streamlit + API entrypoints.
- `pytest -q` passing on release commit.
- `python scripts/preprod_readiness_check.py` passing in staging/production-like env.
- `python scripts/smoke_test_private_beta.py --dry-run` passing.
- `python scripts/smoke_test_private_beta.py --base-url <staging-api>` passing at least one safe health endpoint.
- Manual checklist completed on synthetic tenant/user.
- Rollback owner identified and reachable.

## Automated checks
- Unit/integration test suite (`pytest -q`).
- Preprod readiness config policy check.
- Smoke dry-run local checks.
- Smoke HTTP safe endpoint checks (`/health`, `/health/db` when available).
- Optional smoke evidence capture JSON:
  - `python scripts/smoke_test_private_beta.py --dry-run --evidence-output /tmp/psyhelper-smoke-evidence.json`
  - `python scripts/smoke_test_private_beta.py --base-url <staging-api> --evidence-output /tmp/psyhelper-smoke-http-evidence.json`

## Manual checks (still required)
- Admin bootstrap and disable procedure.
- Therapist onboarding/login.
- Client creation and mood entry.
- Homework assignment/submission.
- Report/chat sanity if enabled.
- Self export and temporary-file handling.
- Audit/log verification.
- Tenant/subscription access sanity.
- Data-rights/delete request sanity in governed workflow.

## Evidence capture requirement
- Fill `docs/private_beta_rehearsal_evidence_template.md` for each rehearsal.
- Capture commit hash, operator, exact commands, return codes, and environment.
- Attach smoke evidence JSON paths, screenshots, and log snippets.
- Record launch blockers and final go/no-go decision with sign-off.

## Accepted controlled-beta risks
- Authenticated clinical flows remain manual-only in this sprint for safety.
- Streamlit-hosted runtime may have platform limitations for sensitive persistence.
- Incident controls are operational/process-driven, not fully automated.

## Go / no-go criteria
### Go
- All automated checks pass.
- All manual checklist items pass on synthetic data.
- Rehearsal evidence template completed with sign-off.
- No critical readiness failures.
- No unresolved P0/P1 security or data-isolation defects.

### No-go
- Any critical readiness check fails.
- Health endpoints unreachable after deploy.
- Tenant boundary/access-control anomaly observed.
- Export/delete-rights process cannot be executed and audited.
- Missing rehearsal evidence or incomplete decision record.

## Launch blockers
- Missing/weak production secret configuration.
- Silent filesystem fallback enabled in production.
- PostgreSQL required but `DATABASE_URL` missing/invalid.
- Admin bootstrap left enabled without compensating controls.
- Audit/data-rights persistence unavailable for beta workflows.
- Synthetic data safeguards not followed.
