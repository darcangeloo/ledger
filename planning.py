"""Code Planning Mode: template pagina pre-strutturato + export in .md.
Nessuna tabella nuova: solo un normale type='page' con figli precompilati.
"""
from __future__ import annotations

import sqlite3

import db

SECTIONS = ["Contesto", "Stack", "Fasi", "Vincoli"]


def create_code_planning_page(conn: sqlite3.Connection) -> dict:
    page_id = db.create_block(
        conn,
        type="page",
        parent_id=None,
        content={"title": "Nuovo piano"},
        properties={"tipo": "code_planning"},
    )

    order = 0
    for section in SECTIONS:
        db.create_block(
            conn,
            type="heading",
            parent_id=page_id,
            content={"text": section, "level": 2},
            order_index=order,
        )
        order += 1
        db.create_block(conn, type="text", parent_id=page_id, content={"text": ""}, order_index=order)
        order += 1

    return db.get_block(conn, page_id)


def _item_text(item) -> str:
    """Le voci di elenco sono stringhe nelle versioni vecchie di Editor.js
    e oggetti {content, items} in quelle nuove."""
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return item.get("content") or item.get("text") or ""
    return ""


def _list_to_markdown(content: dict, depth: int = 0) -> list[str]:
    ordered = content.get("style") == "ordered"
    lines = []
    for index, item in enumerate(content.get("items", []), start=1):
        bullet = f"{index}." if ordered else "-"
        lines.append(f"{'  ' * depth}{bullet} {_item_text(item)}")
        if isinstance(item, dict) and item.get("items"):
            lines.extend(
                _list_to_markdown({"style": content.get("style"), "items": item["items"]}, depth + 1)
            )
    return lines


def _block_to_markdown(block: dict) -> str:
    content = block.get("content") or {}
    btype = block["type"]

    if btype == "heading":
        level = content.get("level", 2)
        return f"{'#' * level} {content.get('text', '')}"

    if btype == "checklist":
        lines = []
        for item in content.get("items", []):
            mark = "x" if item.get("checked") else " "
            lines.append(f"- [{mark}] {item.get('text', '')}")
        return "\n".join(lines)

    if btype == "list":
        return "\n".join(_list_to_markdown(content))

    if btype == "quote":
        lines = [f"> {line}" for line in content.get("text", "").split("\n")]
        if content.get("caption"):
            lines.append(f">\n> — {content['caption']}")
        return "\n".join(lines)

    if btype == "code":
        return f"```\n{content.get('code', '')}\n```"

    if btype == "delimiter":
        return "---"

    if btype == "table":
        rows = content.get("content", [])
        if not rows:
            return ""
        lines = ["| " + " | ".join(rows[0]) + " |"]
        lines.append("|" + "---|" * len(rows[0]))
        for row in rows[1:]:
            lines.append("| " + " | ".join(row) + " |")
        return "\n".join(lines)

    if btype == "diagram":
        return f"```mermaid\n{content.get('source', '')}\n```"

    return content.get("text", "")


def export_to_markdown(conn: sqlite3.Connection, page_id: str) -> str:
    page = db.get_block(conn, page_id)
    if page is None:
        raise ValueError(f"Blocco non trovato: {page_id}")

    title = (page.get("content") or {}).get("title", "Senza titolo")
    children = db.list_blocks(conn, page_id)

    parts = [f"# {title}", ""]
    for block in children:
        parts.append(_block_to_markdown(block))
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"
