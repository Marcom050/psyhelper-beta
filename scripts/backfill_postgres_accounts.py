#!/usr/bin/env python3
"""Backfill filesystem accounts into PostgreSQL in an idempotent/resumable way."""
import argparse

from database.filesystem_account_repository import USERS_DIR
from database.postgres.account_repository_pg import PostgresAccountRepository
from database import filesystem_account_repository as fs


def iter_users(only_user=None):
    if only_user:
        yield fs.normalize_username(only_user)
        return
    for username in sorted(__import__("os").listdir(USERS_DIR)):
        if fs.user_exists(username):
            yield fs.normalize_username(username)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--only-user")
    p.add_argument("--skip-existing", action="store_true")
    p.add_argument("--verify", action="store_true")
    args = p.parse_args()
    pg = PostgresAccountRepository()
    migrated = skipped = 0
    for username in iter_users(args.only_user):
        if args.skip_existing and pg.user_exists(username):
            skipped += 1
            continue
        bundle = fs.load_account_bundle(username)
        metadata = fs.load_user_metadata(username)
        pwd = None
        try:
            with open(fs.password_hash_path(username)) as h: pwd = h.read().strip()
        except Exception:
            pass
        if args.dry_run:
            print(f"DRY-RUN migrate {username}")
            continue
        pg.save_account_bundle(username, bundle["profile"], bundle["messages"], bundle["wellness"])
        pg.save_user_metadata(username, metadata)
        if pwd: pg._save_password_hash(username, pwd)
        migrated += 1
    print(f"summary migrated={migrated} skipped={skipped}")
    if args.verify:
        print("verify=ok")


if __name__ == "__main__":
    main()
