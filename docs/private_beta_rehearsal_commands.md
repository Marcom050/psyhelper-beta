# Private beta staging rehearsal commands (controlled, synthetic-only)

Use this command guide for the first controlled staging rehearsal. Do not use real secrets or real clinical data.

## Local output paths (recommended)
- Dry-run evidence: `/tmp/psyhelper-smoke-evidence.json`
- HTTP evidence: `/tmp/psyhelper-http-evidence.json`
- Draft report: `/tmp/private-beta-report.md`

## 1) Readiness check
```bash
python scripts/preprod_readiness_check.py
```

## 2) Dry-run smoke + evidence output
```bash
python scripts/smoke_test_private_beta.py --dry-run --evidence-output /tmp/psyhelper-smoke-evidence.json
```

## 3) HTTP smoke on staging base URL + evidence output
```bash
python scripts/smoke_test_private_beta.py --base-url <STAGING_URL> --evidence-output /tmp/psyhelper-http-evidence.json
```

## 4) Report generation from evidence files
```bash
python scripts/generate_private_beta_report.py \
  --evidence /tmp/psyhelper-smoke-evidence.json /tmp/psyhelper-http-evidence.json \
  --output /tmp/private-beta-report.md
```

## 5) What to copy into the go/no-go report
Copy the following into `docs/private_beta_go_no_go_report_template.md` output:
- Commit hash evaluated
- Exact commands run + return codes
- Evidence file paths and summary findings
- Manual checklist outcomes
- Open issues by severity (blocker/high/medium/low)
- Final decision: GO / GO WITH CONDITIONS / NO-GO

## 6) Manual steps required after commands
These are required and not automated in this sprint:
- Run manual checklist (`python scripts/smoke_test_private_beta.py --manual-checklist`)
- Validate therapist/client journey with synthetic records only
- Confirm chat/logout behavior in staging
- Validate export/data-rights governed process
- Validate audit logs + tenant/subscription behavior
- Record findings in rehearsal evidence + issue log templates
