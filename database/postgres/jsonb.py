"""Optional psycopg JSONB adapter helpers."""

try:
    from psycopg.types.json import Jsonb as _Jsonb
except ImportError:  # pragma: no cover - used only when psycopg is absent in local tests.
    _Jsonb = None


def jsonb(value):
    """Wrap ``value`` for psycopg JSONB binding when psycopg is installed."""
    if _Jsonb is None:
        return value
    return _Jsonb(value)
