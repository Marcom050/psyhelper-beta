# Audit modalità demo, gating commerciale e persistenza

## Stato dopo le correzioni CI della PR #117

La modalità predefinita è una demo senza billing: `COMMERCIAL_GATING_ENABLED=false` è
documentato negli esempi di configurazione e il controllo commerciale è opt-in. La
PR #117 aveva già introdotto il flag nelle settings, il corto circuito dell'accesso,
l'isolamento delle settings nei test, il copy demo e PostgreSQL come fonte
autorevole senza letture di fallback dal filesystem.

Con il gating disattivato, un terapeuta (anche con trial storico scaduto) e i suoi
pazienti collegati possono effettuare login e leggere o scrivere dati clinici. Lo
stato esposto è `demo`, senza scadenza o giorni residui. Se il flag è attivo,
continuano a valere gli stati commerciali legacy (`trialing`, `active`, periodo di
grazia e `past_due`).

## Interfaccia

Nel normale flusso demo compare una sola nota discreta. Trial, giorni residui,
metriche di abbonamento e copy della beta commerciale non vengono mostrati. Il
disclaimer professionale e di emergenza resta sempre visibile; i controlli Analytics
sono disponibili soltanto con `SHOW_DEBUG_UI=true`. La cancellazione paziente è
un'azione manuale nella sezione secondaria **Gestione profilo**, preceduta da un
avviso permanente e da una seconda conferma esplicita.

## Persistenza e migrazione

Quando `USE_POSTGRESQL=true`, i repository PostgreSQL sono autorevoli e l'assenza di
un record non provoca letture dal filesystem. Il filesystem è destinato al solo
sviluppo locale: su Streamlit Community Cloud non è durevole e può essere perso.

`scripts/backfill_postgres_accounts.py` è uno strumento manuale e idempotente. Offre
`--dry-run`, ignora sempre i record già presenti in PostgreSQL, non modifica né
cancella i file sorgente e stampa soltanto i conteggi `migrated`, `skipped` e
`failed`, senza identificativi o contenuti degli account.
