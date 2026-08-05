"""Ricerca full-text su `blocks`, via tabella virtuale FTS5 `blocks_fts`
sincronizzata con trigger SQLite. Nessuna tabella parallela per singolo
tipo di blocco: il testo indicizzato e' estratto genericamente da
content/properties qualunque sia lo `type`.
"""
from __future__ import annotations

import json
import re
import sqlite3

FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS blocks_fts USING fts5(
    block_id UNINDEXED,
    text
);

CREATE TRIGGER IF NOT EXISTS blocks_fts_ai AFTER INSERT ON blocks BEGIN
    INSERT INTO blocks_fts (block_id, text)
    VALUES (new.id, ledger_extract_text(new.content, new.properties));
END;

CREATE TRIGGER IF NOT EXISTS blocks_fts_au AFTER UPDATE ON blocks BEGIN
    DELETE FROM blocks_fts WHERE block_id = old.id;
    INSERT INTO blocks_fts (block_id, text)
    VALUES (new.id, ledger_extract_text(new.content, new.properties));
END;

CREATE TRIGGER IF NOT EXISTS blocks_fts_ad AFTER DELETE ON blocks BEGIN
    DELETE FROM blocks_fts WHERE block_id = old.id;
END;
"""

_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _collect_strings(value, out: list) -> None:
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, dict):
        for v in value.values():
            _collect_strings(v, out)
    elif isinstance(value, list):
        for v in value:
            _collect_strings(v, out)


def _extract_text_udf(content_json: str | None, properties_json: str | None) -> str:
    parts: list = []
    for raw in (content_json, properties_json):
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            continue
        _collect_strings(data, parts)
    return " ".join(parts)


def init_fts_schema(conn: sqlite3.Connection) -> None:
    """Registra la funzione SQL usata dai trigger e crea tabella/trigger.

    La funzione va ri-registrata a ogni apertura di connessione (non e'
    persistita nel file DB), lo schema/i trigger invece si' (idempotenti
    grazie a IF NOT EXISTS).
    """
    conn.create_function("ledger_extract_text", 2, _extract_text_udf)
    conn.executescript(FTS_SCHEMA)
    conn.commit()


def search(conn: sqlite3.Connection, query: str, limit: int = 50) -> list[dict]:
    import db

    tokens = _WORD_RE.findall(query)
    if not tokens:
        return []
    match_expr = " ".join(f'"{t}"' for t in tokens)

    rows = conn.execute(
        """
        SELECT block_id, snippet(blocks_fts, 1, '[', ']', '...', 12) AS snippet
        FROM blocks_fts
        WHERE blocks_fts MATCH ?
        ORDER BY rank
        LIMIT ?
        """,
        (match_expr, limit),
    ).fetchall()

    results = []
    for r in rows:
        block = db.get_block(conn, r["block_id"])
        if block:
            block["snippet"] = r["snippet"]
            results.append(block)
    return results
