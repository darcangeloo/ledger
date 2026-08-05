# Ledger

Note, journal e progetti in un'unica app desktop per Windows. Tutto resta sul
tuo computer, cifrato. Nessun account, nessun server, nessuna connessione.

## Cosa fa

- **Pagine a blocchi** — testo, titoli, elenchi, checklist, citazioni, codice,
  tabelle e diagrammi Mermaid
- **Database** con schema a piacere, guardabili come tabella, board kanban o lista
- **Ricerca full-text** su tutto quello che hai scritto
- **Backlink** — scrivi `[[Nome pagina]]` e la pagina citata mostra chi la nomina
- **Journal** giornaliero con mood, gratitudine e contatore di giorni consecutivi
- **Ripasso programmato** dei concetti, con algoritmo SM-2
- **Progetti** con stato, priorità e pagine Architettura / Decisioni / Vincoli
- **Cattura rapida** — `Ctrl+Shift+Space` da qualsiasi applicazione, con Ledger
  minimizzato o dietro le altre finestre: finisce in una inbox da smistare
- **Punto della settimana** — scadenze, ripassi e pagine toccate di recente
- **Backup** cifrato su una cartella che scegli tu, anche un disco esterno
- **Esportazione** di qualsiasi pagina in Markdown

Tutto poggia su una sola tabella `blocks`: ogni funzione è una query su quella,
non una tabella dedicata.

## Installazione

Scarica `Ledger.exe` dall'ultima [release](../../releases) e lancia:

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1
```

Copia il programma in `%LOCALAPPDATA%\Programs\Ledger` e crea i collegamenti su
Desktop e menu Start. Non servono diritti di amministratore e non viene scritto
nulla fuori dal tuo profilo utente.

Per rimuoverlo: `install.ps1 -Uninstall`. Le note **non** vengono cancellate.

In alternativa puoi eseguire `Ledger.exe` direttamente, senza installare nulla.

> **Al primo avvio Windows SmartScreen mostra un avviso**: l'eseguibile non è
> firmato con un certificato commerciale. Confronta il checksum SHA-256 con
> quello pubblicato nella release, oppure compila tu dai sorgenti.

## Dove finiscono i dati

| | |
|---|---|
| Vault cifrato | `%APPDATA%\Ledger\ledger.db` |
| Salt della chiave | `%APPDATA%\Ledger\ledger.db.salt` |

Servono entrambi: se copi il vault, copia anche il `.salt`.

**Non esiste un recupero della passphrase.** Se la dimentichi, le note non sono
più leggibili da nessuno. Fai backup.

Il modello di sicurezza, con i suoi limiti espliciti, è descritto in
[SECURITY.md](SECURITY.md). Leggilo prima di affidarci qualcosa di davvero
delicato.

## Compilare dai sorgenti

Servono Python 3.11+ e Node 18+.

```bash
pip install -r requirements.txt
npm install

npm run build                          # compila Editor.js e Mermaid in locale
pyinstaller build.spec --noconfirm     # produce dist/Ledger.exe
```

Per lo sviluppo, senza impacchettare:

```bash
npm run build
python main.py
```

In sviluppo il vault sta accanto ai sorgenti; nell'eseguibile in `%APPDATA%`.

## Test

Solo libreria standard, nessuna GUI: coprono cifratura, motore a blocchi,
ricerca, backlink, SM-2, journal, export e backup.

```bash
python -m unittest discover -s tests -v
```

## Come è fatto

Python + [pywebview](https://pywebview.flowrl.com/) (WebView2), niente Electron.
Il frontend è HTML/CSS/JS compilato con esbuild: le librerie finiscono dentro
l'eseguibile, non vengono mai scaricate da un CDN.

```
main.py              avvio, finestra, percorsi
crypto.py            vault cifrato, DB in memoria
db.py                CRUD e query generica sulla tabella blocks
api.py               ponte verso il frontend
search.py            indice FTS5 e ricerca
links.py             backlink [[wikilink]]
journal.py           journal, riflessioni, streak
spaced_repetition.py algoritmo SM-2
projects.py          progetti e pagine collegate
planning.py          modello di piano ed esportazione Markdown
review.py            aggregazione settimanale
capture.py           hotkey globale e finestra di cattura
backup.py            copia cifrata su cartella locale
frontend/            interfaccia
tests/               test del motore dati e della cifratura
```

## Licenza

MIT — vedi [LICENSE](LICENSE).
