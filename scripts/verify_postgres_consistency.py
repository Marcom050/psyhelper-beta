#!/usr/bin/env python3
"""Verify PostgreSQL consistency against filesystem source."""
import os

from database.filesystem_account_repository import USERS_DIR
from database.postgres.account_repository_pg import PostgresAccountRepository
from database import filesystem_account_repository as fs


def main():
    pg = PostgresAccountRepository()
    errors = 0
    warnings = 0
    for username in sorted(os.listdir(USERS_DIR)):
        if not fs.user_exists(username):
            continue
        username = fs.normalize_username(username)
        if not pg.user_exists(username):
            print(f"ERROR missing_user {username}")
            errors += 1
            continue
        md = pg.load_user_metadata(username)
        if not md.get("tenant_id"):
            print(f"WARNING tenant_missing {username}")
            warnings += 1
        if md.get("role") == "client" and md.get("therapist_username") and md.get("tenant_id") != md.get("therapist_username"):
            print(f"ERROR tenant_mismatch {username}")
            errors += 1
    print(f"summary warnings={warnings} errors={errors}")


if __name__ == "__main__":
    main()
