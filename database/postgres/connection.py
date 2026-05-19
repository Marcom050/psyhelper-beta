"""Minimal PostgreSQL connection-pool support for JSONB repositories."""

from contextlib import contextmanager
import time

from database import config
from core.settings import SETTINGS

_POOL = None

SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS accounts (
        username TEXT PRIMARY KEY,
        profile JSONB NOT NULL DEFAULT '{}'::jsonb,
        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
        password_hash TEXT
    )
    """,
    "ALTER TABLE accounts ADD COLUMN IF NOT EXISTS password_hash TEXT",
    "CREATE INDEX IF NOT EXISTS idx_accounts_metadata_tenant_id ON accounts ((metadata->>'tenant_id'))",
    "CREATE INDEX IF NOT EXISTS idx_accounts_metadata_role ON accounts ((metadata->>'role'))",
    "CREATE INDEX IF NOT EXISTS idx_accounts_metadata_therapist_username ON accounts ((metadata->>'therapist_username'))",
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
    """
    CREATE TABLE IF NOT EXISTS clinical_records (
        id TEXT PRIMARY KEY,
        entity_type TEXT NOT NULL,
        tenant_id TEXT NOT NULL,
        owner_username TEXT NOT NULL,
        lifecycle_status TEXT NOT NULL,
        payload JSONB NOT NULL DEFAULT '{}'::jsonb,
        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_clinical_records_tenant_entity ON clinical_records (tenant_id, entity_type)",
    "CREATE INDEX IF NOT EXISTS idx_clinical_records_tenant_status ON clinical_records (tenant_id, lifecycle_status)",
    "CREATE INDEX IF NOT EXISTS idx_clinical_records_owner ON clinical_records (owner_username)",
    "CREATE INDEX IF NOT EXISTS idx_clinical_records_created_at ON clinical_records (created_at)",
    """
    CREATE TABLE IF NOT EXISTS analytics_snapshots (
        id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        therapist_username TEXT NOT NULL,
        snapshot_date DATE NOT NULL,
        metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_analytics_snapshots_tenant_date ON analytics_snapshots (tenant_id, snapshot_date)",
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
        _POOL = ConnectionPool(conninfo=get_database_url(), min_size=1, max_size=10, open=True, kwargs={"connect_timeout": SETTINGS.db_connect_timeout_sec})
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


def db_healthcheck() -> float:
    start = time.perf_counter()
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    return round((time.perf_counter() - start) * 1000, 2)
