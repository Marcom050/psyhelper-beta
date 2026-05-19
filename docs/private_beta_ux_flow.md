# Private Beta UX Flow (Streamlit)

## Obiettivo del flusso
Rendere la prima esperienza del terapeuta in private beta più chiara, con navigazione semplice, stati vuoti leggibili e messaggi di rischio/limite espliciti, senza riscrivere architettura o frontend.

## User journey private beta (inteso)
1. Accesso con account esistente oppure creazione account terapeuta (trial beta).
2. Presa visione dei disclaimer private beta.
3. Apertura dashboard terapeuta con percorso guidato: crea/seleziona paziente, controlla trend, prepara recap.
4. Gestione homework/timeline/note private del paziente selezionato.
5. Logout e chiusura sessione.

## Therapist first-login flow
- Login tramite credenziali fornite/registrate.
- Se ruolo terapeuta: accesso diretto alla dashboard terapeuta.
- Dashboard mostra stato accesso/subscription e CTA primaria “Crea nuovo paziente”.

## Create client flow
- Pulsante dedicato in alto nella dashboard terapeuta.
- Dialog con validazioni minime (nome, username, password temporanea, conferma password).
- Dopo creazione: selezione automatica del nuovo paziente e refresh dashboard.

## Mood / Homework / Report flow
- Mood/trend: tab Trend mostra indicatori quando disponibili, altrimenti stato vuoto esplicativo.
- Homework: assegnazione in form dedicata + monitoraggio assegnati/completati.
- Report/recap: recap pre-seduta esportabile in `.txt`.

## Export / Data-rights visibility
- Nessuna nuova UI dedicata aggiunta in questa sprint.
- Sezioni informative private beta indicano che la governance dati/export resta controllata.

## Limitazioni note
- End-to-end autenticato resta in parte manuale per scelta di controllo beta.
- Streamlit resta UI di beta: non è ancora un frontend/mobile finale.
- Nessuna automazione nuova su compliance legale/regolatoria.

## Cosa resta manuale
- Validazione operativa finale prima di uso con tester fidati.
- Alcune verifiche di readiness/deployment tramite script e checklist manuale.

## Cosa è intenzionalmente non rifinito
- Design system completo.
- Esperienza mobile dedicata.
- Orchestrazione multi-servizio avanzata.

## Stato mobile
- Mobile app **non iniziata** in questa sprint.
- Qualsiasi nota mobile è solo pianificazione futura, non implementazione.

## Note pianificazione futura (non implementate)
- Definire user flow mobile therapist-first coerente con RBAC attuale.
- Mappare subset di schermate Streamlit da portare in frontend moderno in sprint separata.

## Vincolo lingua private beta
- Tutto il testo visibile ai terapeuti/clienti nella UI Streamlit deve restare in italiano (disclaimer, warning, stati vuoti, etichette e guidance).
- Materiale tecnico interno (script CLI, commit, test, runbook) può restare in inglese.

## UX polish sprint: chiarezza terapeuta + riduzione clutter
- **Vincolo lingua:** tutta la UI visibile a terapeuti/clienti resta in italiano (etichette, warning, stati vuoti, onboarding, navigazione).
- **Principio guida:** ridurre elementi ripetuti o tecnici nel flusso principale; mostrare prima azioni e dati utili alla seduta.
- **Chat session cleanup:** la chat visibile in sessione Streamlit viene azzerata su logout/reset sessione e tramite azione esplicita “Pulisci chat corrente”, con pulizia solo UI/session-state (nessuna cancellazione dei record clinici persistiti lato backend).
- **Diario semplificato:** il campo “risposta alternativa CBT” è rimosso dal flusso UI standard per mantenere la compilazione essenziale.
- **Igiene metadati:** in aree utente standard non vanno mostrati token/secret/password, né metadati low-value (es. `created_at`, `internal_id`) salvo contesti admin/debug separati.
- **Input chat bottom-native:** i messaggi vengono renderizzati sopra il `st.chat_input` e l’input resta nel comportamento bottom nativo di Streamlit; applicata solo una rifinitura CSS minima per coerenza visiva.
- **Limite noto Streamlit:** il posizionamento/stile finale dell’input può variare leggermente in base a tema e browser e non replica in modo pixel-perfect il layout ChatGPT.
- **Stato mobile:** app mobile non avviata in questa sprint (solo Streamlit private beta).
