# Streamlit Cloud deployment guide for controlled private beta

## What this deploy path actually is
- **Streamlit entrypoint:** `psyhelper_streamlit.py`.
- **FastAPI/API entrypoint:** `api/app.py` (`app` object, typically served via `uvicorn api.app:app`).
- Streamlit can run in:
  - **HTTP API mode** (`USE_HTTP_API=true`) and talk to FastAPI via `API_BASE_URL`.
  - **Local fallback mode** (`USE_HTTP_API=false`) where app logic runs in-process.

For controlled private beta staging, prefer explicit HTTP API mode with isolated backend and managed PostgreSQL.

## Required runtime configuration (production-like private beta)
Set these in **Streamlit Cloud → App settings → Secrets** (and equivalent backend host secrets):

- `ENVIRONMENT=production` (or `staging` for staging)
- `SECRET_KEY` (strong random value, >=32 chars)
- `DEBUG=false`
- `TESTING=false`
- `STRICT_PRODUCTION_MODE=true`
- `USE_POSTGRESQL=true`
- `DATABASE_URL=postgresql://...` (managed PostgreSQL)
- `USE_FILESYSTEM_FALLBACK=false`
- `AUTH_SECURITY_STATE_PATH` (only if local file persistence is still used)
- `AUDIT_LOG_PATH` (only if local file persistence is still used)
- `DATA_RIGHTS_STORAGE_PATH` (only if local file persistence is still used)
- `PRIVACY_POLICY_VERSION` (explicit)
- `TERMS_VERSION` (explicit)
- `CONSENT_ENFORCEMENT_ENABLED=true`
- `DATA_EXPORT_ENABLED=true` or `false` (explicit)
- `ADMIN_BOOTSTRAP_MODE=disabled` (or tightly controlled one-time `cli` before disable)
- `ADMIN_BOOTSTRAP_SECRET` (strong random value, >=32 chars)
- `CORS_ALLOWED_ORIGINS` (no wildcard in production-like env)
- `API_BASE_URL` (backend URL when using HTTP API mode)

## Optional configuration
- `REFERRER_POLICY` (default exists if unset)
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `REFRESH_TOKEN_EXPIRE_DAYS`
- `TOKEN_ISSUER`
- `DB_CONNECT_TIMEOUT_SEC`
- `DB_STATEMENT_TIMEOUT_MS`
- `LOGIN_RATE_LIMIT_ATTEMPTS`
- `LOGIN_RATE_LIMIT_WINDOW_SEC`
- `LOGIN_LOCKOUT_SEC`
- `BETA_TRIAL_DAYS`
- `EXPORT_OUTPUT_PATH` (ephemeral safe temp location, e.g. `/tmp/...`)

## How to set Streamlit secrets
1. Open Streamlit Cloud app settings.
2. Go to **Secrets**.
3. Paste key/value entries in TOML format.
4. Save and redeploy/reboot app.
5. Verify startup logs for missing key or import failures.

## Backend/API connection notes
- If backend is separate from Streamlit, deploy API (`uvicorn api.app:app`) to your backend host.
- Set `API_BASE_URL` in Streamlit secrets to backend base URL.
- Set `USE_HTTP_API=true` in Streamlit secrets.
- Ensure API host allows CORS from the Streamlit app origin only.

## Post-deploy smoke validation
- Dry-run local safety check:
  - `python scripts/smoke_test_private_beta.py --dry-run`
- Staging HTTP smoke:
  - `python scripts/smoke_test_private_beta.py --base-url https://<api-host>`
- Manual checklist only:
  - `python scripts/smoke_test_private_beta.py --manual-checklist`

## Rollback / redeploy basics
1. Revert to last known-good commit/tag.
2. Redeploy Streamlit app.
3. Redeploy backend API if separate.
4. Re-run smoke checks and manual checklist before reopening beta access.

## Log inspection basics
- Streamlit: App logs in Streamlit Cloud dashboard.
- API: host/container logs for FastAPI process.
- Verify auth/admin/export operations in audit logs and platform logs.

## Known limitations and caveats (important)
- Streamlit Cloud filesystem is **ephemeral**; do not depend on local disk for durable sensitive state.
- Production-like usage requires managed PostgreSQL and explicit persistence strategy for audit/auth/data-rights artifacts.
- This setup is for **controlled private beta validation**, not full clinical compliance certification.

## Streamlit watcher setting for deploy
- In deploy environments, Streamlit file watching is disabled via `.streamlit/config.toml` (`[server] fileWatcherType = "none"`) to avoid `OSError: [Errno 24] inotify instance limit reached` on large repositories.
