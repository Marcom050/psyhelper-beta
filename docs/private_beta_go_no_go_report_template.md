# Private beta controlled staging - first go/no-go report template

> Internal rehearsal artifact only. Use synthetic data only. Do **not** include real credentials, secrets, or real clinical data.

## 1) Report metadata
- Report date/time (UTC):
- Environment name:
- Deployed commit hash:
- Deployment URL(s):
- Operator:
- Reviewer:
- Rehearsal evidence file path/link:
- Smoke evidence JSON path/link:

## 2) Rehearsal execution results
- Readiness result (`python scripts/preprod_readiness_check.py`):
- HTTP smoke result (`python scripts/smoke_test_private_beta.py --base-url ...`):
- Manual authenticated flow results (checklist summary):

### Synthetic rehearsal identities
- Synthetic tenant identifier:
- Synthetic therapist identifier:
- Synthetic client identifier:

## 3) Issue summary
- Total issues:
- Blocker issues count:
- High issues count:
- Medium issues count:
- Low issues count:

### Blocker issues
- ISSUE-___:

### High issues
- ISSUE-___:

### Medium issues
- ISSUE-___:

### Low issues
- ISSUE-___:

## 4) Observations
### Security/privacy observations
- 

### Data persistence observations
- 

### Audit/log observations
- 

### UX observations
- 

## 5) Decision and risk treatment
- Rollback decision (if NO-GO or rollback-triggered GO WITH CONDITIONS):
- Accepted risks:
- Required fixes before real therapist invite:

### Final decision (select one)
- [ ] GO
- [ ] GO WITH CONDITIONS
- [ ] NO-GO

### Decision rationale
-

## 6) Sign-off
- Operator name + timestamp:
- Reviewer name + timestamp:
- Engineering lead sign-off:
- Product/operations sign-off:

## 7) Safety reminders
- No real therapist/client records were used in this rehearsal.
- No destructive automated flows were executed.
- This report does **not** represent production clinical compliance certification.
