from __future__ import annotations
import logging, os
from dataclasses import dataclass
logger = logging.getLogger(__name__)

def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in {"1","true","yes","on"}

@dataclass(frozen=True)
class Settings:
    environment:str; secret_key:str; use_postgresql:bool; database_url:str; strict_production_mode:bool; use_filesystem_fallback:bool
    db_connect_timeout_sec:float; db_statement_timeout_ms:int
    access_token_expire_minutes:int; refresh_token_expire_days:int; token_issuer:str
    login_rate_limit_attempts:int; login_rate_limit_window_sec:int; login_lockout_sec:int
    consent_version:str; privacy_policy_version:str; terms_version:str; consent_enforcement_enabled:bool; data_export_enabled:bool; beta_trial_days:int
    @property
    def is_production(self)->bool: return self.environment=="production"

_DEVELOPMENT_SECRET="psyhelper-beta-dev-secret-change-me"

def load_settings()->Settings:
    env=os.getenv("ENVIRONMENT","development").strip().lower()
    if env not in {"development","staging","production"}: raise RuntimeError("ENVIRONMENT must be development|staging|production")
    strict=_env_bool("STRICT_PRODUCTION_MODE", env=="production")
    secret_key=os.getenv("SECRET_KEY","")
    if env=="production" and len(secret_key)<32: raise RuntimeError("SECRET_KEY must be set and >=32 chars in production")
    if not secret_key:
        secret_key=_DEVELOPMENT_SECRET
        if env!="development": logger.warning("Unsafe config: using development SECRET_KEY outside development")
    use_postgresql=_env_bool("USE_POSTGRESQL",False); database_url=os.getenv("DATABASE_URL","").strip(); use_fs=_env_bool("USE_FILESYSTEM_FALLBACK",True)
    if env=="production" and not use_postgresql: raise RuntimeError("USE_POSTGRESQL=true is required in production")
    if strict and env=="production" and use_fs: raise RuntimeError("USE_FILESYSTEM_FALLBACK must be false in strict production mode")
    if use_postgresql and not database_url: raise RuntimeError("DATABASE_URL is required when USE_POSTGRESQL=true")
    return Settings(env, secret_key, use_postgresql, database_url, strict, use_fs, float(os.getenv("DB_CONNECT_TIMEOUT_SEC","5")), int(os.getenv("DB_STATEMENT_TIMEOUT_MS","5000")), int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES","15")), int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS","7")), os.getenv("TOKEN_ISSUER","psyhelper-beta"), int(os.getenv("LOGIN_RATE_LIMIT_ATTEMPTS","8")), int(os.getenv("LOGIN_RATE_LIMIT_WINDOW_SEC","60")), int(os.getenv("LOGIN_LOCKOUT_SEC","300")), os.getenv("CONSENT_VERSION","v1"), os.getenv("PRIVACY_POLICY_VERSION",""), os.getenv("TERMS_VERSION",""), _env_bool("CONSENT_ENFORCEMENT_ENABLED", True), _env_bool("DATA_EXPORT_ENABLED", True), int(os.getenv("BETA_TRIAL_DAYS","14")))

SETTINGS=load_settings()
