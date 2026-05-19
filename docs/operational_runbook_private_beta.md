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

## 2) Deploy selected commit
- Record selected commit hash.
- Deploy backend API (`api/app.py`, `app`) if separate.
- Deploy Streamlit app (`psyhelper_streamlit.py`).
- Confirm secrets are loaded and no missing-key startup errors.
- Confirm CORS configuration matches Streamlit origin.
- Confirm admin bootstrap mode is intended for this window (`cli` for controlled bootstrap or `disabled`).

## 3) Post-deploy smoke checklist + evidence capture
- Run HTTP smoke against deployed API:
  - `python scripts/smoke_test_private_beta.py --base-url https://<api-host>`
- Run dry-run evidence capture (offline-safe):
  - `python scripts/smoke_test_private_beta.py --dry-run --evidence-output /tmp/psyhelper-smoke-evidence.json`
- Optionally run HTTP evidence capture:
  - `python scripts/smoke_test_private_beta.py --base-url https://<api-host> --evidence-output /tmp/psyhelper-smoke-http-evidence.json`
- Run/print manual checklist:
  - `python scripts/smoke_test_private_beta.py --manual-checklist`
- Fill `docs/private_beta_rehearsal_evidence_template.md` with timestamp, operator, environment, and pass/fail details.

## 4) Synthetic data safety rules (mandatory)
- Use synthetic tenant/therapist/client identifiers with clear prefixes (`STAGING_SYNTH_`, `TEST_THERAPIST_`, `TEST_CLIENT_`).
- No real therapist/client names (unless explicit tester consent for therapist display name only).
- No real clinical histories, phone numbers, addresses, or legal/fiscal identifiers.
- Use fake email domains where possible.
- Never reuse production-like secrets.
- Keep delete/retention handling in governed workflow; do not perform automatic hard-deletes.

## 5) Manual authenticated staging rehearsal
- Use supervised manual flows only (no automated destructive/authenticated smoke in CI).
- Admin bootstrap: create first admin, verify login.
- Immediately set `ADMIN_BOOTSTRAP_MODE=disabled` and rotate bootstrap secret.
- Therapist onboarding/login in synthetic tenant.
- Create synthetic client, mood entry, homework assignment/submission.
- Validate report/chat routes if enabled.
- Trigger self/data-rights export for synthetic account.

## 6) Audit/log review
- Review auth failures, admin role changes, exports, suspension actions, and data-rights traces.
- Ensure suspicious access or repeated failures are escalated.
- Record audit/log evidence links in the rehearsal template.

## 7) Go/no-go + rollback
- Decide go/no-go only after evidence template completion.
- If no-go, execute rollback to previous known-good commit.
- Re-run smoke + manual checklist after rollback before reopening access.
- Document incident and rollback rationale.

## 8) Beta limitations and caveats
- Controlled private beta staging mode only; not full clinical compliance attestation.
- Streamlit Cloud has ephemeral filesystem constraints.
- Sensitive persistence must be explicit (managed DB + durable audit strategy).
- Authenticated end-to-end flows still require supervised manual validation.
- Invite first trusted therapist only after successful rehearsal + explicit go decision.

## 8) Decision documentation
- After rehearsal execution, generate an evidence summary draft (optional):
  - `python scripts/generate_private_beta_report.py --evidence /tmp/psyhelper-smoke-evidence.json`
- Complete `docs/private_beta_go_no_go_report_template.md` with readiness/smoke/manual outcomes.
- Log each defect in `docs/private_beta_staging_issue_log_template.md` with launch-blocking yes/no.
- Validate `docs/first_trusted_therapist_invite_checklist.md` before inviting first trusted therapist.
