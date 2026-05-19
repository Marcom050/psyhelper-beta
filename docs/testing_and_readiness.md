# Testing and pre-production readiness

## Local test commands
- Main suite: `pytest -q`
- Warnings-visible run: `pytest -q -W default`

The CI baseline is green when `pytest -q` passes with no internal regressions.

## Warning hygiene policy
- Internal warnings are fixed in code where safe.
- Third-party warnings are filtered only when they are known upstream deprecations and do not mask project warnings.
- Current targeted filters are in `pytest.ini` for LangChain `asyncio.iscoroutinefunction` and `RunnableWithMessageHistory` deprecations.

## Run readiness check
- Command: `python scripts/preprod_readiness_check.py`
- Output: PASS/FAIL by check + summary.
- Exit code: non-zero only for critical failures.

## Minimum env vars
For production-like checks:
- `ENVIRONMENT=production`
- `SECRET_KEY` (>=32 chars, non-default)
- `USE_POSTGRESQL=true`
- `DATABASE_URL` set if postgres is enabled
- `USE_FILESYSTEM_FALLBACK=false` (recommended for strict mode)
- `AUTH_SECURITY_STATE_PATH` set
- `AUDIT_LOG_PATH` set
- `CORS_ALLOWED_ORIGINS` not `*`

## Storage notes for tests
- Test suite isolates filesystem-backed auth/audit paths and resets mutable backend flags between tests.
- Avoid hardcoded local absolute paths inside tests.

## What green CI means
- Repository dependencies install successfully.
- `pytest -q` passes in a clean environment.
- No deploy action is triggered.

## What is NOT yet production-ready
- This baseline does not add HA infrastructure, observability stack, auto-deploy, or enterprise key management.
- Readiness check is a guardrail script, not a compliance certification.
