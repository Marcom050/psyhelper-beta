# Private beta staging rehearsal evidence template

> Controlled private beta only. Synthetic tenant/test data only. Do **not** include real credentials, real therapist/client data, or secrets.

## Rehearsal metadata
- Rehearsal date/time (UTC):
- Environment name (`staging`, etc.):
- Commit hash deployed:
- Deployment URL(s):
  - API:
  - Streamlit:
- Operator:

## Synthetic identifiers used
- Synthetic tenant identifier:
- Synthetic therapist identifier:
- Synthetic client identifier:
- Synthetic data prefixes verified (for example `STAGING_SYNTH_`, `TEST_THERAPIST_`, `TEST_CLIENT_`):

## Environment and readiness evidence
- Env/config checklist result:
- Readiness check result (`python scripts/preprod_readiness_check.py`):
- Smoke dry-run result (`python scripts/smoke_test_private_beta.py --dry-run`):
- HTTP smoke result (`python scripts/smoke_test_private_beta.py --base-url ...`):
- Smoke evidence JSON path(s):

## Manual authenticated rehearsal results
- Admin bootstrap result:
- Therapist login/onboarding result:
- Client creation result:
- Mood entry result:
- Homework assignment result:
- Report/chat check result (if available):
- Self export result:
- Audit/log verification result:
- Tenant/subscription sanity result:
- Data rights/delete request sanity result:

## Findings and risk
- Issues found:
- Severity of issues (P0/P1/P2/P3):
- Launch blockers present? (yes/no + details):
- Rollback decision:
- Go/no-go decision:

## Evidence attachments
- Screenshot links/placeholders:
- Log snippet links/placeholders:
- Command output links/placeholders:
- Ticket/incident links (if any):

## Final sign-off
- Decision owner:
- Security/privacy reviewer:
- Timestamp:
- Notes:

## Report handoff
- Convert captured smoke evidence JSON into a review draft (optional):
  - `python scripts/generate_private_beta_report.py --evidence /tmp/psyhelper-smoke-evidence.json --output /tmp/private-beta-report.md`
- Use that summary plus this evidence sheet to complete `docs/private_beta_go_no_go_report_template.md`.
- Any rehearsal issues should be tracked in `docs/private_beta_staging_issue_log_template.md`.
