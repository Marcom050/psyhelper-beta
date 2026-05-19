import os
from core.settings import load_settings


def test_settings_dev_defaults(monkeypatch):
    monkeypatch.delenv('SECRET_KEY', raising=False)
    monkeypatch.setenv('ENVIRONMENT','development')
    s=load_settings()
    assert s.secret_key


def test_settings_production_requires_secret(monkeypatch):
    monkeypatch.setenv('ENVIRONMENT','production')
    monkeypatch.delenv('SECRET_KEY', raising=False)
    monkeypatch.setenv('USE_POSTGRESQL','true')
    monkeypatch.setenv('DATABASE_URL','postgresql://x')
    monkeypatch.setenv('USE_FILESYSTEM_FALLBACK','false')
    try:
        load_settings()
        assert False
    except RuntimeError:
        assert True
