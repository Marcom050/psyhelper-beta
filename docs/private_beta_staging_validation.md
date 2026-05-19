# Private beta staging validation (go/no-go)

## Purpose
Define the minimum validation bar before inviting the first real therapist into controlled private beta.

## Preconditions before first invite
- Deployment completed for Streamlit + API entrypoints.
- `pytest -q` passing on release commit.
- `python scripts/preprod_readiness_check.py` passing in staging/production-like env.
- `python scripts/smoke_test_private_beta.py --base-url <staging-api>` passing at least one safe health endpoint.
- Manual checklist completed on synthetic tenant/user.
- Rollback owner identified and reachable.

## Automated checks
- Unit/integration test suite (`pytest -q`).
- Preprod readiness config policy check.
- Smoke dry-run local checks.
- Smoke HTTP safe endpoint checks (`/health`, `/health/db` when available).

## Manual checks
- Admin bootstrap and disable procedure.
- Therapist onboarding/login.
- Client creation and mood entry.
- Homework assignment/submission.
- Report/chat sanity if enabled.
- Self export and temporary-file handling.
- Audit/log verification.
- Tenant/subscription access sanity.

## Accepted controlled-beta risks
- Some authenticated clinical flows are manual-only (not fully automated smoke).
- Streamlit-hosted runtime may have platform limitations for sensitive persistence.
- Incident controls are operational/process-driven, not fully automated.

## Go / no-go criteria
### Go
- All automated checks pass.
- All manual checklist items pass on synthetic data.
- No critical readiness failures.
- No unresolved P0/P1 security or data-isolation defects.

### No-go
- Any critical readiness check fails.
- Health endpoints unreachable after deploy.
- Tenant boundary/access-control anomaly observed.
- Export/delete-rights process cannot be executed and audited.

## What to capture after first smoke run
- Commit hash, environment, timestamp, operator.
- Smoke command outputs and return codes.
- Manual checklist results and screenshots/log references.
- Open risks and accepted exceptions.
- Decision record (go/no-go) with approver.

## Launch blockers
- Missing/weak production secret configuration.
- Silent filesystem fallback enabled in production.
- PostgreSQL required but `DATABASE_URL` missing/invalid.
- Admin bootstrap left enabled without compensating controls.
- Audit/data-rights persistence unavailable for beta workflows.
