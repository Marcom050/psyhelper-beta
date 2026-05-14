# Modello abbonamento professionisti/clienti

PsyHelper usa un modello multi-account pensato per studi e psicologi:

1. Lo psicologo crea un account professionista e mantiene un solo abbonamento mensile.
2. Dalla dashboard professionista può creare account cliente separati e illimitati.
3. Ogni cliente accede con credenziali proprie e compila chat, diario, monitoraggio, esercizi e resoconto nel proprio spazio dati.
4. L'accesso dei clienti è valido solo se l'abbonamento dello psicologo collegato è attivo.

## Collegamento pagamenti in produzione

Per collegare il pagamento reale in produzione:

- imposta `SUBSCRIPTION_CHECKOUT_URL` nei secrets per mostrare il link di attivazione/rinnovo;
- aggiorna `subscription_status` dell'account professionista tramite webhook del provider pagamenti, ad esempio Stripe;
- gli stati considerati attivi sono configurabili con `ACTIVE_SUBSCRIPTION_STATUSES` e di default sono `active,trialing`;
- `NEW_THERAPIST_SUBSCRIPTION_STATUS` controlla lo stato assegnato ai nuovi professionisti e di default è `trialing` per consentire test/prova.
