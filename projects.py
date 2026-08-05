"""System Design: template database 'Progetti' con pagine figlie
Architettura/Decisioni/Vincoli. Nessuna tabella nuova: e' un normale
type='database' + type='database_row' + type='page' su `blocks`.
"""
from __future__ import annotations

import sqlite3

import db

PROJECT_SCHEMA = {
    "campi": [
        {"nome": "Nome", "tipo": "text"},
        {"nome": "Stack", "tipo": "text"},
        {"nome": "Stato", "tipo": "select", "opzioni": ["Da iniziare", "In corso", "In pausa", "Completato"]},
        {"nome": "Priorita", "tipo": "select", "opzioni": ["Bassa", "Media", "Alta"]},
        {"nome": "Area", "tipo": "select", "opzioni": ["personale", "coding"]},
    ]
}

CHILD_PAGES = ["Architettura", "Decisioni", "Vincoli"]


def ensure_projects_database(conn: sqlite3.Connection) -> dict:
    existing = db.query_blocks(
        conn,
        parent_id=None,
        filters=[
            {"field": "type", "op": "=", "value": "database"},
            {"field": "properties.template", "op": "=", "value": "progetti"},
        ],
    )
    if existing:
        return existing[0]

    db_id = db.create_block(
        conn,
        type="database",
        parent_id=None,
        content={"title": "Progetti"},
        properties={"template": "progetti"},
        schema=PROJECT_SCHEMA,
    )
    return db.get_block(conn, db_id)


def list_projects(conn: sqlite3.Connection) -> list[dict]:
    """Righe del database Progetti. Lista vuota se il template non esiste
    ancora: consultare l'elenco non deve crearlo.
    """
    existing = db.query_blocks(
        conn,
        parent_id=None,
        filters=[
            {"field": "type", "op": "=", "value": "database"},
            {"field": "properties.template", "op": "=", "value": "progetti"},
        ],
    )
    if not existing:
        return []
    return db.query_blocks(
        conn,
        parent_id=existing[0]["id"],
        sort=[{"field": "order_index", "dir": "asc"}],
    )


def create_project(conn: sqlite3.Connection, nome: str) -> dict:
    projects_db = ensure_projects_database(conn)

    properties = {"Nome": nome, "Stack": "", "Stato": None, "Priorita": None, "Area": None}
    row_id = db.create_block(
        conn,
        type="database_row",
        parent_id=projects_db["id"],
        properties=properties,
    )

    pagine = {}
    for label in CHILD_PAGES:
        page_id = db.create_block(
            conn,
            type="page",
            parent_id=row_id,
            content={"title": f"{nome} — {label}"},
        )
        pagine[label.lower()] = page_id

    db.update_block(conn, row_id, properties={**properties, "pagine": pagine})
    return db.get_block(conn, row_id)
