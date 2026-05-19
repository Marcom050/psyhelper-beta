from __future__ import annotations

import os
import sys
from pathlib import Path

DEFAULT_DEV_SECRET = "psyhelper-beta-dev-secret-change-me"


def _as_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _check(name: str, passed: bool, detail: str, critical: bool = False) -> tuple[bool, bool]:
    status = "PASS" if passed else "FAIL"
    marker = "CRITICAL" if critical else "WARN"
    print(f"[{status}] {name}: {detail}" + ("" if passed else f" ({marker})"))
    return passed, critical and not passed


def run() -> int:
    env = os.getenv("ENVIRONMENT", "development").strip().lower()
    is_prod = env == "production"

    failures = 0
    critical_failures = 0

    secret = os.getenv("SECRET_KEY", "")
    use_postgres = _as_bool("USE_POSTGRESQL", False)
    db_url = os.getenv("DATABASE_URL", "").strip()
    use_fs = _as_bool("USE_FILESYSTEM_FALLBACK", True)
    strict = _as_bool("STRICT_PRODUCTION_MODE", is_prod)
    debug = _as_bool("DEBUG", False)
    testing = _as_bool("TESTING", False)
    cors_origins = os.getenv("CORS_ALLOWED_ORIGINS", "").strip()
    audit_path = os.getenv("AUDIT_LOG_PATH", "").strip()
    auth_path = os.getenv("AUTH_SECURITY_STATE_PATH", "").strip()
    privacy_policy_version = os.getenv("PRIVACY_POLICY_VERSION", "").strip()
    terms_version = os.getenv("TERMS_VERSION", "").strip()
    consent_enforcement = _as_bool("CONSENT_ENFORCEMENT_ENABLED", True)
    data_export_enabled = os.getenv("DATA_EXPORT_ENABLED", "").strip().lower()
    admin_bootstrap_secret = os.getenv("ADMIN_BOOTSTRAP_SECRET", "").strip()
    admin_bootstrap_mode = os.getenv("ADMIN_BOOTSTRAP_MODE", "cli").strip().lower()

    checks = [
        _check("ENVIRONMENT valid", env in {"development", "staging", "production"}, f"ENVIRONMENT={env or 'unset'}", critical=True),
        _check("SECRET_KEY set for production", (not is_prod) or (len(secret) >= 32 and secret != DEFAULT_DEV_SECRET), "SECRET_KEY secure in production", critical=True),
        _check("Storage backend selected", use_postgres or use_fs, f"USE_POSTGRESQL={use_postgres}, USE_FILESYSTEM_FALLBACK={use_fs}", critical=True),
        _check("DATABASE_URL when postgres", (not use_postgres) or bool(db_url), f"DATABASE_URL {'present' if db_url else 'missing'}", critical=True),
        _check("DEBUG disabled in production", (not is_prod) or (not debug), f"DEBUG={debug}", critical=True),
        _check("TESTING flag disabled in production", (not is_prod) or (not testing), f"TESTING={testing}", critical=True),
        _check("Auth security persistence configured", (not is_prod) or bool(auth_path), f"AUTH_SECURITY_STATE_PATH={'set' if auth_path else 'unset'}", critical=True),
        _check("Audit persistence configured", (not is_prod) or bool(audit_path), f"AUDIT_LOG_PATH={'set' if audit_path else 'unset'}", critical=True),
        _check("Privacy policy version configured", (not is_prod) or bool(privacy_policy_version), f"PRIVACY_POLICY_VERSION={privacy_policy_version or 'unset'}", critical=True),
        _check("Terms version configured", (not is_prod) or bool(terms_version), f"TERMS_VERSION={terms_version or 'unset'}", critical=True),
        _check("Consent enforcement enabled", (not is_prod) or consent_enforcement, f"CONSENT_ENFORCEMENT_ENABLED={consent_enforcement}", critical=True),
        _check("Data export feature flag explicit", (not is_prod) or (data_export_enabled in {'true','false','1','0','yes','no','on','off'}), f"DATA_EXPORT_ENABLED={data_export_enabled or 'unset'}", critical=True),
        _check("Admin bootstrap mode configured", (not is_prod) or (admin_bootstrap_mode in {'cli','disabled'}), f"ADMIN_BOOTSTRAP_MODE={admin_bootstrap_mode or 'unset'}", critical=True),
        _check("Admin bootstrap secret configured", (not is_prod) or (len(admin_bootstrap_secret) >= 32 and admin_bootstrap_secret.lower() not in {'changeme','default','admin-bootstrap-secret'}), "ADMIN_BOOTSTRAP_SECRET secure", critical=True),
        _check("CORS basic sanity", (not is_prod) or (cors_origins not in {"", "*"}), f"CORS_ALLOWED_ORIGINS={cors_origins or 'unset'}"),
        _check("pytest config present", Path("pytest.ini").exists(), "pytest.ini found", critical=True),
        _check("Strict production mode", (not is_prod) or strict, f"STRICT_PRODUCTION_MODE={strict}"),
    ]

    for passed, is_critical_failure in checks:
        if not passed:
            failures += 1
            critical_failures += int(is_critical_failure)

    print(f"\nSummary: {len(checks)-failures} PASS / {failures} FAIL (critical: {critical_failures})")
    return 1 if critical_failures else 0


if __name__ == "__main__":
    sys.exit(run())
