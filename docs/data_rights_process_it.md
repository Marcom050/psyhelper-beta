# Processo operativo data-rights (beta commerciale controllata)

**Versione:** v0.1  
**Data:** 2026-05-19

Documento operativo preliminare per beta commerciale controllata; da validare legalmente prima di espansione commerciale ampia.

## Richieste coperte
- Export dati
- Cancellazione account/dati
- Rettifica

## Flusso MVP
1. Ricezione richiesta via email a **m.maskaro74@gmail.com** (Responsabile: **Marco Mascaro**).
2. Verifica identità/account richiedente.
3. Classificazione richiesta (export/cancellazione/rettifica).
4. Esecuzione tecnica/manuale con tracciamento interno.
5. Riscontro al professionista con esito e limiti applicati.

## Limitazioni attuali da comunicare
- Alcuni step possono richiedere intervento manuale.
- Tempistiche soggette alla capacità operativa della beta controllata.
- Cancellazioni possono includere tempi tecnici e verifiche aggiuntive.

## Supporto beta commerciale controllata
- Canale principale di supporto: **m.maskaro74@gmail.com**
- Responsabile supporto: **Marco Mascaro**
- Tempo di risposta previsto: entro **1 giorno lavorativo** durante la beta commerciale controllata.
- Per bug bloccanti, problemi di login/accesso, errori sui dati o sospetti incidenti sicurezza/privacy, il professionista deve contattare immediatamente il supporto via email includendo:
  - descrizione del problema;
  - data e ora approssimative;
  - account/tenant coinvolto;
  - passaggi che hanno portato al problema;
  - screenshot utili, evitando dati clinici non necessari.
- In caso di issue critica, Marco può sospendere temporaneamente gli accessi, impostare l'account in modalità read-only o interrompere il test beta fino al completamento delle verifiche.


## Relazione con disdetta/account commerciale
- In caso di disdetta commerciale, l'account può essere messo in sola lettura o disattivato secondo processo operativo applicabile.
- Prima della disattivazione definitiva, il professionista può richiedere export dei dati disponibili tramite questo processo.
- Richieste di cancellazione, limitazione o conservazione dati restano gestite nei limiti tecnici, contrattuali e normativi applicabili.

## Eliminazione profilo paziente (beta controllata)
- Dalla dashboard terapeuta è disponibile l'azione **Elimina profilo** con doppia conferma esplicita in italiano.
- L'eliminazione rimuove in modo permanente il record account del paziente (profilo, metadata, messaggi, wellness) dal backend attivo.
- L'azione è consentita solo a terapeuta proprietario del tenant (o amministratore se già autorizzato dai controlli API), con controlli RBAC e isolamento tenant.
- Ogni richiesta produce audit event per richiesta, esito positivo o fallimento/negazione.
- Lo stato di launch gate resta invariato: onboarding primo terapeuta pagante ancora bloccato finché i gate ufficiali non sono verdi.
