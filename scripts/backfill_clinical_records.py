"""Backfill legacy wellness JSON into structured clinical_records."""
import argparse

from services import auth_service, clinical_data_service


def run(tenant_id: str, dry_run: bool = True):
    clients = auth_service.get_clients_for_tenant(tenant_id)
    created = 0
    for c in clients:
        username = c.get('username')
        bundle = auth_service.load_account_bundle(username)
        wellness = bundle.get('wellness', {})
        for i, m in enumerate(wellness.get('mood_entries', [])):
            if dry_run:
                created += 1
                continue
            clinical_data_service.create_clinical_record(entity_type='mood_entry', entity_id=f'backfill-{username}-{i}', owner_username=tenant_id, subject_username=username, lifecycle_status='active', payload=m, metadata={'backfill': True})
            created += 1
    return created


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--tenant-id', required=True)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    print({'created': run(args.tenant_id, dry_run=args.dry_run), 'dry_run': args.dry_run})
