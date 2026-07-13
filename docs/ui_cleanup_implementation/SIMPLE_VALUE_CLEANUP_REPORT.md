# PsyHelper Streamlit - Simple Value Cleanup Report

## Sintesi
Pulizia mirata dei campi modificabili in `psyhelper_streamlit.py` per rendere la demo più immediata: meno caselle superflue, domande più semplici, help brevi, placeholder concreti e visibilità esplicitata per contenuti sensibili.

## Campi eliminati dalla UI
- Diario paziente: `Bisogno emerso` rimosso dalla UI e salvato come stringa vuota compatibile nella chiave `bisogno`.
- Onboarding iniziale: sonno, motivazione, pensieri generici e obiettivi generici rimossi dal flusso visibile; le chiavi profilo restano valorizzate con default compatibili.
- Preparazione seconda seduta: track di prosecuzione, priorità breve termine, disponibilità media, stress medio e obiettivi 2-4 settimane nascosti dalla visualizzazione normale e mappati su default/valori esistenti.
- Timeline terapeuta: rimosso il pulsante `Aggiungi al recap pre-seduta`.
- Sidebar demo: note beta e metadata di sessione nascosti salvo `SHOW_DEBUG_UI=true`.

## Campi resi facoltativi
- Diario paziente: ansia, stress, sensazioni corporee e nota per la seduta esplicitati come facoltativi o spostati in dettagli.
- Area privata: titolo reso facoltativo e non bloccante.
- Timeline terapeuta: dettaglio evento indicato come facoltativo.

## Campi spostati nei dettagli
- Diario paziente: ansia, stress e sensazioni corporee spostati nell'expander chiuso `Aggiungi qualche dettaglio, se ti aiuta`.

## Domande riscritte
| Sezione | Campo precedente | Decisione | Nuova domanda | Help | Placeholder | Perché è utile |
|---|---|---|---|---|---|---|
| Diario | Data | Mantenuto | Data | Scegli il giorno dell'episodio. | n/d | Colloca gli episodi nel tempo. |
| Diario | Stato d'animo prevalente | Riscritto | Che emozione hai sentito di più? | Scegli quella più presente in quel momento. | n/d | Consente trend e lettura episodio. |
| Diario | Intensità dell'emozione (1-10) | Riscritto | Quanto era forte? | 0 significa per niente, 10 significa molto forte. | n/d | Rende confrontabile l'intensità nel tempo. |
| Diario | Trigger/situazione | Riscritto | Che cosa è successo? | Descrivi brevemente il momento o la situazione. | Es. Ho ricevuto un messaggio che mi ha preoccupato. | Descrive l'episodio concreto. |
| Diario | Pensiero automatico | Riscritto | Che pensiero ti è venuto in quel momento? | Scrivilo come ti è comparso, anche con poche parole. | Es. Non riuscirò a gestirlo. | Aiuta il terapeuta a capire il significato attribuito all'episodio. |
| Diario | Comportamento o impulso | Riscritto | Che cosa hai fatto subito dopo? | Descrivi brevemente come hai reagito. | Es. Ho evitato di rispondere e ho spento il telefono. | Collega episodio e reazione osservabile. |
| Diario | Nota per il professionista | Riscritto | Vuoi riprendere qualcosa di questo episodio in seduta? (facoltativo) | Questo testo sarà visibile al terapeuta. | Es. Vorrei capire perché tendo a evitare queste situazioni. | Produce punti concreti per la seduta. |
| Diario dettagli | Ansia (0-10) | Spostato nei dettagli | Quanta ansia hai sentito? (facoltativo) | Indica la tua percezione da 0 a 10. | n/d | Mantiene grafici e recap senza appesantire il diario. |
| Diario dettagli | Stress (0-10) | Spostato nei dettagli | Quanto stress hai sentito? (facoltativo) | Indica la tua percezione da 0 a 10. | n/d | Mantiene trend distinti quando compilato. |
| Diario dettagli | Sensazioni corporee | Spostato nei dettagli | Che cosa hai sentito nel corpo? (facoltativo) | Scegli solo le sensazioni che ricordi chiaramente. | n/d | Aggiunge contesto somatico se utile. |
| Diario dettagli | Bisogno emerso | Nascosto dalla UI | n/d | n/d | n/d | Riuso basso; chiave preservata. |
| Homework terapeuta | Esercizio | Riscritto | Quale esercizio vuoi assegnare? | Scegli l'attività concordata con il paziente. | n/d | Identifica il tipo di compito. |
| Homework terapeuta | Scadenza | Riscritto | Entro quando? | Scegli una data realistica rispetto alla prossima seduta. | n/d | Rende chiara la data di completamento. |
| Homework terapeuta | Consegna essenziale | Riscritto | Che cosa vuoi chiedere al paziente? | Questa è la domanda che comparirà nel compito. | Es. Quale piccolo passo puoi provare prima della prossima seduta? | Evita duplicazioni di obiettivo/istruzioni. |
| Homework paziente | Prompt come label della textarea | Riscritto | La tua risposta | Scrivi ciò che hai osservato o provato. Non serve una risposta perfetta. | Es. Ho provato a fare una pausa prima di rispondere. | Mostra prima la domanda assegnata e poi una risposta singola. |
| Area privata | Titolo | Riscritto | Titolo facoltativo | Serve soltanto a ritrovare la nota più facilmente. | Es. Da riprendere con calma | Aiuta il recupero senza bloccare il salvataggio. |
| Area privata | Nota privata | Riscritto | Che cosa vuoi annotare? | Questa nota resta privata finché non scegli di condividerla. | Scrivi un pensiero, un dubbio o qualcosa che non vuoi dimenticare. | Chiarisce privacy e contenuto atteso. |
| Area privata | Condividi con il terapeuta | Riscritto | Condividi questa nota | n/d | n/d | Esplicita l'azione sulla nota corrente. |
| Area privata | Revoca condivisione | Riscritto | Interrompi la condivisione | n/d | n/d | Chiarisce l'effetto senza cambiare stati tecnici. |
| Preparazione seconda seduta | Baseline: umore medio settimana | Riscritto | Com'è andata questa settimana? | 0 significa molto difficile, 10 significa molto bene. | n/d | Sintesi semplice della settimana. |
| Preparazione seconda seduta | Diario guidato 3 giorni | Riscritto | Quale situazione importante è successa? | Descrivi un episodio concreto della settimana. | Es. Ho affrontato una conversazione che rimandavo. | Fornisce un episodio da discutere. |
| Preparazione seconda seduta | Scheda CBT: pensiero automatico | Riscritto | Che pensiero ti è venuto? | Scrivi il pensiero principale, anche in poche parole. | Es. Non ce la farò. | Raccoglie il pensiero senza termini tecnici. |
| Preparazione seconda seduta | Pensiero alternativo | Riscritto | Quale piccolo passo vorresti provare? | Indica un'azione semplice da discutere con il terapeuta. | Es. Rispondere dopo aver fatto una pausa. | Trasforma la preparazione in azione concreta. |
| Preparazione seconda seduta | Nota prossima seduta | Riscritto | Che cosa vuoi riprendere nella prossima seduta? | Questo testo sarà visibile al terapeuta. | Es. Vorrei parlare della paura di sbagliare. | Produce agenda di seduta. |
| Onboarding iniziale | Umore attuale | Riscritto | Come ti senti oggi? | Serve solo a iniziare il monitoraggio. | n/d | Riduce l'attrito iniziale. |
| Onboarding iniziale | Intensità del malessere | Riscritto | Quanto è forte questa emozione? | 0 significa per niente, 10 significa molto forte. | n/d | Primo dato comparabile. |
| Timeline terapeuta | Aggiungi evento/progresso/ricaduta | Riscritto | Che cosa vuoi aggiungere al percorso? | Inserisci un evento o un cambiamento utile da ricordare. | Es. Ha affrontato una situazione che prima evitava. | Aggiunge eventi manuali utili al percorso. |
| Timeline terapeuta | Dettaglio | Riscritto | Aggiungi un breve dettaglio | Facoltativo: indica perché può essere utile riprenderlo. | Es. Ne parleremo nella prossima seduta. | Contestualizza l'evento. |
| Note terapeuta | Osservazioni cliniche, ipotesi, note seduta | Riscritto | Note private del terapeuta | Queste note non sono mostrate al paziente e non entrano automaticamente nel recap. | Scrivi appunti utili per il tuo lavoro. | Mantiene spazio professionale esplicito. |
| Recap | Text area read-only | Riscritto | Riepilogo prima della seduta | n/d | n/d | Evita l'impressione di campo modificabile. |

