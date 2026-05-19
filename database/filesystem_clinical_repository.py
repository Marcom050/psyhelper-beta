import os
from datetime import datetime, timezone

from database.filesystem_account_repository import normalize_username
from database.interfaces.clinical_repository_interface import ClinicalRepository
from database.json_storage import atomic_write_json, load_json_file

BASE = os.path.expanduser('~/psyhelper_data')
CLINICAL_PATH = os.path.join(BASE, 'clinical_records.json')
SNAPSHOT_PATH = os.path.join(BASE, 'analytics_snapshots.json')


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _load(path, default):
    try:
        return load_json_file(path)
    except Exception:
        return default


class FilesystemClinicalRepository(ClinicalRepository):
    def _tenant_required(self, tenant_id):
        tenant_id = normalize_username(tenant_id or "")
        if not tenant_id:
            raise ValueError('tenant_id is required')
        return tenant_id

    def create_clinical_record(self, **kw):
        tenant_id = self._tenant_required(kw['tenant_id'])
        records = _load(CLINICAL_PATH, [])
        now = _now()
        rec = {**kw, 'tenant_id': tenant_id, 'created_at': now, 'updated_at': now, 'id': f"{tenant_id}:{kw['entity_type']}:{kw['entity_id']}"}
        records = [r for r in records if r.get('id') != rec['id']] + [rec]
        atomic_write_json(CLINICAL_PATH, records)
        return rec

    def update_clinical_record_status(self, **kw):
        tenant_id = self._tenant_required(kw['tenant_id'])
        records = _load(CLINICAL_PATH, [])
        for r in records:
            if r.get('tenant_id') == tenant_id and r.get('entity_type') == kw['entity_type'] and str(r.get('entity_id')) == str(kw['entity_id']):
                r['lifecycle_status'] = kw['lifecycle_status']
                r['updated_at'] = _now()
        atomic_write_json(CLINICAL_PATH, records)

    def list_clinical_records(self, **kw):
        tenant_id = self._tenant_required(kw['tenant_id'])
        records = [r for r in _load(CLINICAL_PATH, []) if r.get('tenant_id') == tenant_id]
        for f in ('entity_type', 'owner_username', 'subject_username', 'lifecycle_status'):
            if kw.get(f) is not None:
                records = [r for r in records if r.get(f) == kw[f]]
        return records

    def upsert_analytics_snapshot(self, **kw):
        tenant_id = self._tenant_required(kw['tenant_id'])
        rows = _load(SNAPSHOT_PATH, [])
        key = f"{tenant_id}:{kw['therapist_username']}:{kw['snapshot_date']}"
        now = _now()
        row = {'id': key, 'tenant_id': tenant_id, 'therapist_username': kw['therapist_username'], 'snapshot_date': kw['snapshot_date'], 'metrics': kw['metrics'], 'updated_at': now, 'created_at': now}
        rows = [r for r in rows if r.get('id') != key] + [row]
        atomic_write_json(SNAPSHOT_PATH, rows)
        return row

    def get_analytics_snapshot(self, **kw):
        tenant_id = self._tenant_required(kw['tenant_id'])
        key = f"{tenant_id}:{kw['therapist_username']}:{kw['snapshot_date']}"
        for r in _load(SNAPSHOT_PATH, []):
            if r.get('id') == key:
                return r
        return None
