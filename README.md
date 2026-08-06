# Ledger

Notes, journal, and projects in a single desktop app for Windows. Everything
stays on your machine, encrypted. No account, no server, no network connection.

*Vibe-coded: planned as a phased prompt and built iteratively with Claude Code.
See [How it's built](#how-its-built) below.*

## What it does

- **Block-based pages** — text, headings, lists, checklists, quotes, code,
  tables, and Mermaid diagrams
- **Databases** with any schema you want, viewable as a table, kanban board, or list
- **Full-text search** across everything you've written
- **Backlinks** — write `[[Page name]]` and the referenced page shows who links to it
- **Daily journal** with mood, gratitude, and a streak counter
- **Scheduled review** of concepts, using the SM-2 algorithm
- **Projects** with status, priority, and Architecture / Decisions / Constraints pages
- **Quick capture** — `Ctrl+Shift+Space` from any application, with Ledger
  minimized or behind other windows: lands in an inbox to triage later
- **Weekly digest** — deadlines, reviews due, and recently touched pages
- **Encrypted backup** to a folder you choose, including an external drive
- **Export** any page to Markdown

Everything rests on a single `blocks` table: every feature is a query against
it, not a dedicated table.

## Installation

Download `Ledger.exe` from the latest [release](../../releases) and run:

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1
```

This copies the program to `%LOCALAPPDATA%\Programs\Ledger` and creates
shortcuts on the Desktop and Start menu. No admin rights required, and nothing
is written outside your user profile.

To remove it: `install.ps1 -Uninstall`. Your notes are **not** deleted.

You can also just run `Ledger.exe` directly, with no installation.

> **On first launch, Windows SmartScreen shows a warning**: the executable
> isn't signed with a commercial certificate. Compare the SHA-256 checksum
> against the one published in the release, or build it yourself from source.

## Where your data lives

| | |
|---|---|
| Encrypted vault | `%APPDATA%\Ledger\ledger.db` |
| Key salt | `%APPDATA%\Ledger\ledger.db.salt` |

You need both: if you copy the vault, copy the `.salt` file too.

**There is no passphrase recovery.** If you forget it, your notes are
unreadable by anyone, including you. Back up accordingly.

The security model, including its explicit limitations, is described in
[SECURITY.md](SECURITY.md). Read it before trusting it with anything sensitive.

## Building from source

You'll need Python 3.11+ and Node 18+.

```bash
pip install -r requirements.txt
npm install

npm run build                          # bundles Editor.js and Mermaid locally
pyinstaller build.spec --noconfirm     # produces dist/Ledger.exe
```

For development, without packaging:

```bash
npm run build
python main.py
```

In development the vault sits next to the source; in the packaged executable
it lives under `%APPDATA%`.

## Tests

Standard library only, no GUI involved: they cover encryption, the block
engine, search, backlinks, SM-2, journal, export, and backup.

```bash
python -m unittest discover -s tests -v
```

## How it's built

Planned as a phased CLAUDE.md prompt and implemented with Claude Code —
architecture, constraints, and stop conditions written up front, executed
phase by phase.

Python + [pywebview](https://pywebview.flowrl.com/) (WebView2), no Electron.
The frontend is HTML/CSS/JS bundled with esbuild: libraries ship inside the
executable and are never fetched from a CDN.

```
main.py              startup, window, paths
crypto.py            encrypted vault, in-memory DB
db.py                CRUD and generic queries over the blocks table
api.py               bridge to the frontend
search.py            FTS5 index and search
links.py             [[wikilink]] backlinks
journal.py           journal, reflections, streak
spaced_repetition.py SM-2 algorithm
projects.py          projects and linked pages
planning.py          plan model and Markdown export
review.py            weekly digest aggregation
capture.py           global hotkey and capture window
backup.py            encrypted copy to a local folder
frontend/            UI
tests/               data engine and encryption tests
```

## License

MIT — see [LICENSE](LICENSE).
