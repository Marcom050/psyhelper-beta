from __future__ import annotations

import os
import subprocess
import sys


def _run(env: dict[str, str]):
    merged = os.environ.copy()
    merged.update(env)
    return subprocess.run(
        [sys.executable, "scripts/preprod_readiness_check.py"],
        capture_output=True,
        text=True,
        env=merged,
        check=False,
    )


def test_readiness_allows_development_defaults():
    result = _run({"ENVIRONMENT": "development"})
    assert result.returncode == 0
    assert "[PASS] ENVIRONMENT valid" in result.stdout


def test_readiness_fails_insecure_production_config():
    result = _run(
        {
            "ENVIRONMENT": "production",
            "SECRET_KEY": "short",
            "USE_POSTGRESQL": "true",
            "USE_FILESYSTEM_FALLBACK": "false",
            "DATABASE_URL": "",
            "DEBUG": "true",
            "AUTH_SECURITY_STATE_PATH": "",
            "AUDIT_LOG_PATH": "",
            "CORS_ALLOWED_ORIGINS": "*",
        }
    )
    assert result.returncode != 0
    assert "[FAIL] SECRET_KEY set for production" in result.stdout
    assert "[FAIL] DATABASE_URL when postgres" in result.stdout
