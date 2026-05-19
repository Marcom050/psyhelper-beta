# Commercial beta launch gate status

## Current status
**BLOCKED UNTIL COMMERCIAL BETA SAFETY GATE IS COMPLETED**

## Istruzioni compilazione
Compilare questo documento solo con evidenze reali. Nessun campo può essere marcato completato senza prova verificabile.

## Dati obbligatori (da compilare manualmente)
- Commit hash under review:
- Environment name:
- Environment URL:
- Test date (YYYY-MM-DD):
- Executor:

## Comandi obbligatori eseguiti
- `pytest -q`:
- `python scripts/preprod_readiness_check.py`:
- `python scripts/smoke_test_private_beta.py --dry-run`:

## Required before first paying therapist
- Test suite e readiness registrati con output reale: **PENDING**
- Backup/restore test completed with evidence: **PENDING**
- Manual billing activation tested end-to-end with evidence: **PENDING**
- Support/contact path filled and published: **PENDING**
- Accepted conditions sign-off (business + ops + legal review pending): **PENDING**

## Support model (beta commerciale controllata)
- Canale supporto principale: **m.maskaro74@gmail.com**
- Responsabile supporto: **Marco Mascaro**
- Finestra risposta target: entro **1 giorno lavorativo** durante la beta commerciale controllata.
- Escalation bug bloccante: terapeuta -> canale supporto -> Marco Mascaro con priorità alta e presa in carico immediata.
- Escalation incidente dati: segnalazione immediata a Marco Mascaro, blocco operativo se necessario, triage e registrazione incidente.
- In caso di issue critica, Marco può sospendere temporaneamente accessi, impostare read-only o interrompere il beta test fino a verifica completata.
- Disclaimer emergenze: PsyHelper non gestisce emergenze cliniche; in caso di emergenza o rischio immediato usare i canali professionali/sanitari o di emergenza.

## Backup/restore evidence
- Frequenza backup configurata (default: giornaliera):
- RPO target (default: 24h):
- RTO target (default: 48h):
- Data test restore pre-GO:
- Esito test restore (PASS/FAIL):
- Link evidence/log:


## Evidenze policy commerciale (trial/disdetta/rimborsi)
- Conferma comunicazione trial 24 ore pre-addebito: **PENDING**
- Conferma raccolta dati contatto + fatturazione alla creazione account: **PENDING**
- Conferma procedura manuale "no addebito se disdetta entro 24 ore": **PENDING**
- Conferma policy "no rimborsi post-pagamento salvo legge/accordo scritto": **PENDING**

## Manual billing activation evidence
- Terapeuta test (anonimizzato/ID):
- Conferma accordo piano €29,90/mese:
- Conferma pagamento/fatturazione manuale:
- Stato precedente account:
- Stato nuovo account:
- Audit record (chi/quando/motivo):
- Onboarding inviato dopo attivazione:

## Accepted conditions
- Ho verificato che non sono presenti evidenze fittizie.
- Ho verificato che backup/restore è stato testato con successo prima del GO.
- Ho verificato che il contatto supporto è compilato e attivo.
- Ho verificato che il flusso billing manuale è stato testato e tracciato.

## Decision field
- GO
- GO WITH CONDITIONS
- NO-GO

## Decision (current)
**NO-GO (default until all required evidence is complete).**

## Sign-off
- Decision:
- Signed by:
- Date:
- Conditions (if GO WITH CONDITIONS):
