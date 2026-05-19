from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


REQUIRED_ENV_KEYS = {
    "ENVIRONMENT",
    "SECRET_KEY",
    "DEBUG",
    "TESTING",
    "USE_POSTGRESQL",
    "DATABASE_URL",
    "USE_FILESYSTEM_FALLBACK",
    "AUTH_SECURITY_STATE_PATH",
    "AUDIT_LOG_PATH",
    "DATA_RIGHTS_STORAGE_PATH",
    "EXPORT_OUTPUT_PATH",
    "ADMIN_BOOTSTRAP_MODE",
    "ADMIN_BOOTSTRAP_SECRET",
    "PRIVACY_POLICY_VERSION",
    "TERMS_VERSION",
    "CONSENT_ENFORCEMENT_ENABLED",
    "DATA_EXPORT_ENABLED",
    "CORS_ALLOWED_ORIGINS",
}


def _keys(path: str) -> set[str]:
    out = set()
    for raw in Path(path).read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        out.add(line.split("=", 1)[0].strip())
    return out


def _run_readiness(extra: dict[str, str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(extra)
    return subprocess.run([sys.executable, "scripts/preprod_readiness_check.py"], capture_output=True, text=True, check=False, env=env)


def _run_smoke(extra: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(extra)
    return subprocess.run([sys.executable, "scripts/smoke_test_private_beta.py", *args], capture_output=True, text=True, check=False, env=env)


def test_env_example_contains_required_keys():
    for file_name in (".env.example", ".env.production.example"):
        keys = _keys(file_name)
        missing = REQUIRED_ENV_KEYS - keys
        assert not missing, f"{file_name} missing: {sorted(missing)}"


def test_production_requires_database_url_when_postgres_enabled():
    result = _run_readiness({"ENVIRONMENT": "production", "USE_POSTGRESQL": "true", "DATABASE_URL": "", "USE_FILESYSTEM_FALLBACK": "false"})
    assert result.returncode != 0
    assert "[FAIL] DATABASE_URL when postgres" in result.stdout


def test_production_disallows_silent_filesystem_fallback_for_sensitive_state():
    result = _run_readiness({"ENVIRONMENT": "production", "USE_POSTGRESQL": "true", "DATABASE_URL": "postgresql://x", "USE_FILESYSTEM_FALLBACK": "true"})
    assert result.returncode != 0
    assert "[FAIL] No filesystem fallback in production" in result.stdout


def test_streamlit_cloud_docs_exist():
    assert Path("docs/streamlit_cloud_deployment.md").exists()


def test_smoke_script_dry_run_succeeds():
    result = _run_smoke({"ENVIRONMENT": "development"}, "--dry-run")
    assert result.returncode == 0
    assert "dry-run" in result.stdout.lower()
    assert "manual checklist" in result.stdout.lower()


def test_smoke_script_http_mode_fails_for_unreachable_base_url():
    result = _run_smoke({}, "--base-url", "http://127.0.0.1:9")
    assert result.returncode != 0
    assert "endpoint unreachable" in result.stdout.lower() or "no safe health endpoints" in result.stdout.lower()


def test_smoke_manual_checklist_has_core_flows():
    result = _run_smoke({}, "--manual-checklist")
    assert result.returncode == 0
    output = result.stdout.lower()
    for phrase in [
        "admin bootstrap",
        "therapist onboarding/login",
        "client creation",
        "mood entry",
        "homework assignment",
        "report/chat",
        "self export",
        "audit/log verification",
        "tenant/subscription sanity",
    ]:
        assert phrase in output


def test_no_real_secrets_in_env_examples():
    forbidden_fragments = ["sk-", "AKIA", "-----BEGIN", "prod_secret", "real_secret"]
    for file_name in (".env.example", ".env.production.example"):
        text = Path(file_name).read_text()
        for marker in forbidden_fragments:
            assert marker not in text


def test_smoke_script_has_no_delete_or_mutation_calls():
    text = Path("scripts/smoke_test_private_beta.py").read_text().lower()
    for forbidden in ["method=\"delete\"", "method='delete'", "/delete", "hard-delete", "drop table", "truncate"]:
        assert forbidden not in text


def test_readiness_check_storage_persistence_requirements():
    result = _run_readiness({
        "ENVIRONMENT": "production",
        "SECRET_KEY": "x" * 40,
        "USE_POSTGRESQL": "true",
        "DATABASE_URL": "postgresql://x",
        "USE_FILESYSTEM_FALLBACK": "false",
        "AUTH_SECURITY_STATE_PATH": "",
        "AUDIT_LOG_PATH": "",
        "DATA_RIGHTS_STORAGE_PATH": "",
        "PRIVACY_POLICY_VERSION": "2026-01",
        "TERMS_VERSION": "2026-01",
        "CONSENT_ENFORCEMENT_ENABLED": "true",
        "DATA_EXPORT_ENABLED": "true",
        "ADMIN_BOOTSTRAP_MODE": "disabled",
        "ADMIN_BOOTSTRAP_SECRET": "y" * 40,
        "CORS_ALLOWED_ORIGINS": "https://example.com",
    })
    assert result.returncode != 0
    assert "[FAIL] Auth security persistence configured" in result.stdout
    assert "[FAIL] Audit persistence configured" in result.stdout
    assert "[FAIL] Data-rights persistence configured" in result.stdout
