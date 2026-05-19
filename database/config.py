"""Database backend feature flags and configuration."""

from core.settings import SETTINGS

USE_POSTGRESQL = SETTINGS.use_postgresql
DATABASE_URL = SETTINGS.database_url
USE_FILESYSTEM_FALLBACK = SETTINGS.use_filesystem_fallback
STRICT_PRODUCTION_MODE = SETTINGS.strict_production_mode
