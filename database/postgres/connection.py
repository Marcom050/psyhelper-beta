"""Minimal PostgreSQL connection-pool support for JSONB repositories."""

from contextlib import contextmanager

from database import config

_POOL = None

SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS accounts (
        username TEXT PRIMARY KEY,
        profile JSONB NOT NULL DEFAULT '{}'::jsonb,
        metadata JSONB NOT NULL DEFAULT '{}'::jsonb
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS messages (
        username TEXT PRIMARY KEY,
        messages JSONB NOT NULL DEFAULT '[]'::jsonb
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS wellness (
        username TEXT PRIMARY KEY,
        wellness JSONB NOT NULL DEFAULT '{}'::jsonb
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS notes (
        username TEXT PRIMARY KEY,
        notes JSONB NOT NULL DEFAULT '{}'::jsonb
    )
    """,
)


def get_database_url():
    """Return the configured PostgreSQL connection string."""
    if not config.DATABASE_URL:
        raise RuntimeError("DATABASE_URL must be set when USE_POSTGRESQL is enabled")
    return config.DATABASE_URL


def get_pool():
    """Create and cache a small psycopg3 connection pool."""
    global _POOL
    if _POOL is None:
        try:
            from psycopg_pool import ConnectionPool
        except ImportError as exc:
            raise RuntimeError("Install psycopg_pool/psycopg to enable PostgreSQL persistence") from exc
        _POOL = ConnectionPool(conninfo=get_database_url(), min_size=1, max_size=10, open=True)
    return _POOL


@contextmanager
def connection():
    """Yield a pooled PostgreSQL connection."""
    with get_pool().connection() as conn:
        yield conn


def initialize_schema():
    """Create the minimal JSONB tables without destructive migrations."""
    with connection() as conn:
        with conn.cursor() as cursor:
            for statement in SCHEMA_STATEMENTS:
                cursor.execute(statement)
        conn.commit()


def reset_pool():
    """Close and clear the cached pool; useful for tests."""
    global _POOL
    if _POOL is not None:
        _POOL.close()
        _POOL = None
