from __future__ import annotations

import os

import pytest

import database.audit_log as audit_log
import database.auth_security_repository as auth_security_repository
import database.config as db_config


@pytest.fixture(autouse=True)
def _restore_global_state():
    """Prevent state leakage across tests that mutate module globals/env-backed paths."""
    original = {
        "USE_POSTGRESQL": db_config.USE_POSTGRESQL,
        "DATABASE_URL": db_config.DATABASE_URL,
        "USE_FILESYSTEM_FALLBACK": db_config.USE_FILESYSTEM_FALLBACK,
        "STRICT_PRODUCTION_MODE": db_config.STRICT_PRODUCTION_MODE,
        "AUDIT_LOG_PATH": audit_log.AUDIT_LOG_PATH,
        "AUTH_SECURITY_STATE_PATH": auth_security_repository._SECURITY_PATH,
    }
    yield
    db_config.USE_POSTGRESQL = original["USE_POSTGRESQL"]
    db_config.DATABASE_URL = original["DATABASE_URL"]
    db_config.USE_FILESYSTEM_FALLBACK = original["USE_FILESYSTEM_FALLBACK"]
    db_config.STRICT_PRODUCTION_MODE = original["STRICT_PRODUCTION_MODE"]
    audit_log.AUDIT_LOG_PATH = original["AUDIT_LOG_PATH"]
    auth_security_repository._SECURITY_PATH = original["AUTH_SECURITY_STATE_PATH"]


@pytest.fixture(autouse=True)
def _cleanup_test_fs_paths():
    """Ensure env-overridden file paths are not leaked between tests."""
    original_audit = os.getenv("AUDIT_LOG_PATH")
    original_security = os.getenv("AUTH_SECURITY_STATE_PATH")
    yield
    if original_audit is None:
        os.environ.pop("AUDIT_LOG_PATH", None)
    if original_security is None:
        os.environ.pop("AUTH_SECURITY_STATE_PATH", None)
