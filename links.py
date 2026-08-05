"""Backlink: parsing `[[Nome Pagina]]` nel content dei blocchi e
popolamento della tabella `links`. Nessuna logica per tipo di blocco:
qualunque blocco puo' contenere wikilink nel proprio content.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone

import db

LINKS_SCHEMA = """
CREATE TABLE IF NOT EXISTS links (
    from_block_id TEXT NOT NULL,
    to_block_id   TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    PRIMARY KEY (from_block_id, to_block_id),
    FOREIGN KEY (from_block_id) REFERENCES blocks(id),
    FOREIGN KEY (to_block_id) REFERENCES blocks(id)
);
CREATE INDEX IF NOT EXISTS idx_links_to ON links(to_block_id);
"""

WIKILINK_RE = re.compile(r"\[\[([^\[\]]+)\]\]")


def init_links_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(LINKS_SCHEMA)
    conn.commit()


def _collect_strings(value, out: list) -> None:
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, dict):
        for v in value.values():
            _collect_strings(v, out)
    elif isinstance(value, list):
        for v in value:
            _collect_strings(v, out)


def extract_wikilink_titles(block: dict) -> set[str]:
    parts: list = []
    _collect_strings(block.get("content"), parts)
    names = set()
    for text in parts:
        for name in WIKILINK_RE.findall(text):
            names.add(name.strip())
    return names


def _find_page_by_title(conn: sqlite3.Connection, title: str) -> str | None:
    row = conn.execute(
        "SELECT id FROM blocks WHERE type = 'page' AND json_extract(content, '$.title') = ? COLLATE NOCASE",
        (title,),
    ).fetchone()
    return row["id"] if row else None


def sync_links_for_block(conn: sqlite3.Connection, block: dict) -> None:
    """Ricalcola i link uscenti di `block` in base ai wikilink nel content."""
    titles = extract_wikilink_titles(block)

    conn.execute("DELETE FROM links WHERE from_block_id = ?", (block["id"],))
    now = datetime.now(timezone.utc).isoformat()
    for title in titles:
        target_id = _find_page_by_title(conn, title)
        if target_id and target_id != block["id"]:
            conn.execute(
                "INSERT OR IGNORE INTO links (from_block_id, to_block_id, created_at) VALUES (?, ?, ?)",
                (block["id"], target_id, now),
            )
    conn.commit()


def delete_links_for_block(conn: sqlite3.Connection, block_id: str) -> None:
    conn.execute("DELETE FROM links WHERE from_block_id = ? OR to_block_id = ?", (block_id, block_id))
    conn.commit()


def backlinks_for(conn: sqlite3.Connection, block_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT b.* FROM links l
        JOIN blocks b ON b.id = l.from_block_id
        WHERE l.to_block_id = ?
        ORDER BY l.created_at
        """,
        (block_id,),
    ).fetchall()
    return [db.row_to_dict(r) for r in rows]
