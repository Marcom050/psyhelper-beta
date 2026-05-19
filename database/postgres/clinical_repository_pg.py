from database.interfaces.clinical_repository_interface import ClinicalRepository
from database.postgres.connection import connection, initialize_schema
from database.postgres.jsonb import jsonb


class PostgresClinicalRepository(ClinicalRepository):
    def __init__(self):
        initialize_schema()

    def _tenant_required(self, tenant_id):
        if not tenant_id:
            raise ValueError('tenant_id is required')
        return tenant_id

    def create_clinical_record(self, **kw):
        tid = self._tenant_required(kw['tenant_id'])
        rid = f"{tid}:{kw['entity_type']}:{kw['entity_id']}"
        with connection() as conn:
            with conn.cursor() as c:
                c.execute("""
                INSERT INTO clinical_records (id, entity_type, tenant_id, owner_username, lifecycle_status, payload, metadata)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (id) DO UPDATE SET lifecycle_status=EXCLUDED.lifecycle_status,payload=EXCLUDED.payload,metadata=EXCLUDED.metadata,updated_at=NOW()
                """, (rid, kw['entity_type'], tid, kw['owner_username'], kw['lifecycle_status'], jsonb({**kw['payload'], 'subject_username': kw.get('subject_username')}), jsonb(kw['metadata'])))
            conn.commit()
        return rid

    def update_clinical_record_status(self, **kw):
        tid = self._tenant_required(kw['tenant_id'])
        rid = f"{tid}:{kw['entity_type']}:{kw['entity_id']}"
        with connection() as conn:
            with conn.cursor() as c:
                c.execute("UPDATE clinical_records SET lifecycle_status=%s, updated_at=NOW() WHERE id=%s AND tenant_id=%s", (kw['lifecycle_status'], rid, tid))
            conn.commit()

    def list_clinical_records(self, **kw):
        tid = self._tenant_required(kw['tenant_id'])
        query = "SELECT id,entity_type,tenant_id,owner_username,lifecycle_status,payload,metadata,created_at,updated_at FROM clinical_records WHERE tenant_id=%s"
        params = [tid]
        if kw.get('entity_type'):
            query += " AND entity_type=%s"; params.append(kw['entity_type'])
        if kw.get('owner_username'):
            query += " AND owner_username=%s"; params.append(kw['owner_username'])
        if kw.get('lifecycle_status'):
            query += " AND lifecycle_status=%s"; params.append(kw['lifecycle_status'])
        with connection() as conn:
            with conn.cursor() as c:
                c.execute(query, tuple(params))
                rows = c.fetchall()
        return [{'id': r[0], 'entity_type': r[1], 'tenant_id': r[2], 'owner_username': r[3], 'lifecycle_status': r[4], 'payload': r[5], 'metadata': r[6], 'created_at': str(r[7]), 'updated_at': str(r[8]), 'subject_username': (r[5] or {}).get('subject_username')} for r in rows]

    def upsert_analytics_snapshot(self, **kw):
        tid = self._tenant_required(kw['tenant_id'])
        sid = f"{tid}:{kw['therapist_username']}:{kw['snapshot_date']}"
        with connection() as conn:
            with conn.cursor() as c:
                c.execute("""
                INSERT INTO analytics_snapshots (id, tenant_id, therapist_username, snapshot_date, metrics)
                VALUES (%s,%s,%s,%s,%s)
                ON CONFLICT (id) DO UPDATE SET metrics=EXCLUDED.metrics,updated_at=NOW()
                """, (sid, tid, kw['therapist_username'], kw['snapshot_date'], jsonb(kw['metrics'])))
            conn.commit()

    def get_analytics_snapshot(self, **kw):
        tid = self._tenant_required(kw['tenant_id'])
        sid = f"{tid}:{kw['therapist_username']}:{kw['snapshot_date']}"
        with connection() as conn:
            with conn.cursor() as c:
                c.execute("SELECT id,tenant_id,therapist_username,snapshot_date,metrics,created_at,updated_at FROM analytics_snapshots WHERE id=%s AND tenant_id=%s", (sid, tid))
                r = c.fetchone()
        if not r:
            return None
        return {'id': r[0], 'tenant_id': r[1], 'therapist_username': r[2], 'snapshot_date': str(r[3]), 'metrics': r[4], 'created_at': str(r[5]), 'updated_at': str(r[6])}