## Help e placeholder introdotti
- Aggiunti help brevi ai campi principali del diario, homework, area privata, preparazione seconda seduta, timeline e note terapeuta.
- Aggiunti placeholder concreti per episodio, pensiero, reazione, nota da seduta, homework, area privata, preparazione seconda seduta e timeline manuale.
- Aggiunte caption di visibilità per risposte homework, note private condivise e timeline manuale.

## Chiavi dati mantenute
- Diario: `data`, `umore`, `umore_intensita`, `ansia`, `stress`, `trigger`, `sensazioni`, `bisogno`, `pensiero_automatico`, `comportamento`, `nota_professionista`.
- Homework: assegnazione con template, prompt e due date; risposta singola invariata.
- Area privata: stati tecnici `private`, `shared`, `revoked` invariati.
- Preparazione seconda seduta: step `baseline`, `goals`, `diary`, `cbt`, `next_session_note` mantenuti e popolati con valori compatibili.
- Timeline: `timeline_events` invariata.
- Note terapeuta: storage esistente invariato.

## Test eseguiti
- `pytest -q`
- `python -m compileall -q .`
- `python -m ruff check psyhelper_streamlit.py`
- Avvio Streamlit con health check HTTP locale.

## Problemi incontrati
- Nessun problema nei test automatici eseguiti.
- La verifica completa manuale dei 10 flussi Streamlit non è automatizzabile in questa sessione non interattiva; è stato effettuato avvio applicazione e health check HTTP locale.

## Modifiche rinviate perché troppo complesse
- Nessun cambio di schema dati.
- Nessun refactoring di servizi, repository, autenticazione, autorizzazione, algoritmi recap/trend/insight o AI.
- Nessuna modifica a billing, trial, prezzi o flussi commerciali.

## File modificati
- `psyhelper_streamlit.py`
- `docs/ui_cleanup_implementation/SIMPLE_VALUE_CLEANUP_REPORT.md`
