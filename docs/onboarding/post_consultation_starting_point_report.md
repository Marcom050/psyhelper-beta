# Report modifica onboarding post-colloquio

## Domande eliminate o rimosse dalla UI paziente
- “Com’è andata questa settimana?” (`baseline.mood`, `baseline.stress` non vengono più raccolti nel nuovo form; restano supportati nei dati storici).
- “Quale situazione importante è successa?” come episodio della settimana (`diary.guided_3_days` resta supportata per storico, ma il nuovo form usa `diary.habits_to_change`).
- “Che pensiero ti è venuto?” riferita a un episodio recente (la chiave compatibile `cbt.automatic_thought` ora raccoglie i pensieri a cui dare meno peso).
- “Quale piccolo passo vorresti provare?” come preparazione alla prossima seduta (`goals.short_term_priority`/`cbt.alternative_thought` restano solo storici).
- “Che cosa vuoi riprendere nella prossima seduta?” come valutazione/preparazione seduta (`next_session_note.note` resta compatibile; nel nuovo form è informazione aggiuntiva facoltativa).

## Domande riscritte o aggiunte
- Aggiunta: “Cosa pensi stia minando maggiormente la tua serenità in questo momento?” → `baseline.perceived_difficulty`.
- Aggiunta: “Cosa vorresti cambiare delle tue abitudini o del tuo modo di affrontare le situazioni?” → `diary.habits_to_change`.
- Riscritta: “A quali pensieri vorresti riuscire a dare meno peso?” → `cbt.automatic_thought`.
- Riscritta/riusata: “Quali cambiamenti concreti vorresti ottenere attraverso questo percorso?” → `goals.goals_text`.
- Aggiunta: “Cosa ti aspetti dal terapeuta?” → `goals.therapist_expectations`.
- Aggiunta: “Cosa pensi di poter mettere tu in questo percorso?” → `goals.personal_commitment`.
- Aggiunta facoltativa: “C’è qualcosa che vorresti che il terapeuta sapesse prima di iniziare?” → `next_session_note.additional_info`, con duplicazione compatibile in `note` e `points_to_resume`.

## Campi resi facoltativi
- La domanda finale sulle informazioni aggiuntive è esplicitamente facoltativa.
- Non sono state introdotte scale numeriche obbligatorie.

## Chiavi dati mantenute
- Step tecnici mantenuti: `baseline`, `goals`, `diary`, `cbt`, `next_session_note`.
- Chiavi legacy ancora lette/mostrate senza errori: `mood`, `stress`, `guided_3_days`, `situation`, `emotion`, `alternative_thought`, `track`, `short_term_priority`, `time_commitment`, `note`, `points_to_resume`.

## Nuove chiavi dati
- `baseline.perceived_difficulty`.
- `diary.habits_to_change`.
- `goals.therapist_expectations`.
- `goals.personal_commitment`.
- `next_session_note.additional_info`.

## Compatibilità storico
I dati precedenti restano nello stesso contenitore `post_consultation_onboardings` e vengono visualizzati con etichette “dato storico” quando non corrispondono più alla nuova semantica del form. Il riepilogo resta descrittivo e non genera diagnosi o insight clinici.
