"""Weekly review automatica: dashboard che aggrega dati gia' esistenti
via query_blocks. Zero storage nuovo.
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta, timezone

import db
import spaced_repetition


def overdue_tasks(conn: sqlite3.Connection) -> list[dict]:
    """Righe di un qualsiasi database con un campo 'date' nello schema
    la cui data e' passata. Generico, nessuna logica per singolo database.
    """
    rows = db.query_blocks(conn, filters=[{"field": "type", "op": "=", "value": "database_row"}])
    today = date.today().isoformat()

    overdue = []
    for row in rows:
        parent = db.get_block(conn, row["parent_id"]) if row.get("parent_id") else None
        if not parent or not parent.get("schema"):
            continue
        date_fields = [f["nome"] for f in parent["schema"].get("campi", []) if f["tipo"] == "date"]
        for fname in date_fields:
            value = (row.get("properties") or {}).get(fname)
            if value and value < today:
                overdue.append(
                    {
                        **row,
                        "_scadenza_campo": fname,
                        "_scadenza_valore": value,
                        "_database_titolo": (parent.get("content") or {}).get("title"),
                    }
                )
                break
    return overdue


def concepts_due(conn: sqlite3.Connection) -> list[dict]:
    return spaced_repetition.due_today(conn)


def pages_modified_last_week(conn: sqlite3.Connection) -> list[dict]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    pages = db.query_blocks(conn, filters=[{"field": "type", "op": "=", "value": "page"}])
    recent = [p for p in pages if p["updated_at"] >= cutoff]
    recent.sort(key=lambda p: p["updated_at"], reverse=True)
    return recent


def weekly_review(conn: sqlite3.Connection) -> dict:
    return {
        "task_scaduti": overdue_tasks(conn),
        "concetti_da_rivedere": concepts_due(conn),
        "pagine_modificate": pages_modified_last_week(conn),
    }
