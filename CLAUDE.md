# Ledger — CLAUDE.md

*(ottimizzato per Claude Sonnet 5 in Claude Code — agentico, esecuzione a fasi)*

## Stato iniziale

Nessun codice esistente per questo progetto. Prima esecuzione da zero.

## Stato finale (target)

App desktop Windows standalone (.exe), 100% locale, cifrata a riposo. Un unico motore dati a blocchi alimenta: editor pagine, database/tabelle con viste multiple (tabella/kanban/lista), ricerca full-text, backlink tra pagine, spaced-repetition (knowledge booster), sezione system design con diagrammi, code planning mode con export .md, quick capture globale, weekly review automatica, backup cifrato locale.

## Regole vincolanti (MUST / NEVER)

* MUST: unico motore dati a blocchi (tabella `blocks`). Ogni feature (task, database, backlink, spaced repetition, ricerca) è uno schema o una query su questa tabella — MAI una tabella parallela dedicata a un singolo concetto
* MUST: zero chiamate di rete in qualsiasi fase, incluse librerie/font/icone — tutto bundlato localmente in build, mai caricato da CDN
* MUST: cifratura a riposo del DB (`sqlcipher3`, fallback `cryptography.Fernet` su file se sqlcipher non disponibile)
* MUST: in ogni fase implementare solo quanto specificato in quella fase — non aggiungere file, astrazioni, dipendenze o funzionalità fuori scope
* NEVER: password/passphrase in log, stdout, file temporanei
* NEVER: dipendenza da Electron
* NEVER: effetti UI neon/cyberpunk/glow fluorescente/scanline/glitch (vedi Design System)

## Stop conditions — fermati e chiedi conferma prima di:

* Aggiungere qualsiasi nuova dipendenza (Python o npm/JS)
* Modificare lo schema della tabella `blocks` una volta creato
* Cancellare o sovrascrivere file esistenti
* Passare alla fase successiva

## Igiene di sessione

* Una fase = una sessione. Fase successiva → nuova sessione, non continuare nella stessa conversazione
* Per correggere una fase già completata usa `/rewind`, non istruzioni correttive a metà conversazione
* `/compact` al 50% di contesto usato, non al 90%
* Output obbligatorio a fine fase: "✅ Fase N completata: \[cosa fatto] — Test manuale: \[come verificare] — Manca: \[cosa resta]"

\---

## Stack tecnico

* Backend: Python 3
* Storage: SQLite + `sqlcipher3` (cifratura at-rest), tabella virtuale FTS5 per ricerca
* Frontend: HTML/JS in `pywebview` (backend `edgechromium`), bundler locale (es. esbuild) per eventuali librerie JS — MAI CDN
* Editor blocchi: `Editor.js` (bundlato localmente)
* Diagrammi: `Mermaid.js` (bundlato localmente), renderizzato client-side da testo sorgente salvato in un blocco tipo `diagram`

## Modello dati

Tabella unica `blocks`:

```
id            TEXT PRIMARY KEY
parent\_id     TEXT NULL
type          TEXT   -- 'page' | 'text' | 'heading' | 'checklist' | 'database' | 'database\_row' | 'diagram' | 'concept'
content       JSON
properties    JSON
schema        JSON NULL   -- solo per type='database'
order\_index   INTEGER
created\_at    TEXT
updated\_at    TEXT
```

Estensioni:

* `blocks\_fts` — tabella virtuale FTS5, sincronizzata via trigger SQLite su INSERT/UPDATE di `content`/`properties`, per ricerca full-text
* `links` (`from\_block\_id`, `to\_block\_id`, `created\_at`) — backlink espliciti, popolati quando il testo di un blocco contiene `\[\[Nome Pagina]]`
* Knowledge booster = blocchi `type='concept'` con `properties = {argomento, confidenza (1-5), prossima\_revisione}`, calcolata con algoritmo SM-2

## Struttura progetto

```
Ledger/
├── main.py
├── db.py                    # CRUD blocchi, query generica con filter/sort/group
├── api.py                   # js\_api: CRUD + query\_blocks + search + spaced\_repetition
├── crypto.py                # apertura/chiusura DB cifrato
├── search.py                # sync trigger FTS5, funzioni di query full-text
├── links.py                 # parsing \[\[wikilink]], popolamento tabella links, query backlink
├── spaced\_repetition.py      # algoritmo SM-2
├── capture.py                # hotkey globale, mini-finestra quick capture
├── review.py                  # aggregazione weekly review (query su blocks esistenti)
├── backup.py                  # export cifrato schedulato
├── frontend/
│   ├── index.html
│   ├── editor.js
│   ├── mermaid\_view.js
│   ├── views/
│   │   ├── table\_view.js
│   │   ├── board\_view.js
│   │   ├── list\_view.js
│   │   └── graph\_view.js       # vista backlink/grafo
│   └── style.css
├── build.spec
└── install.ps1
```

\---

## Fasi (una per sessione, in ordine)

**Fase 1 — Setup + motore dati**
`db.py` (CRUD blocchi generico) + `crypto.py` (DB cifrato, passphrase al primo avvio). Test: creare/leggere blocchi via script, verificare che il file su disco non sia leggibile in chiaro.

**Fase 2 — API layer**
`api.py`: `query\_blocks(parent\_id, filters, sort, group\_by)` generica esposta via `js\_api`. Nessuna funzione specifica tipo `get\_tasks()`.

**Fase 3 — Editor pagina**
Integrazione Editor.js per blocchi testo/heading/checklist. Salvataggio automatico su `content`.

