"""Knowledge booster: type='concept' su `blocks` + algoritmo SM-2.
Nessuna tabella nuova: tutto in properties, query generica per il
ripasso dovuto.
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import db

MIN_EASINESS = 1.3
DEFAULT_EASINESS = 2.5


def _today() -> str:
    return date.today().isoformat()


def create_concept(conn: sqlite3.Connection, argomento: str) -> dict:
    block_id = db.create_block(
        conn,
        type="concept",
        parent_id=None,
        content={"argomento": argomento},
        properties={
            "argomento": argomento,
            "confidenza": None,
            "prossima_revisione": _today(),
            "ef": DEFAULT_EASINESS,
            "intervallo": 0,
            "ripetizioni": 0,
        },
    )
    return db.get_block(conn, block_id)


def due_today(conn: sqlite3.Connection) -> list[dict]:
    today = _today()
    return db.query_blocks(
        conn,
        filters=[
            {"field": "type", "op": "=", "value": "concept"},
            {"field": "properties.prossima_revisione", "op": "<=", "value": today},
        ],
        sort=[{"field": "properties.prossima_revisione", "dir": "asc"}],
    )


def review_concept(conn: sqlite3.Connection, concept_id: str, confidenza: int) -> dict:
    """Applica SM-2. confidenza 1-5 (1 = non ricordato, 5 = perfetto)."""
    block = db.get_block(conn, concept_id)
    props = block.get("properties") or {}

    ef = props.get("ef", DEFAULT_EASINESS)
    intervallo = props.get("intervallo", 0)
    ripetizioni = props.get("ripetizioni", 0)

    quality = max(0, min(5, confidenza))

    if quality < 3:
        ripetizioni = 0
        intervallo = 1
    else:
        if ripetizioni == 0:
            intervallo = 1
        elif ripetizioni == 1:
            intervallo = 6
        else:
            intervallo = round(intervallo * ef)
        ripetizioni += 1

    ef = ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    ef = max(ef, MIN_EASINESS)

    prossima_revisione = (date.today() + timedelta(days=intervallo)).isoformat()

    new_properties = {
        **props,
        "confidenza": confidenza,
        "ef": round(ef, 2),
        "intervallo": intervallo,
        "ripetizioni": ripetizioni,
        "prossima_revisione": prossima_revisione,
    }
    db.update_block(conn, concept_id, properties=new_properties)
    return db.get_block(conn, concept_id)
