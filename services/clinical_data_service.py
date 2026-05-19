from datetime import date

from services import auth_service
from services.analytics_service import therapist_overview
from database.repository_factory import get_clinical_repository


def _tenant_for(username: str):
    md = auth_service.load_user_metadata(username)
    return auth_service.resolve_tenant_id(md, username)


def create_clinical_record(*, entity_type, entity_id, owner_username, subject_username, lifecycle_status, payload, metadata):
    tenant_id = _tenant_for(owner_username) or _tenant_for(subject_username) or owner_username or subject_username
    if not tenant_id:
        raise ValueError('tenant_id is required')
    repo = get_clinical_repository()
    return repo.create_clinical_record(
        entity_type=entity_type,
        entity_id=entity_id,
        tenant_id=tenant_id,
        owner_username=owner_username,
        subject_username=subject_username,
        lifecycle_status=lifecycle_status,
        payload=payload,
        metadata=metadata,
    )


def update_snapshot_for_therapist(therapist_username: str):
    tenant_id = _tenant_for(therapist_username) or therapist_username
    if not tenant_id:
        return None
    metrics = therapist_overview(therapist_username, allow_snapshot_fallback=False)
    return get_clinical_repository().upsert_analytics_snapshot(
        tenant_id=tenant_id,
        therapist_username=therapist_username,
        snapshot_date=date.today().isoformat(),
        metrics=metrics,
    )


def get_snapshot_for_therapist(therapist_username: str):
    tenant_id = _tenant_for(therapist_username)
    if not tenant_id:
        raise ValueError('tenant_id is required')
    return get_clinical_repository().get_analytics_snapshot(
        tenant_id=tenant_id,
        therapist_username=therapist_username,
        snapshot_date=date.today().isoformat(),
    )
