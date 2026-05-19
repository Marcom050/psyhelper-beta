# Operational runbook - controlled private beta

## Pre-deploy checklist
- Confirm `.env.production.example` values are populated in hosting secrets (no default secrets).
- Run `pytest -q`.
- Run `python scripts/preprod_readiness_check.py` in production-like env.
- Confirm PostgreSQL reachable and schema bootstrap succeeds.
- Confirm audit/auth/data-rights paths are persistent or moved to managed persistence.

## Post-deploy smoke test
- Run `python scripts/smoke_test_private_beta.py --base-url <api-url>` if API reachable.
- If not, run `python scripts/smoke_test_private_beta.py` and execute manual flow checklist.

## First admin creation
- Preferred: one-time CLI bootstrap (`ADMIN_BOOTSTRAP_MODE=cli`) in controlled secure terminal.
- After bootstrap, set `ADMIN_BOOTSTRAP_MODE=disabled` and rotate bootstrap secret.

## Invite first therapist
- Admin creates therapist account under correct tenant.
- Therapist performs first login and consent acceptance.

## Suspend user/tenant
- Set account metadata status to suspended via admin tooling.
- Record action in audit log with reason and timestamp.

## Data export
- Use privacy/data-rights service endpoints or admin tooling.
- Ensure exports are delivered securely and removed from temporary storage after delivery.

## Delete request handling
- Process as governed delete request (no hard-delete automation for clinical records).
- Mark lifecycle status and maintain legal/audit trace.

## Manual rollback
- Roll back app to previous known-good commit.
- Re-run smoke tests and readiness check.
- Verify DB schema remains additive and compatible.

## Audit/logs
- Review `AUDIT_LOG_PATH` output and platform logs daily during beta.
- Escalate unusual auth failures, role changes, and export/delete operations.

## Incident response
- Contain: suspend affected account/tenant.
- Preserve evidence: snapshot logs/audit trails.
- Notify stakeholders per beta incident policy.
- Recover service and document postmortem.

## Declared beta limits
- Controlled private beta only.
- No automatic clinical hard-delete.
- No billing production flows.
- Streamlit hosting limitations for sensitive data persistence must be acknowledged.
