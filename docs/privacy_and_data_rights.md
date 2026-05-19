# Privacy and Data Rights

- Consent model: explicit consent status/version/scope with accepted timestamp in user metadata.
- Privacy and terms versioning: stored per-user (`privacy_policy_version`, `terms_version`) and enforced at onboarding.
- Data-rights requests: `export`, `delete`, `retention`, `processing_restriction` with status transitions (`requested -> processing -> completed/rejected/cancelled`).
- Export behavior: tenant-scoped JSON only, auth required, RBAC enforced, audited (`data_export_generated`), no permanent file storage.
- Redaction: export pipeline centrally strips passwords, hashes, tokens, secrets, internal auth security state and similar sensitive keys.
- Delete/retention limitation: delete request sets `deletion_requested` flag; no automatic hard delete of clinical data.
- Audit events: admin list/update/export and export generation are written to audit log.
- Admin responsibilities: verify legal basis, process requests, update status correctly, avoid invalid transitions.
