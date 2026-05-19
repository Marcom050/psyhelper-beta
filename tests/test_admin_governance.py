import os
from starlette.testclient import TestClient

from api.app import app
from services import auth_service, data_rights_service
from scripts import admin_bootstrap
from database.audit_log import get_events


def _set_users_dir(monkeypatch, path):
    monkeypatch.setattr('database.filesystem_account_repository.USERS_DIR', str(path))
    monkeypatch.setattr('database.account_repository.USERS_DIR', str(path))


def _h(c, u, p="secret"):
    t = c.post('/auth/login', json={"username": u, "password": p}).json()["access_token"]
    return {"Authorization": f"Bearer {t}"}


def test_cannot_create_admin_implicitly(tmp_path, monkeypatch):
    _set_users_dir(monkeypatch, tmp_path/'users')
    c = TestClient(app, raise_server_exceptions=False)
    r = c.post('/auth/signup', json={"username":"a","password":"secret","role":"admin"})
    assert r.status_code == 422


def test_admin_bootstrap_requires_strong_secret(tmp_path, monkeypatch):
    monkeypatch.setenv('ADMIN_BOOTSTRAP_SECRET', 'weak')
    _set_users_dir(monkeypatch, tmp_path/'users')
    assert admin_bootstrap.run(['--username','admin','--password','secret','--bootstrap-secret','weak']) == 1


def test_admin_bootstrap_creates_admin_with_audit(tmp_path, monkeypatch):
    monkeypatch.setenv('ADMIN_BOOTSTRAP_SECRET', 'A'*31 + '1')
    _set_users_dir(monkeypatch, tmp_path/'users')
    monkeypatch.setattr('database.audit_log.AUDIT_LOG_PATH', str(tmp_path/'audit.json'))
    assert admin_bootstrap.run(['--username','admin','--password','secret','--bootstrap-secret','A'*31 + '1']) == 0
    assert auth_service.load_user_metadata('admin')['role'] == 'admin'
    assert any(e['event_type']=='admin_bootstrap_created' for e in get_events(limit=50, offset=0))


def test_admin_promotion_audited_high_severity(tmp_path, monkeypatch):
    _set_users_dir(monkeypatch, tmp_path/'users')
    monkeypatch.setattr('database.audit_log.AUDIT_LOG_PATH', str(tmp_path/'audit.json'))
    c = TestClient(app, raise_server_exceptions=False)
    c.post('/auth/signup', json={"username":"root","password":"secret","role":"client"})
    md = auth_service.load_user_metadata('root'); md['role']='admin'; auth_service.save_user_metadata('root', md)
    c.post('/auth/signup', json={"username":"u1","password":"secret","role":"client"})
    r = c.patch('/admin/users/u1/role', headers=_h(c,'root'), json={"role":"admin"})
    assert r.status_code == 200
    evt = [e for e in get_events(limit=100, offset=0) if e['event_type']=='admin_role_changed'][0]
    assert evt['metadata']['severity'] == 'high'


def test_cannot_demote_last_admin_if_supported(tmp_path, monkeypatch):
    _set_users_dir(monkeypatch, tmp_path/'users')
    c = TestClient(app, raise_server_exceptions=False)
    c.post('/auth/signup', json={"username":"solo","password":"secret","role":"client"})
    md = auth_service.load_user_metadata('solo'); md['role']='admin'; auth_service.save_user_metadata('solo', md)
    r = c.patch('/admin/users/solo/role', headers=_h(c,'solo'), json={"role":"client"})
    assert r.status_code == 400


def test_admin_data_rights_export_e2e(tmp_path, monkeypatch):
    _set_users_dir(monkeypatch, tmp_path/'users')
    monkeypatch.setattr(data_rights_service, 'REQUESTS_PATH', str(tmp_path/'requests.json'))
    monkeypatch.setattr('database.audit_log.AUDIT_LOG_PATH', str(tmp_path/'audit.json'))
    c = TestClient(app, raise_server_exceptions=False)
    c.post('/auth/signup', json={"username":"th","password":"secret","role":"therapist","subscription_status":"active"})
    c.post('/auth/signup', json={"username":"root","password":"secret","role":"client"})
    md = auth_service.load_user_metadata('root'); md['role']='admin'; auth_service.save_user_metadata('root', md)
    c.post('/therapists/me/clients', headers=_h(c,'th'), json={"username":"c1","password":"secret","profile":{"nome":"C1"}})
    req = data_rights_service.create_request('export','c1','th','c1')
    resp = c.get(f"/admin/data-rights/requests/{req['request_id']}/export", headers=_h(c,'root'))
    assert resp.status_code == 200
    payload = resp.json()['data']
    assert payload['request']['status'] == 'completed'
    assert payload['export']['tenant_id'] == 'th'
    assert 'password' not in str(payload['export']).lower()
    assert any(e['event_type']=='admin_data_rights_export' for e in get_events(limit=100, offset=0))


def test_audit_storage_isolated_between_tests(tmp_path, monkeypatch):
    monkeypatch.setattr('database.audit_log.AUDIT_LOG_PATH', str(tmp_path/'audit.json'))
    from database.audit_log import log_event
    log_event('x', actor='a', payload={})
    assert len(get_events(limit=20, offset=0)) == 1


def test_readiness_admin_bootstrap_config_required_in_prod(monkeypatch):
    from scripts.preprod_readiness_check import run
    monkeypatch.setenv('ENVIRONMENT', 'production')
    monkeypatch.setenv('SECRET_KEY', 'x'*32)
    monkeypatch.setenv('USE_FILESYSTEM_FALLBACK', '1')
    monkeypatch.setenv('AUTH_SECURITY_STATE_PATH', '/tmp/a')
    monkeypatch.setenv('AUDIT_LOG_PATH', '/tmp/b')
    monkeypatch.setenv('PRIVACY_POLICY_VERSION', 'v1')
    monkeypatch.setenv('TERMS_VERSION', 'v1')
    monkeypatch.setenv('DATA_EXPORT_ENABLED', 'true')
    monkeypatch.setenv('CORS_ALLOWED_ORIGINS', 'https://example.com')
    monkeypatch.setenv('DEBUG', '0')
    monkeypatch.setenv('TESTING', '0')
    monkeypatch.delenv('ADMIN_BOOTSTRAP_SECRET', raising=False)
    assert run() == 1
