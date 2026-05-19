from __future__ import annotations

import argparse
import os
import secrets
import sys

from database.audit_log import audit_log_event
from services import auth_service


def _is_strong_secret(value: str) -> bool:
    if len(value) < 32:
        return False
    has_alpha = any(c.isalpha() for c in value)
    has_digit = any(c.isdigit() for c in value)
    return has_alpha and has_digit


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="One-time admin bootstrap")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--bootstrap-secret", required=True)
    args = parser.parse_args(argv)

    expected = os.getenv("ADMIN_BOOTSTRAP_SECRET", "").strip()
    if not expected:
        print("ADMIN_BOOTSTRAP_SECRET is not configured")
        return 1
    if not _is_strong_secret(expected):
        print("ADMIN_BOOTSTRAP_SECRET is not strong enough")
        return 1
    if not secrets.compare_digest(args.bootstrap_secret, expected):
        print("Invalid bootstrap secret")
        return 1

    username = auth_service.normalize_username(args.username)
    if not username:
        print("Invalid username")
        return 1

    if auth_service.user_exists(username):
        md = auth_service.load_user_metadata(username)
        md["role"] = "admin"
        auth_service.save_user_metadata(username, md)
    else:
        auth_service.create_user(username, args.password, role="admin", subscription_status="active")

    audit_log_event(
        "admin_bootstrap_created",
        actor_username=username,
        target_username=username,
        metadata={"method": "cli", "one_time": True},
        severity="critical",
    )
    print(f"Admin bootstrap completed for {username}")
    return 0


if __name__ == "__main__":
    sys.exit(run())
