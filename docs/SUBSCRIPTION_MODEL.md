# Subscription model - Commercial beta safety gate

## Plan
- **PsyHelper Beta Professionista — €29,90/mese**.
- Fase iniziale: attivazione commerciale controllata con billing manuale consentito.

## Stati subscription
- `trialing`: accesso consentito durante prova iniziale di 24 ore; primo pagamento non ancora dovuto.
- `active`: accesso pieno funzionalità previste.
- `grace_period`: accesso limitato; avviso pagamento da regolarizzare.
- `past_due`: modalità read-only.
- `canceled`: modalità read-only e blocco nuove operazioni scrittura.

## Read-only mode
In `past_due` e `canceled` l'utente può consultare dati consentiti ma non creare/modificare nuovi contenuti clinici/operativi.

## Workflow manuale primo cliente pagante (obbligatorio in beta controllata)
1. Il terapeuta conferma adesione al piano **€29,90/mese** e fornisce dati di contatto + informazioni di fatturazione/pagamento in fase di creazione account.
2. L'account entra in `trialing` per 24 ore: durante questa finestra non è dovuto alcun pagamento.
3. Se arriva richiesta di cancellazione/disdetta entro 24 ore, non si applica alcun addebito del primo mese e l'account viene disattivato o portato in sola lettura secondo processo operativo.
4. Se non arriva disdetta entro 24 ore, il primo pagamento diventa dovuto e pagamento/fatturazione vengono gestiti manualmente (es. bonifico/fattura) in questa fase beta.
5. Marco verifica l'incasso o la conferma amministrativa del pagamento.
6. Solo dopo verifica, admin autorizzato imposta lo stato subscription su `active` (o stato appropriato).
7. Registrare evidenza in audit interno: chi, quando, account/tenant, stato precedente, stato nuovo, motivo.
8. Inviare al terapeuta istruzioni di onboarding e conferma attivazione.

## Chi può attivare/disattivare
- Solo admin autorizzati.
- Nessun self-service per stato commerciale in questa fase.

## Audit richiesto
Ogni attivazione/disattivazione deve lasciare traccia verificabile (timestamp, attore, tenant/account, motivazione).

## Pagamento fallito o non regolarizzato
- Impostare `grace_period` con comunicazione al terapeuta.
- Se non regolarizzato entro finestra definita, passare a `past_due` (read-only).
- Mantenere tracciabilità audit del cambio stato.
- Comunicare sempre prossimi passi e canale supporto.

## Messaggio al terapeuta (template sintetico)
"Il tuo account PsyHelper è in beta commerciale controllata. Lo stato abbonamento è aggiornato a: <stato>. Per supporto amministrativo/contabile contatta: m.maskaro74@gmail.com."

## Metodo minimo sicuro attuale
Usare il flusso admin/backend già esistente per aggiornare metadata subscription dell'account; vietate modifiche dirette non tracciate fuori dal percorso amministrativo autorizzato.


## Supporto beta commerciale controllata
- Canale principale di supporto amministrativo/contabile: **m.maskaro74@gmail.com**.
- Responsabile supporto: **Marco Mascaro**.
- Tempo di risposta previsto: entro **1 giorno lavorativo** durante la beta commerciale controllata.


## Disdetta e rimborsi (beta commerciale controllata)
- Salvo diverso accordo scritto o obbligo inderogabile di legge, gli importi già pagati non sono rimborsabili.
- Salvo diverso accordo scritto, la disdetta dopo attivazione ha effetto al termine del periodo già pagato.
- Dopo disdetta, l'account può essere impostato in sola lettura o disattivato secondo processo operativo.
- Policy operativa preliminare: validazione legale necessaria prima di rollout commerciale ampio.
