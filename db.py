"""CRUD generico sull'unica tabella `blocks`.

Ogni feature (task, database, backlink, spaced repetition, ricerca) e'
uno schema o una query su questa tabella, mai una tabella dedicata.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS blocks (
    id            TEXT PRIMARY KEY,
    parent_id     TEXT NULL,
    type          TEXT NOT NULL,
    content       JSON,
    properties    JSON,
    schema        JSON NULL,
    order_index   INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    FOREIGN KEY (parent_id) REFERENCES blocks(id)
);
CREATE INDEX IF NOT EXISTS idx_blocks_parent ON blocks(parent_id);
CREATE INDEX IF NOT EXISTS idx_blocks_type ON blocks(type);
"""

_JSON_FIELDS = ("content", "properties", "schema")
_MUTABLE_FIELDS = {"parent_id", "type", "content", "properties", "schema", "order_index"}

UNSET = object()  # distingue "parent_id non specificato" da "parent_id=None (radice)"


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_block(
    conn: sqlite3.Connection,
    type: str,
    parent_id: str | None = None,
    content: dict | list | None = None,
    properties: dict | None = None,
    schema: dict | None = None,
    order_index: int = 0,
    block_id: str | None = None,
) -> str:
    block_id = block_id or str(uuid.uuid4())
    now = _now()
    conn.execute(
        """
        INSERT INTO blocks
            (id, parent_id, type, content, properties, schema, order_index, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            block_id,
            parent_id,
            type,
            json.dumps(content) if content is not None else None,
            json.dumps(properties) if properties is not None else None,
            json.dumps(schema) if schema is not None else None,
            order_index,
            now,
            now,
        ),
    )
    conn.commit()
    return block_id


def get_block(conn: sqlite3.Connection, block_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM blocks WHERE id = ?", (block_id,)).fetchone()
    return row_to_dict(row) if row else None


def list_blocks(conn: sqlite3.Connection, parent_id: str | None = None) -> list[dict]:
    if parent_id is None:
        rows = conn.execute("SELECT * FROM blocks ORDER BY order_index").fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM blocks WHERE parent_id = ? ORDER BY order_index",
            (parent_id,),
        ).fetchall()
    return [row_to_dict(r) for r in rows]


def update_block(conn: sqlite3.Connection, block_id: str, **fields) -> None:
    if not fields:
        return
    unknown = set(fields) - _MUTABLE_FIELDS
    if unknown:
        raise ValueError(f"Campi non validi: {unknown}")

    columns = []
    values = []
    for key, value in fields.items():
        if key in _JSON_FIELDS and value is not None:
            value = json.dumps(value)
        columns.append(f"{key} = ?")
        values.append(value)
    columns.append("updated_at = ?")
    values.append(_now())
    values.append(block_id)

    conn.execute(f"UPDATE blocks SET {', '.join(columns)} WHERE id = ?", values)
    conn.commit()


def delete_block(conn: sqlite3.Connection, block_id: str) -> None:
    conn.execute("DELETE FROM blocks WHERE id = ?", (block_id,))
    conn.commit()


def descendant_ids(conn: sqlite3.Connection, block_id: str) -> list[str]:
    """Tutti gli id nel sottoalbero di `block_id`, incluso se stesso.
    Ordine figli-prima-dei-genitori, cosi' la cancellazione non lascia
    mai righe orfane a meta' operazione.
    """
    collected: list[str] = []
    frontier = [block_id]
    while frontier:
        current = frontier.pop()
        collected.append(current)
        rows = conn.execute("SELECT id FROM blocks WHERE parent_id = ?", (current,)).fetchall()
        frontier.extend(r["id"] for r in rows)
    collected.reverse()
    return collected


def delete_block_tree(conn: sqlite3.Connection, block_id: str) -> list[str]:
    """Cancella un blocco e tutta la sua discendenza. Ritorna gli id rimossi."""
    ids = descendant_ids(conn, block_id)
    conn.executemany("DELETE FROM blocks WHERE id = ?", [(i,) for i in ids])
    conn.commit()
    return ids


def row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    for key in _JSON_FIELDS:
        if d.get(key):
            d[key] = json.loads(d[key])
    return d


def query_blocks(
    conn: sqlite3.Connection,
    parent_id=UNSET,
    filters: list[dict] | None = None,
    sort: list[dict] | None = None,
    group_by: str | None = None,
):
    """Query generica sulla tabella blocks. Nessuna funzione dedicata per
    tipo (niente get_tasks/get_pages): ogni vista passa da qui.

    parent_id: UNSET = non filtrare, None = solo blocchi radice, altrimenti
        id del genitore.
    filters: lista di {"field", "op", "value"}. field puo' essere una
        colonna diretta (type, parent_id, order_index, ...) o un path
        dentro content/properties/schema (es. "properties.stato").
        op: "=", "!=", "<", "<=", ">", ">=", "like", "in".
    sort: lista di {"field", "dir"} con stesso field mapping di filters,
        applicata in ordine (primo criterio = priorita' piu' alta).
    group_by: field (stesso mapping) -> ritorna dict {valore: [blocchi]}
        invece di una lista piatta.
    """
    sql = "SELECT * FROM blocks"
    params: list = []
    if parent_id is not UNSET:
        if parent_id is None:
            sql += " WHERE parent_id IS NULL"
        else:
            sql += " WHERE parent_id = ?"
            params.append(parent_id)

    rows = conn.execute(sql, params).fetchall()
    blocks = [row_to_dict(r) for r in rows]

    for f in filters or []:
        blocks = [b for b in blocks if _match_filter(b, f)]

    for s in reversed(sort or []):
        field = s["field"]
        reverse = s.get("dir", "asc") == "desc"
        blocks.sort(key=lambda b: _sort_key(_get_field(b, field)), reverse=reverse)

    if group_by:
        grouped: dict = {}
        for b in blocks:
            grouped.setdefault(_get_field(b, group_by), []).append(b)
        return grouped

    return blocks


def _get_field(block: dict, field: str):
    parts = field.split(".")
    value = block.get(parts[0])
    for p in parts[1:]:
        if not isinstance(value, dict):
            return None
        value = value.get(p)
    return value


def _match_filter(block: dict, f: dict) -> bool:
    value = _get_field(block, f["field"])
    op = f.get("op", "=")
    target = f.get("value")
    if op == "=":
        return value == target
    if op == "!=":
        return value != target
    if op == "<":
        return value is not None and value < target
    if op == "<=":
        return value is not None and value <= target
    if op == ">":
        return value is not None and value > target
    if op == ">=":
        return value is not None and value >= target
    if op == "like":
        return value is not None and str(target).strip("%").lower() in str(value).lower()
    if op == "in":
        return value in target
    raise ValueError(f"Operatore non supportato: {op}")


def _sort_key(value):
    """Chiave d'ordinamento totale anche su valori eterogenei.

    Le properties sono JSON libero: la stessa chiave puo' essere numero in
    una riga e stringa in un'altra. Confrontarle direttamente solleverebbe
    TypeError e farebbe fallire la vista intera, quindi si ordina prima per
    famiglia di tipo (vuoti, numeri, testo) e poi per valore.
    """
    if value is None:
        return (2, 0.0, "")
    if isinstance(value, bool):
        return (1, float(value), "")
    if isinstance(value, (int, float)):
        return (0, float(value), "")
    if isinstance(value, str):
        return (1, 0.0, value.lower())
    return (1, 0.0, str(value))
