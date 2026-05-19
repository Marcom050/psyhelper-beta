import os

from core.settings import SETTINGS
from services import auth_service, privacy_service, data_rights_service


def test_consent_required_for_active_client(tmp_path, monkeypatch):
    monkeypatch.setattr('database.filesystem_account_repository.USERS_DIR', str(tmp_path / 'users'))
    auth_service.create_user('t1','pw',role='therapist')
    auth_service.create_user('c1','pw',role='client',therapist_username='t1')
    md = auth_service.load_user_metadata('c1')
    assert not privacy_service.has_valid_consent(md)


def test_therapist_onboarding_records_consent(tmp_path, monkeypatch):
    monkeypatch.setattr('database.filesystem_account_repository.USERS_DIR', str(tmp_path / 'users'))
    auth_service.create_user('th','pw',role='therapist')
    md = auth_service.load_user_metadata('th')
    md = privacy_service.apply_consent(md, actor='th', scope='therapist_onboarding', consent_version=SETTINGS.consent_version, privacy_policy_version='v1', terms_version='v1')
    assert md['consent_status'] == 'accepted'


def test_client_creation_records_consent(tmp_path, monkeypatch):
    monkeypatch.setattr('database.filesystem_account_repository.USERS_DIR', str(tmp_path / 'users'))
    auth_service.create_user('th','pw',role='therapist')
    auth_service.create_client_account('th','c2','pw','Client 2')
    md = privacy_service.apply_consent(auth_service.load_user_metadata('c2'), actor='th', scope='client_onboarding', consent_version='v1', privacy_policy_version='v1', terms_version='v1')
    assert md['consent_scope'] == 'client_onboarding'


def test_data_deletion_request_workflow(tmp_path, monkeypatch):
    monkeypatch.setattr(data_rights_service, 'REQUESTS_PATH', str(tmp_path / 'requests.json'))
    item = data_rights_service.create_request('delete','c1','t1','admin')
    updated = data_rights_service.update_request_status(item['request_id'],'processing')
    assert updated['status'] == 'processing'
