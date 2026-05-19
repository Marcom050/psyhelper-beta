# Private Beta Backend Readiness

## Ready for private beta
- Tenant-scoped auth/RBAC and admin controls.
- Data-rights request workflow with validated status transitions.
- Safe JSON data export endpoints for self and admin request handling.
- Security headers baseline (`nosniff`, `DENY`, `Referrer-Policy`, no-store for sensitive endpoints).
- Readiness check script covering secret quality, debug, CORS, persistence paths, privacy versions, export flag.

## Not full production compliance yet
- Legal review pending.
- DPIA pending.
- DPA process pending.
- Formal backup policy pending.
- Formal incident response policy pending.
- No fully automated legal/compliance orchestration.

## Future compliance steps
1. External legal review of policy and processing records.
2. DPIA with risk register and mitigations.
3. Vendor/subprocessor DPA completion.
4. Backup retention + restoration drills.
5. Incident response runbooks + tabletop exercises.
