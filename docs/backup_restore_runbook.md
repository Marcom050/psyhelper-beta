# Backup & Restore runbook (commercial beta)

## Scope dati da includere
- Database applicativo primario (PostgreSQL se attivo).
- Storage filesystem/JSON usato in fallback locale (se abilitato).
- Configurazioni operative necessarie al ripristino.

## Frequenza backup (placeholder)
- **[DA DEFINIRE PRIMA GO-LIVE]** (es. giornaliera + retention).

## Procedura backup manuale (MVP)
1. Identificare datastore attivo (`USE_POSTGRESQL` / filesystem fallback).
2. Eseguire dump coerente del datastore.
3. Salvare artifact in percorso sicuro con timestamp.
4. Registrare evidenza.

## Procedura restore (MVP)
1. Preparare ambiente pulito di restore.
2. Ripristinare dump.
3. Verificare avvio servizi.
4. Eseguire smoke/readiness minimi post-restore.
5. Registrare esito con eventuali anomalie.

## Checklist test restore
- Integrità dump verificata.
- Ripristino completato senza errori bloccanti.
- Accesso account test riuscito.
- Lettura dati attesa coerente.
- Test smoke essenziale completato.

## RPO/RTO (placeholder)
- RPO: **[DA DEFINIRE]**
- RTO: **[DA DEFINIRE]**

## Evidenze obbligatorie
- Data backup:
- Data test restore:
- Esecutore:
- Risultato (PASS/FAIL):
- Problemi riscontrati:

## Rischio configurazioni filesystem/JSON
Se la persistenza usa filesystem/JSON locale, il rischio perdita/corruzione è più alto rispetto a datastore gestito. Prima dell'uso clinico reale continuativo è richiesta configurazione produzione-safe con backup automatizzati verificati.
