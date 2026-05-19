# Private beta launch checklist

- Impostare `ENVIRONMENT=production`.
- Impostare `SECRET_KEY` forte (>=32 caratteri).
- Configurare `ADMIN_BOOTSTRAP_SECRET` forte, usare una sola volta, poi ruotare/rimuovere.
- Configurare backend persistence (`USE_POSTGRESQL` + `DATABASE_URL` oppure fallback filesystem controllato).
- Configurare `AUDIT_LOG_PATH` persistente.
- Configurare `AUTH_SECURITY_STATE_PATH` persistente.
- Configurare `PRIVACY_POLICY_VERSION` e `TERMS_VERSION`.
- Configurare `DATA_EXPORT_ENABLED` esplicito.
- Configurare `CORS_ALLOWED_ORIGINS` non permissivo (mai `*`).
- Eseguire backup manuale iniziale storage + audit.
- Eseguire smoke test post-deploy (login, onboarding therapist, client create, export).
- Verifica pre-invito terapeuti: readiness script green, admin governance attiva, audit persistente.
- Rollback base: ripristino snapshot storage + env precedente + restart.
- Limiti beta dichiarati: no enterprise IAM, no dual control, no hard delete clinico.
