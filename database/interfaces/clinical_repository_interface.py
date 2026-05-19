from abc import ABC, abstractmethod


class ClinicalRepository(ABC):
    @abstractmethod
    def create_clinical_record(self, *, entity_type, entity_id, tenant_id, owner_username, subject_username, lifecycle_status, payload, metadata):
        ...

    @abstractmethod
    def update_clinical_record_status(self, *, tenant_id, entity_type, entity_id, lifecycle_status):
        ...

    @abstractmethod
    def list_clinical_records(self, *, tenant_id, entity_type=None, owner_username=None, subject_username=None, lifecycle_status=None):
        ...

    @abstractmethod
    def upsert_analytics_snapshot(self, *, tenant_id, therapist_username, snapshot_date, metrics):
        ...

    @abstractmethod
    def get_analytics_snapshot(self, *, tenant_id, therapist_username, snapshot_date):
        ...
