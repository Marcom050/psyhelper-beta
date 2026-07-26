# Audit demo: accesso commerciale e persistenza

Audit eseguito il 26 luglio 2026 sul codice applicativo Python. Questo documento distingue gli stati commerciali legacy, che restano leggibili per compatibilità, dai controlli applicati nella demo.

## Inventario del gating commerciale

- `BETA_TRIAL_DAYS` è configurato in `core/settings.py`, documentato negli esempi di ambiente e usato dalle funzioni legacy in `services/subscription_service.py`. L'entrypoint Streamlit conserva il ramo commerciale isolato ma non usa il valore nella UI demo. La registrazione HTTP legacy (`api/routers/auth.py`) salva inoltre `trial_days` e una scadenza calcolata.
- `trial_expires_at`, `trial_days_remaining` e `is_trial_expired` sono definiti in `services/subscription_service.py`. Le loro sole chiamate applicative sono nel ramo UI `show_subscription_required` e nella risoluzione dello stato legacy. Con il gating spento, `is_trial_expired` restituisce sempre `False`, lo stato demo non espone i giorni residui e l'accesso è sempre consentito.
- I controlli `subscription_status`/`billing_status` sono concentrati in `services/subscription_service.py`, `services/subscription_access.py`, `services/billing_service.py`, `api/dependencies.py`, `api/security.py` e nei router auth/admin. I valori legacy ammessi (`trialing`, `active`, `past_due`, `canceled`, `inactive`, `covered_by_therapist`) sono normalizzati in `database/tenant_metadata.py`. Con `COMMERCIAL_GATING_ENABLED=false`, i guard globali danno lettura e scrittura sia al terapeuta sia al paziente collegato, senza modificare i metadata.
- Il copy visibile commerciale era nell'intestazione/disclaimer, nel banner ripetuto, nel login, nella registrazione, nelle metriche della dashboard e nel blocco subscription di `psyhelper_streamlit.py`. La UI normale ora mostra una sola nota demo; il vecchio blocco commerciale resta raggiungibile esclusivamente quando il flag viene esplicitamente riattivato. Il consenso Analytics è renderizzato solo con `SHOW_DEBUG_UI=true` e Analytics resta spento per default.
- Documenti storici in `docs/` descrivono ancora la precedente beta e il relativo modello commerciale. Non sono parte della UI e non sono stati riscritti, così il codice/processo legacy resta recuperabile.

### Causa esatta del blocco precedente

`is_subscription_active_for` trasformava un trial scaduto in `billing_status=past_due` e restituiva falso. Streamlit interrompeva poi sia la dashboard terapeuta sia il flusso paziente tramite `show_subscription_required`/`ensure_subscription_or_stop`. In parallelo, i guard API calcolavano `can_write=False` per `past_due` e `require_active_therapist` accettava soltanto gli stati configurati (normalmente `active,trialing`). Non risultano cancellazioni associate a questi controlli: era un blocco di accesso, non una rimozione dati.

## Audit cancellazione, retention e inattività

Le sole cancellazioni permanenti di account individuate sono `delete_user_account` nei repository filesystem/PostgreSQL, esposte dal servizio auth e dal router terapeuta. Nella UI Streamlit il terapeuta proprietario apre prima la sezione secondaria **Gestione profilo**, avvia l'azione e deve poi premere **Sì, elimina definitivamente** dopo l'avviso di permanenza. Esistono inoltre cancellazioni manuali di singole note dell'area privata e richieste data-rights; nessuna è temporizzata.

Non esistono job cron, TTL di account, purge, cleanup di profili, cancellazioni per `created_at`, mancato login, mancata compilazione, inattività, trial scaduto, `past_due`, hibernation o restart. `cleanup_expired` in `database/auth_security_repository.py` elimina esclusivamente record temporanei di rate-limit/revoca token scaduti, non account o dati clinici. Le scadenze dell'onboarding e degli homework cambiano solo uno stato clinico e non eliminano dati.

**Conclusione esplicita: non esiste alcuna cancellazione automatica di account o profili per inattività o scadenza del trial.**

## Percorso di persistenza

I factory di `database/repository_factory.py` selezionano in modo coerente account (credenziali/hash, metadata, profilo e messaggi), wellness (diario, homework, timeline e area privata), note private del terapeuta e record clinici. Il collegamento terapeuta-paziente è nei metadata account (`tenant_id`/`therapist_username`).

Prima della correzione, quando PostgreSQL non conteneva una riga, i repository PostgreSQL potevano leggere dal filesystem; la creazione account eseguiva anche una scrittura speculare locale. Questo consentiva una fonte di verità mista: un account poteva apparire grazie a `~/psyhelper_data/users` e sparire dopo hibernation, reboot o redeploy di Streamlit Community Cloud. È la causa più probabile della perdita apparente dei profili.

Dopo la correzione, con `USE_POSTGRESQL=true` e `DATABASE_URL` valorizzato, PostgreSQL è l'unica fonte di verità e l'unica destinazione di scrittura per account, profili, metadata, hash, messaggi, wellness e note. Una riga PostgreSQL assente produce un documento vuoto/non trovato e non una lettura locale implicita. Il filesystem resta disponibile soltanto quando il backend PostgreSQL è disabilitato e produce un warning tecnico nei log sulla non durabilità in Streamlit Community Cloud.

## Configurazione Streamlit Community Cloud

Impostare nei secrets/variabili d'ambiente:

```text
ENVIRONMENT=production
USE_POSTGRESQL=true
DATABASE_URL=<URL PostgreSQL gestito e persistente>
USE_FILESYSTEM_FALLBACK=false
COMMERCIAL_GATING_ENABLED=false
SECRET_KEY=<segreto casuale di almeno 32 caratteri>
```

Non usare directory locali o il repository Git come storage runtime. Prima del deploy verificare con `scripts/verify_postgres_consistency.py` e predisporre backup secondo `docs/backup_restore_runbook.md`.

## Migrazione non distruttiva

`scripts/backfill_postgres_accounts.py` è uno strumento manuale. Eseguirlo prima con `--dry-run`, quindi senza tale opzione. I file sorgente non vengono eliminati. Gli account già presenti in PostgreSQL sono ignorati, evitando di sovrascrivere dati potenzialmente più recenti; il riepilogo riporta migrati, ignorati e falliti senza stampare password, hash, token o contenuti clinici. Ripetere il comando è quindi idempotente.

## Limiti residui

- Il filesystem locale rimane intenzionalmente disponibile per sviluppo e non è durevole in cloud.
- I metadata commerciali legacy non vengono migrati o cancellati; sono ignorati in modalità demo.
- La durabilità effettiva dipende dal servizio PostgreSQL, dalle sue policy di backup e dalla corretta configurazione dei secrets.
- La cancellazione manuale resta definitiva e deve essere usata solo dal terapeuta proprietario dopo la doppia azione esplicita.
