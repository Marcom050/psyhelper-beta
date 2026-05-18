"""Database backend feature flags and configuration."""

import os


def _env_flag(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


USE_POSTGRESQL = _env_flag("USE_POSTGRESQL", False)
DATABASE_URL = os.getenv("DATABASE_URL", "")