**Fase 4 — Database engine + viste**
UI per definire `schema` di un database. `table\_view.js`, `board\_view.js` (drag\&drop su proprietà select), `list\_view.js`. Test: stessa fonte dati, viste diverse.

**Fase 5 — Ricerca full-text**
Tabella `blocks\_fts` + trigger di sync. Funzione `search(query)` in `search.py`, esposta via API, barra di ricerca globale nel frontend.

**Fase 6 — Backlink**
`links.py`: parsing `\[\[Nome Pagina]]` nel content dei blocchi, popolamento tabella `links`. `graph\_view.js`: sezione a fondo pagina "Menzionato in".

**Fase 6bis — Journaling, Riflessioni e Progetti personali**

* Blocco `type='journal\_entry'`: proprietà `{data (univoca per giorno), mood: select, gratitudine: text\[]}` + `content` per testo libero (Editor.js). All'apertura app, se manca l'entry di oggi, viene creata vuota con un prompt di riflessione random da una lista locale
* Riflessioni periodiche: pagina auto-generata (settimanale/mensile) che aggrega le `journal\_entry` del periodo — stessa logica `query\_blocks` già usata per la weekly review (Fase 11), con 2-3 domande guida fisse (es. "cosa ha funzionato", "cosa cambiare")
* Progetti personali: database "Progetti" con campo aggiuntivo `area` (`personale` | `coding`) — stesso schema di Fase 8, non una tabella nuova, solo un filtro in più
* Collegamento automatico: `\[\[Nome Progetto]]` scritto in una journal\_entry popola il link tramite `links.py` già esistente (Fase 6) — zero logica nuova
* Streak: contatore giorni consecutivi con journal\_entry compilata, calcolato via query su `blocks`, mostrato in home

MUST: nessuna tabella nuova oltre a quanto già in `blocks`/`links` — solo nuovi `type` e proprietà.

**Fase 7 — Knowledge booster**
Schema `concept` (argomento, confidenza, prossima\_revisione) + `spaced\_repetition.py` (SM-2). Vista "Da rivedere oggi" = `query\_blocks` filtrata su `prossima\_revisione <= oggi`.

**Fase 8 — System Design**
Template database "Progetti" (stack, stato, priorità) con pagine figlie Architettura/Decisioni/Vincoli. Blocco `type='diagram'`: testo Mermaid salvato in `content`, renderizzato da `mermaid\_view.js`.

**Fase 9 — Code Planning Mode**
Template pagina pre-strutturato (Contesto → Stack → Fasi → Vincoli). Funzione export: serializza la pagina in `.md` pronto da incollare come CLAUDE.md altrove.

**Fase 10 — Quick capture globale**
`capture.py`: hotkey di sistema (es. libreria hotkey OS-level), mini-finestra pywebview separata per catturare un pensiero/task anche ad app principale chiusa/minimizzata, salvato come blocco in una inbox da triagare dopo.

**Fase 11 — Weekly review automatica**
`review.py`: dashboard che aggrega via `query\_blocks` — task scaduti, concetti da rivedere, pagine modificate ultima settimana. Zero storage nuovo.

**Fase 12 — Backup cifrato locale**
`backup.py`: export periodico/manuale del DB cifrato su path locale o drive esterno scelto dall'utente. Mai upload in rete.

**Fase 13 — Design System**
Vedi sezione dedicata sotto. Applicare a tutte le viste esistenti.

**Fase 14 — Packaging**
`build.spec` (pyinstaller) → `.exe` singolo. `install.ps1` → collegamento `.lnk` su Desktop/Start Menu.

**Fase 15 — Verifica finale**
Checklist: DB illeggibile senza passphrase, ogni vista legge dalla stessa fonte, zero chiamate di rete (verificare con Process Monitor/Wireshark), ricerca full-text funzionante, backlink popolati correttamente, quick capture funziona ad app minimizzata, backup ripristinabile, exe standalone funzionante.

\---

## Design System (vincolante)

* Sfondo: chiaro — bianco puro `#FFFFFF` o quasi-bianco `#FAFAF8`. Mai scuro.
* CTA primario: verde smeraldo `#0F5132`, testo bianco
* Bottoni secondari/elementi: verde outline/ghost (bordo `#0F5132`, testo verde, sfondo trasparente)
* Hover/cursore: SOLO micro-interazioni CSS transition/transform — no WebGL, no particle system, no glow/neon/scanline/glitch. Esempi ammessi: bottone si solleva 2px con ombra leggera + scala 1.02 su hover (transition 150ms ease-out); cursore custom sottile che si allarga leggermente su elementi interattivi, verde a opacità ridotta, mai fluorescente
* Font: monospace per codice/URL, sans-serif neutro self-hosted (es. Inter) per il resto
* Librerie frontend esterne: ammesse SOLO se bundlate localmente in build (npm + bundler), mai import da CDN. Introdurre una libreria di animazione solo se le CSS transition non bastano per l'effetto richiesto
* Vietato: neon, glow fluorescente, scanline, glitch, tema scuro cyberpunk, gradient arcobaleno

## Funzioni boost aggiuntive proposte (solo dopo Fase 15, su richiesta esplicita)

* Tagging multi-tag sui blocchi (cross-cutting, oltre ai backlink)
* Time-tracking per pagina/progetto (durata sessioni di focus come proprietà del blocco)
* Streak/statistiche giornaliere (note create, revisioni completate) — query sullo stesso motore, zero storage nuovo

\---

## Nota per l'agente

Questo prompt è per uno strumento agentico con accesso reale al filesystem. Verifica scope lock, azioni vietate e stop condition prima di eseguire ogni fase. Conferma che i path di progetto corrispondano a quelli reali prima di scrivere file.

