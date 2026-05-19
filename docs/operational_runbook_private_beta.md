# Operational runbook - controlled private beta

## 1) Pre-deploy checklist
- Confirm deployment target and rollback owner for this release window.
- Confirm production-like secret values are set (no placeholders, no defaults).
- Confirm `ENVIRONMENT` explicitly set (`staging` or `production`).
- Run:
  - `pytest -q`
  - `python scripts/preprod_readiness_check.py`
  - `python scripts/smoke_test_private_beta.py --dry-run`
- Confirm API and Streamlit entrypoints are unchanged or reviewed.
- Confirm managed PostgreSQL availability and credentials.
- Confirm incident channel and on-call contact for first beta window.

## 2) Deploy checklist
- Deploy backend API (`api/app.py`, `app`) if separate.
- Deploy Streamlit app (`psyhelper_streamlit.py`).
- Confirm secrets are loaded and no missing-key startup errors.
- Confirm CORS configuration matches Streamlit origin.
- Confirm admin bootstrap mode is intended for this window (`cli` for controlled bootstrap or `disabled`).

## 3) Post-deploy smoke checklist
- Run HTTP smoke against deployed API:
  - `python scripts/smoke_test_private_beta.py --base-url https://<api-host>`
- Run/print manual checklist:
  - `python scripts/smoke_test_private_beta.py --manual-checklist`
- Record smoke evidence: timestamp, operator, environment, pass/fail details.

## 4) First admin bootstrap
- Use one-time secure bootstrap path only in controlled terminal/session.
- Create first admin and verify login.
- Immediately set `ADMIN_BOOTSTRAP_MODE=disabled` and rotate bootstrap secret.

## 5) First therapist onboarding
- Admin creates therapist account in intended tenant.
- Therapist performs first login and policy/consent path.
- Verify therapist cannot access other tenant data.

## 6) First client test flow (synthetic data only)
- Create synthetic client profile.
- Record one mood entry.
- Create one homework assignment and one submission.
- Validate report/chat routes if enabled.

## 7) Data export flow
- Trigger self/data-rights export for synthetic account.
- Verify exported package integrity.
- Verify secure delivery path and temporary-file cleanup.

## 8) Delete/data-rights request handling
- Track request in governed workflow (ticket + audit trace).
- Do not hard-delete clinical records automatically.
- Confirm request status transitions and reviewer accountability.

## 9) Tenant/user suspension sanity
- Suspend a synthetic user/tenant via admin path.
- Verify blocked access after suspension.
- Verify action is captured in audit/platform logs.

## 10) Audit/log review
- Review auth failures, admin role changes, exports, and suspension actions.
- Ensure suspicious access or repeated failures are escalated.

## 11) Rollback procedure
- Roll back Streamlit/API to previous known-good commit.
- Verify service restoration.
- Re-run smoke + manual checklist before reopening access.
- Document incident and rollback rationale.

## 12) Incident response basics
- Contain: disable affected account/tenant/API key.
- Preserve logs and audit artifacts.
- Notify stakeholders.
- Patch/redeploy, then run smoke validation.
- Capture postmortem action items.

## 13) Beta limitations and caveats
- Controlled private beta only; not full clinical compliance attestation.
- Streamlit Cloud has ephemeral filesystem constraints.
- Sensitive persistence must be explicit (managed DB + durable audit strategy).
- Authenticated end-to-end flows still require supervised manual validation.
