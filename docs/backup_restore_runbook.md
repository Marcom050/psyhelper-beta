# Backup & Restore runbook (commercial beta)

## Stato operativo
**BLOCCANTE:** l'uso in produzione con dati reali **non può iniziare** finché il test completo backup/restore non è stato eseguito e registrato con evidenze reali.

## Scope dati da includere
- Database applicativo primario (PostgreSQL se attivo).
- Storage filesystem/JSON usato in fallback locale (se abilitato).
- Configurazioni operative necessarie al ripristino.

## Frequenza backup (default beta controllata)
- **Default raccomandato:** backup **giornaliero**.
- Se Marco configura una frequenza diversa, deve documentarla esplicitamente nel launch gate prima del GO.

## Target operativi (default beta controllata)
- **RPO target:** 24 ore.
- **RTO target:** 48 ore.

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

## Checklist test restore (obbligatoria prima del primo terapeuta pagante)
- Integrità dump verificata.
- Ripristino completato senza errori bloccanti.
- Accesso account test riuscito.
- Lettura dati attesa coerente.
- Test smoke essenziale completato.

## Evidenze obbligatorie (da compilare manualmente)
- Data/ora backup eseguito:
- Data/ora test restore eseguito:
- Ambiente test restore:
- Esecutore:
- Comando/strumento usato per backup:
- Comando/strumento usato per restore:
- Esito finale (PASS/FAIL):
- Problemi riscontrati e mitigazioni:
- Link/percorso artifact e log:

## Escalation e contatto incidenti (beta commerciale controllata)
- Contatto supporto/escalation: **m.maskaro74@gmail.com** (Responsabile: **Marco Mascaro**).
- Tempo di risposta previsto: entro **1 giorno lavorativo** durante la beta commerciale controllata.
- Per bug bloccanti, problemi login/accesso, errori dati o sospetti incidenti sicurezza/privacy, inviare email immediata con descrizione problema, data/ora approssimative, account/tenant coinvolto, passaggi riproduzione e screenshot utili senza dati clinici non necessari.
- In caso di issue critica, Marco può sospendere temporaneamente accessi, impostare read-only o interrompere il beta test fino a verifica completata.

## Stato evidenze attuale
- Evidenze backup/restore: **PENDING (nessun dato fittizio ammesso)**.

## Rischio configurazioni filesystem/JSON
Se la persistenza usa filesystem/JSON locale, il rischio perdita/corruzione è più alto rispetto a datastore gestito. Prima dell'uso clinico reale continuativo è richiesta configurazione produzione-safe con backup automatizzati verificati.
