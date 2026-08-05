# Sicurezza

## Modello di minaccia

Ledger protegge **un file di note contro chi ottiene quel file**: backup finiti
su un disco esterno, un laptop rubato, un vecchio hard disk rivenduto, una
cartella sincronizzata per sbaglio.

Ledger **non** protegge contro chi controlla il computer mentre lo stai usando.
Con il vault aperto le note sono in chiaro nella memoria del processo. Un
malware che gira col tuo utente le legge. Nessuna applicazione desktop può
evitarlo, e va detto invece di lasciarlo intendere.

## Come funziona la cifratura

| | |
|---|---|
| Derivazione chiave | PBKDF2-HMAC-SHA256, 480 000 iterazioni, salt casuale da 16 byte |
| Cifratura | Fernet (AES-128-CBC + HMAC-SHA256 per l'autenticazione) |
| Dove sta il database | **Solo in memoria** (`sqlite3` `:memory:` con `serialize`/`deserialize`) |
| Cosa tocca il disco | Unicamente il blob cifrato, riscritto per intero a ogni salvataggio |

Il file `.salt` sta accanto al `.db` e **non è un segreto**, ma senza di esso il
vault è indecifrabile. Copiali sempre insieme.

Nessun recupero password: se dimentichi la passphrase, le note sono perse.
È il comportamento voluto.

## Limiti noti

**Nessun limite ai tentativi.** Chi ottiene il file può provare passphrase
offline quanto vuole. Le 480 000 iterazioni rendono ogni tentativo costoso, ma
una passphrase debole cade comunque. Il minimo di 8 caratteri è un argine
basso: usane una lunga.

**Iterazioni fissate nel formato.** `KDF_ITERATIONS` è una costante. Alzarlo
renderebbe indecifrabili i vault esistenti, che segnalerebbero "passphrase
errata". Serve una migrazione prima di cambiarlo.

**Finestra di perdita fino a un minuto.** Il database vive in memoria; su disco
viene cifrato ogni 60 secondi se qualcosa è cambiato, alla chiusura della
finestra e a ogni backup manuale. Un arresto anomalo perde quindi al massimo
l'ultimo minuto di scrittura, non l'intera sessione.

**Server HTTP su loopback.** pywebview avvia un server Bottle su
`127.0.0.1:<porta casuale>` ogni volta che carica file locali — non è
disattivabile (`webview/__init__.py`, il server parte se ci sono URL locali,
anche con `http_server=False`). Conseguenze:

- serve i file del frontend *senza autenticazione* a qualsiasi processo locale.
  Sono gli stessi file già contenuti nell'eseguibile: non c'è nulla di segreto;
- espone `POST /js_api/<uuid4>`, cioè il ponte verso Python, con
  `Access-Control-Allow-Origin: *`. È protetto solo dall'UUID nel percorso
  (122 bit, non indovinabile), e l'ascolto è limitato a loopback: non è
  raggiungibile dalla rete. Resta un'esposizione locale di cui è giusto sapere.

**Content-Security-Policy.** Le due pagine dichiarano `default-src 'none'` con
`connect-src 'none'`: nessuna origine esterna è caricabile e la pagina non può
aprire `fetch`, XHR o WebSocket verso nessuno, loopback compreso. Il ponte
js_api non passa da lì (usa la messaggistica nativa di WebView2), quindi resta
funzionante. È una rete di sicurezza contro una dipendenza aggiunta per errore
con un riferimento a CDN: verrebbe bloccata dal motore, non solo scoraggiata
dalle convenzioni del progetto.

**La chiave resta in memoria** per tutta la sessione: serve a ogni salvataggio.
Non è protetta da swap del sistema operativo.

**Cancellazione non garantita.** Sostituire il vault non elimina i blocchi
precedenti su SSD (wear leveling) o file system journaled.

**Eseguibile non firmato.** Senza certificato di code signing, Windows
SmartScreen mostra un avviso al primo avvio. Verifica il checksum SHA-256
pubblicato nella release.

**Hotkey globale.** La quick capture registra un hook di tastiera di sistema
(libreria `keyboard`). Serve solo a intercettare `Ctrl+Shift+Space`: nessun
tasto viene registrato o salvato. Alcuni antivirus segnalano comunque la
tecnica, che è la stessa di un keylogger.

## Rete

Ledger non effettua alcuna connessione in uscita. Nessuna telemetria, nessun
aggiornamento automatico, nessun CDN: Editor.js e Mermaid sono compilati
localmente dentro l'eseguibile.

Verificabile:

```powershell
# nessuna connessione in uscita mentre l'app gira
Get-Process Ledger | ForEach-Object { Get-NetTCPConnection -OwningProcess $_.Id }
```

Compare solo la porta di ascolto su `127.0.0.1` descritta sopra.

## Se hai usato una versione precedente alla 1.0

Le versioni fino a `0.x` decifravano il database in un file temporaneo che
restava in chiaro in `%TEMP%` per tutta la sessione, e **sopravviveva a un
arresto anomalo**. Controlla e ripulisci:

```powershell
Get-ChildItem $env:TEMP\*.sqlite | Remove-Item
```

Dalla 1.0 quei file non vengono più creati.

## Segnalare una vulnerabilità

Apri una issue per problemi non sensibili. Per vulnerabilità sfruttabili usa
i [GitHub Security Advisories](https://docs.github.com/code-security/security-advisories/guidance-on-reporting-and-writing/privately-reporting-a-security-vulnerability)
in privato, invece della issue pubblica.
