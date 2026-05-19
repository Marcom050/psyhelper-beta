# Admin governance

## Ruoli disponibili
- `client`: utente paziente
- `therapist`: tenant owner clinico
- `admin`: ruolo privilegiato piattaforma

## Regole di governance admin
- Signup pubblico (`/auth/signup`) non consente `role=admin`.
- Bootstrap admin iniziale avviene solo via `python scripts/admin_bootstrap.py`.
- Promozione/demotion admin avviene via endpoint admin role patch, sempre auditata.
- Self-demotion ultimo admin è bloccata.

## Bootstrap iniziale
1. Configurare `ADMIN_BOOTSTRAP_SECRET` forte (>=32, alfanumerico).
2. Eseguire comando one-time:
   `python scripts/admin_bootstrap.py --username <admin> --password <pwd> --bootstrap-secret <secret>`
3. Ruotare o rimuovere il secret dopo bootstrap.

## Audit admin
- `admin_bootstrap_created` (critical)
- `admin_role_changed` (high quando coinvolge ruolo admin)

## Limiti attuali
- Nessun workflow di approvazione multi-admin.
- Nessuna integrazione HSM/KMS per secret bootstrap.
- Nessun dual-control per demotion/promozione in produzione enterprise.
