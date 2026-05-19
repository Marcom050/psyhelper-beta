# Subscription model - Commercial beta safety gate

## Plan
- **PsyHelper Beta Professionista — €29,90/mese**.
- Fase iniziale: attivazione commerciale controllata con billing manuale consentito.

## Stati subscription
- `trialing`: accesso consentito durante prova iniziale.
- `active`: accesso pieno funzionalità previste.
- `grace_period`: accesso limitato; avviso pagamento da regolarizzare.
- `past_due`: modalità read-only.
- `canceled`: modalità read-only e blocco nuove operazioni scrittura.

## Read-only mode
In `past_due` e `canceled` l'utente può consultare dati consentiti ma non creare/modificare nuovi contenuti clinici/operativi.

## Workflow manuale primo cliente pagante
1. Emissione richiesta pagamento manuale (€29,90/mese).
2. Verifica conferma pagamento (es. bonifico/accordo fatturazione).
3. Admin autorizzato aggiorna stato subscription su account (`active` o stato appropriato).
4. Registrare evidenza in audit interno: chi, quando, stato precedente, stato nuovo, motivo.
5. Comunicare al terapeuta esito attivazione e data rinnovo.

## Chi può attivare/disattivare
- Solo admin autorizzati.
- Nessun self-service per stato commerciale in questa fase.

## Audit richiesto
Ogni attivazione/disattivazione deve lasciare traccia verificabile (timestamp, attore, tenant/account, motivazione).

## Pagamento fallito
- Impostare `grace_period` con comunicazione al terapeuta.
- Se non regolarizzato entro finestra definita, passare a `past_due` (read-only).
- Comunicare sempre prossimi passi e canale supporto.

## Messaggio al terapeuta (template sintetico)
"Il tuo account PsyHelper è in beta commerciale controllata. Lo stato abbonamento è aggiornato a: <stato>. Per supporto amministrativo/contabile contatta: <canale supporto>."

## Metodo minimo sicuro attuale
Usare il flusso admin/backend già esistente per aggiornare metadata subscription dell'account; vietate modifiche dirette non tracciate fuori dal percorso amministrativo autorizzato.
