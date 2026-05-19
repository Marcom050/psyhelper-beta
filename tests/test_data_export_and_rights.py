import os
import pytest
from starlette.testclient import TestClient

from api.app import app
from database.audit_log import get_events
from services import auth_service, data_rights_service


def _h(c, u, p="secret"):
    t = c.post('/auth/login', json={"username": u, "password": p}).json()["access_token"]
    return {"Authorization": f"Bearer {t}"}


def test_streamlit_subscription_datetime_fix_still_green():
    from services.subscription_service import normalize_datetime_utc
    assert normalize_datetime_utc("2026-05-19T10:00:00") is not None
    assert normalize_datetime_utc("2026-05-19T10:00:00+02:00").tzinfo is not None
    assert normalize_datetime_utc("bad") is None


def test_admin_data_rights_export_flow(tmp_path, monkeypatch):
    monkeypatch.setattr('database.filesystem_account_repository.USERS_DIR', str(tmp_path/'users'))
    monkeypatch.setattr('database.account_repository.USERS_DIR', str(tmp_path/'users'))
    monkeypatch.setattr(data_rights_service, 'REQUESTS_PATH', str(tmp_path/'requests.json'))
    monkeypatch.setattr('database.audit_log.AUDIT_LOG_PATH', str(tmp_path/'audit.log'))

    c = TestClient(app, raise_server_exceptions=False)
    assert c.post('/auth/signup', json={"username":"th","password":"secret","role":"therapist","subscription_status":"active"}).status_code == 200
    auth_service.create_user('admin','secret',role='client')
    md = auth_service.load_user_metadata('admin')
    md['role'] = 'admin'
    auth_service.save_user_metadata('admin', md)
    th = _h(c,'th')
    assert c.post('/therapists/me/clients', headers=th, json={"username":"c1","password":"secret","profile":{"nome":"C1"}}).status_code == 200

    ch = _h(c,'c1')
    r = c.get('/v1/me/export', headers=ch)
    assert r.status_code == 200
    ex = r.json()['data']['export']
    assert ex['tenant_id'] == 'th'
    assert 'password_hash' not in str(ex)

    req = data_rights_service.create_request('export','c1','th','c1')
    updated = data_rights_service.update_request_status(req['request_id'], 'processing')
    exported = __import__('services.data_export_service', fromlist=['generate_user_export']).generate_user_export(
        actor_username='admin', subject_username='c1', tenant_id='th', request_id=req['request_id']
    )
    completed = data_rights_service.update_request_status(req['request_id'], 'completed', {'export_generated_at': exported['generated_at']})
    assert completed['status'] == 'completed'
    assert completed['metadata'].get('export_generated_at')

    assert exported['subject_username'] == 'c1'


def test_delete_request_status_transitions(tmp_path, monkeypatch):
    monkeypatch.setattr(data_rights_service, 'REQUESTS_PATH', str(tmp_path/'requests.json'))
    item = data_rights_service.create_request('delete','c1','t1','admin')
    assert data_rights_service.update_request_status(item['request_id'], 'processing')['status'] == 'processing'
    assert data_rights_service.update_request_status(item['request_id'], 'completed')['status'] == 'completed'


def test_delete_request_invalid_transition_denied(tmp_path, monkeypatch):
    monkeypatch.setattr(data_rights_service, 'REQUESTS_PATH', str(tmp_path/'requests.json'))
    item = data_rights_service.create_request('delete','c1','t1','admin')
    data_rights_service.update_request_status(item['request_id'], 'rejected')
    with pytest.raises(ValueError):
        data_rights_service.update_request_status(item['request_id'], 'completed')


def test_security_headers_present():
    c = TestClient(app, raise_server_exceptions=False)
    r = c.get('/health')
    assert r.headers['X-Content-Type-Options'] == 'nosniff'
    assert r.headers['X-Frame-Options'] == 'DENY'


def test_readiness_check_privacy_export_config():
    from scripts.preprod_readiness_check import run
    os.environ['ENVIRONMENT'] = 'production'
    os.environ['SECRET_KEY'] = 'x'*32
    os.environ['USE_FILESYSTEM_FALLBACK'] = '1'
    os.environ['AUTH_SECURITY_STATE_PATH'] = '/tmp/a'
    os.environ['AUDIT_LOG_PATH'] = '/tmp/b'
    os.environ['PRIVACY_POLICY_VERSION'] = 'v1'
    os.environ['TERMS_VERSION'] = 'v1'
    os.environ['DATA_EXPORT_ENABLED'] = 'true'
    os.environ['CORS_ALLOWED_ORIGINS'] = 'https://example.com'
    os.environ['DEBUG'] = '0'
    os.environ['TESTING'] = '0'
    os.environ['ADMIN_BOOTSTRAP_SECRET'] = 'A'*31 + '1'
    assert run() == 0
