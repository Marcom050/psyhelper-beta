# Private beta launch gate checklist (controlled staging rehearsal)

> Internal decision checklist for inviting the first trusted therapist. Use synthetic data only.

## Required deployed commit hash
- Commit hash under evaluation:
- Release tag (if any):

## Environment name
- Environment:
- Date/time (UTC):

## Staging URL
- Streamlit URL: `<STAGING_URL>`
- API base URL: `<STAGING_URL>`

## Operator / reviewer
- Operator:
- Reviewer:

## Automated checks required
- [ ] `pytest -q`
- [ ] `python -m py_compile psyhelper_streamlit.py`
- [ ] `python scripts/preprod_readiness_check.py`
- [ ] `python scripts/smoke_test_private_beta.py --dry-run`
- [ ] `python scripts/smoke_test_private_beta.py --base-url <STAGING_URL>`
- [ ] Evidence files stored (example: `/tmp/psyhelper-smoke-evidence.json`, `/tmp/psyhelper-http-evidence.json`)

## Manual checks required
- [ ] Manual checklist reviewed (`python scripts/smoke_test_private_beta.py --manual-checklist`)
- [ ] Manual therapist/client flow executed end-to-end in staging
- [ ] Evidence template updated (`docs/private_beta_rehearsal_evidence_template.md`)
- [ ] Issues logged (`docs/private_beta_staging_issue_log_template.md`)

## Synthetic-data confirmation
- [ ] Only synthetic tenant/therapist/client identities were used.
- [ ] No real patient data, real credentials, or real production secrets were used.

## Italian UI/copy confirmation
- [ ] Product-facing text shown during rehearsal is in Italian.
- [ ] Private beta disclaimers shown to users are in Italian.

## Chat/logout confirmation
- [ ] Chat works in staging for synthetic users.
- [ ] “Pulisci chat corrente” works in staging.
- [ ] Logout clears visible chat state automatically.

## Therapist flow confirmation
- [ ] Therapist onboarding/login flow validated manually.
- [ ] Controlled-beta context explained to therapist tester.

## Client creation confirmation
- [ ] Client profile creation works with synthetic identifiers.

## Diary/mood confirmation
- [ ] Mood/diary entry creation and visibility verified.

## Homework confirmation
- [ ] Homework assignment and completion flow verified.

## Chat confirmation
- [ ] Chat response path works without blocker errors in logs.

## Export/data-rights confirmation
- [ ] Synthetic self-export flow validated.
- [ ] Data-rights/delete-request governed process validated (no destructive automation).

## Audit/log confirmation
- [ ] Auth/admin/export actions appear in audit/platform logs.

## Tenant/subscription confirmation
- [ ] Tenant scoping is correct.
- [ ] Subscription/trial gating behaves as expected for beta tenant.

## Known limitations
- Limitation 1:
- Limitation 2:

## Open issues by severity
- Blocker:
- High:
- Medium:
- Low:

## Blocker/high issue policy
- GO requires **0 blocker** and **0 high unresolved issues**.
- GO WITH CONDITIONS requires **0 blocker** and explicitly accepted high/medium limitations with mitigation and owner.
- NO-GO if any blocker remains or if privacy/security/tenant/data/export flows are not validated.

## Rollback/support readiness
- [ ] Rollback owner identified and reachable.
- [ ] Support contact path defined and tested.
- [ ] Incident handling expectations documented for controlled beta.

## Final decision
- [ ] GO
- [ ] GO WITH CONDITIONS
- [ ] NO-GO

## Decision rationale and required next action
- Rationale:
- Next action:
