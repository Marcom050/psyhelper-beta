from unittest.mock import patch

from services import analytics_service
from database.filesystem_clinical_repository import FilesystemClinicalRepository


def test_tenant_required_for_clinical_record_query():
    repo = FilesystemClinicalRepository()
    try:
        repo.list_clinical_records(tenant_id=None)
        assert False
    except ValueError:
        assert True


def test_analytics_prefers_snapshot():
    with patch('services.analytics_service.get_clinical_repository') as gcr, patch('services.analytics_service.auth_service.load_user_metadata', return_value={'tenant_id':'t1'}), patch('services.analytics_service.auth_service.resolve_tenant_id', return_value='t1'):
        gcr.return_value.get_analytics_snapshot.return_value = {'metrics': {'active_clients': 99}}
        out = analytics_service.therapist_overview('therapist_a')
        assert out['active_clients'] == 99


def test_archived_client_excluded_from_analytics():
    with patch('services.analytics_service.auth_service.get_clients_for_tenant', return_value=[{'username':'c1','metadata':{'lifecycle_status':'archived'}}, {'username':'c2','metadata':{}}]), patch('services.analytics_service.auth_service.load_account_bundle', return_value={'wellness':{'mood_entries':[],'homework_assignments':[],'homework_submissions':[]}}):
        out = analytics_service.therapist_overview('t', allow_snapshot_fallback=False)
        assert out['active_clients'] == 1
        assert out['pending_homework_count'] == 0
