"""Journaling, riflessioni periodiche, streak. Nessuna tabella nuova:
solo type='journal_entry' e type='page' (properties.tipo='riflessione')
sulla tabella `blocks` esistente, con query_blocks come unico accesso.
"""
from __future__ import annotations

import calendar
import random
import sqlite3
from datetime import date, timedelta

import db

REFLECTION_PROMPTS = [
    "Cosa ti ha sorpreso oggi?",
    "Quale piccola cosa ha reso oggi migliore?",
    "Cosa avresti voluto fare diversamente oggi?",
    "Di cosa sei orgoglioso/a oggi?",
    "Cosa ti sta preoccupando in questo momento?",
    "Cosa hai imparato oggi?",
    "Qual e' stato il momento piu' difficile della giornata?",
    "Per cosa sei grato/a in questo momento?",
]

GUIDE_QUESTIONS = [
    "Cosa ha funzionato in questo periodo?",
    "Cosa vorresti cambiare?",
    "Cosa hai imparato?",
]


def ensure_today_entry(conn: sqlite3.Connection) -> dict:
    today = date.today().isoformat()
    existing = db.query_blocks(
        conn,
        filters=[
            {"field": "type", "op": "=", "value": "journal_entry"},
            {"field": "properties.data", "op": "=", "value": today},
        ],
    )
    if existing:
        return existing[0]

    block_id = db.create_block(
        conn,
        type="journal_entry",
        parent_id=None,
        content={"prompt": random.choice(REFLECTION_PROMPTS)},
        properties={"data": today, "mood": None, "gratitudine": []},
    )
    return db.get_block(conn, block_id)


def is_entry_filled(conn: sqlite3.Connection, entry_id: str) -> bool:
    return len(db.list_blocks(conn, entry_id)) > 0


def current_streak(conn: sqlite3.Connection) -> int:
    entries = db.query_blocks(conn, filters=[{"field": "type", "op": "=", "value": "journal_entry"}])
    filled_dates = {
        e["properties"]["data"]
        for e in entries
        if e.get("properties", {}).get("data") and is_entry_filled(conn, e["id"])
    }

    streak = 0
    day = date.today()
    while day.isoformat() in filled_dates:
        streak += 1
        day -= timedelta(days=1)
    return streak


def _week_bounds(today: date) -> tuple[date, date, str, str]:
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    key = f"settimana-{start.isocalendar().year}-W{start.isocalendar().week:02d}"
    title = f"Riflessione settimanale — {start.strftime('%d/%m')}–{end.strftime('%d/%m/%Y')}"
    return start, end, key, title


def _month_bounds(today: date) -> tuple[date, date, str, str]:
    start = today.replace(day=1)
    end = start.replace(day=calendar.monthrange(start.year, start.month)[1])
    key = f"mese-{start.year}-{start.month:02d}"
    title = f"Riflessione mensile — {start.strftime('%B %Y')}"
    return start, end, key, title


def ensure_reflection_page(conn: sqlite3.Connection, period: str) -> dict:
    if period not in ("weekly", "monthly"):
        raise ValueError(f"Periodo non valido: {period}")

    today = date.today()
    start, end, key, title = _week_bounds(today) if period == "weekly" else _month_bounds(today)

    existing = db.query_blocks(
        conn,
        parent_id=None,
        filters=[
            {"field": "type", "op": "=", "value": "page"},
            {"field": "properties.tipo", "op": "=", "value": "riflessione"},
            {"field": "properties.periodo_key", "op": "=", "value": key},
        ],
    )
    if existing:
        return existing[0]

    entries = [
        e
        for e in db.query_blocks(conn, filters=[{"field": "type", "op": "=", "value": "journal_entry"}])
        if e.get("properties", {}).get("data") and start.isoformat() <= e["properties"]["data"] <= end.isoformat()
    ]
    entries.sort(key=lambda e: e["properties"]["data"])

    page_id = db.create_block(
        conn,
        type="page",
        parent_id=None,
        content={"title": title},
        properties={"tipo": "riflessione", "periodo": period, "periodo_key": key},
    )

    order = 0
    db.create_block(
        conn,
        type="heading",
        parent_id=page_id,
        content={"text": "Voci di journal in questo periodo", "level": 2},
        order_index=order,
    )
    order += 1

    if entries:
        lines = []
        for e in entries:
            props = e["properties"]
            mood = props.get("mood") or "—"
            gratitudine = ", ".join(props.get("gratitudine") or []) or "—"
            lines.append(f"{props['data']}: mood {mood}, gratitudine: {gratitudine}")
        summary = "\n".join(lines)
    else:
        summary = "Nessuna voce di journal in questo periodo."
    db.create_block(
        conn, type="text", parent_id=page_id, content={"text": summary}, order_index=order
    )
    order += 1

    for question in GUIDE_QUESTIONS:
        db.create_block(
            conn,
            type="heading",
            parent_id=page_id,
            content={"text": question, "level": 3},
            order_index=order,
        )
        order += 1
        db.create_block(conn, type="text", parent_id=page_id, content={"text": ""}, order_index=order)
        order += 1

    return db.get_block(conn, page_id)
