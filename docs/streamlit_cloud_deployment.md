# Streamlit Cloud deployment readiness (controlled private beta)

## Scope
This document covers deploying `psyhelper_streamlit.py` on Streamlit Cloud for a controlled private beta.

## Mandatory secrets / environment variables
Configure these in **Streamlit Cloud → App settings → Secrets**:
- `ENVIRONMENT=production`
- `SECRET_KEY` (>=32 random chars)
- `DEBUG=false`
- `TESTING=false`
- `STRICT_PRODUCTION_MODE=true`
- `USE_POSTGRESQL=true`
- `DATABASE_URL=...` (managed PostgreSQL)
- `USE_FILESYSTEM_FALLBACK=false`
- `AUTH_SECURITY_STATE_PATH` (persistent mounted path if available)
- `AUDIT_LOG_PATH` (persistent mounted path if available)
- `DATA_RIGHTS_STORAGE_PATH` (persistent mounted path if available)
- `PRIVACY_POLICY_VERSION`
- `TERMS_VERSION`
- `CONSENT_ENFORCEMENT_ENABLED=true`
- `DATA_EXPORT_ENABLED=true|false` (explicit)
- `ADMIN_BOOTSTRAP_MODE=disabled`
- `ADMIN_BOOTSTRAP_SECRET` (>=32 random chars)
- `CORS_ALLOWED_ORIGINS`

## Streamlit Cloud specific risks
- Filesystem is ephemeral across restarts/redeploys: do **not** rely on local files for sensitive state.
- Secrets are managed in Streamlit settings, not `.env` files.
- Relative paths may point to ephemeral container storage.
- Persistent storage for audit/auth/data-rights is not native; prefer managed DB-backed persistence before handling sensitive production workloads.

## Entrypoint / runtime
- App entrypoint: `psyhelper_streamlit.py`.
- Verify Python version compatibility with `requirements.txt` on Streamlit Cloud runtime.
- Ensure `requirements.txt` includes FastAPI/Streamlit/PostgreSQL deps required by selected runtime path.

## Redeploy
1. Push changes to tracked branch.
2. In Streamlit Cloud, click **Reboot app** or **Deploy** latest commit.
3. Verify logs show successful imports and startup.

## Logs
- Open **Manage app → Logs** for runtime/import errors.
- Typical breakages: missing dependency, missing secret, invalid `DATABASE_URL`, permission/path errors.

## Post-deploy smoke
Run:
- `python scripts/smoke_test_private_beta.py --base-url https://<api-host>` (if API exposed)
- `python scripts/smoke_test_private_beta.py` (dry-run fallback)

Then validate manual checklist flows: login, therapist onboarding, client creation, mood, homework, report/export.

## Sensitive-data caveat
Streamlit Cloud is suitable for controlled beta validation, but sensitive clinical persistence must be externalized (managed PostgreSQL and persistent audit/auth/data-rights strategy) before scaling.
