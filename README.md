# PsyHelper Streamlit

Applicazione Streamlit per supporto CBT con chat, diario, monitoraggio ansia/stress, esercizi mindfulness e resoconto esportabile.

## Avvio locale

1. Installa le dipendenze:

   ```bash
   pip install -r requirements.txt
   ```

2. Configura la chiave Groq in `.streamlit/secrets.toml`:

   ```toml
   GROQ_API_KEY="la-tua-chiave"
   ```

3. Avvia l'app:

   ```bash
   streamlit run psyhelper_streamlit.py
   ```

## Deploy su Streamlit Cloud

Se Streamlit Cloud mostra un errore simile a:

```text
Failed to download the sources for repository: 'psyhelper-beta', branch: 'main', main module: 'psyhelper_streamlit.py'
Make sure the repository and the branch exist and you have write access to it, and then reboot the app.
```

il problema avviene **prima** dell'esecuzione del codice Python: Streamlit Cloud non riesce a clonare il repository/branch configurato.

Controlla questi punti nella dashboard di Streamlit Cloud:

1. **Repository corretto**: il repository GitHub deve esistere e l'account Streamlit deve avere accesso.
2. **Branch corretto**: questo workspace sta lavorando sul branch `work`; se su GitHub non esiste `main`, imposta il deploy sul branch esistente oppure crea/pusha un branch `main`.
3. **Main file path**: deve essere `psyhelper_streamlit.py`.
4. **Repo privato**: se il repository è privato, autorizza Streamlit Cloud/GitHub a leggere quel repository.
5. **Reboot**: dopo aver corretto repository o branch, usa **Reboot app** da Streamlit Cloud.

### Opzioni rapide per risolvere branch `main` mancante

- Cambia nelle impostazioni Streamlit Cloud il branch da `main` al branch realmente presente su GitHub.
- Oppure, se vuoi usare `main`, crea e pusha il branch su GitHub:

  ```bash
  git checkout -b main
  git push -u origin main
  ```

