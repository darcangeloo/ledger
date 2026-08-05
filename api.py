"""Livello API esposto al frontend come js_api (pywebview).

Solo CRUD generico + query_blocks. Niente funzioni dedicate per tipo
(no get_tasks, no get_pages): ogni vista/feature passa da query_blocks
con i propri filtri.

Ogni metodo che tocca il DB passa da `_conn`, che fallisce con un
messaggio leggibile se il vault non e' aperto: senza quel controllo una
chiamata anticipata (quick capture prima dello sblocco) arriverebbe al
frontend come traceback, e il testo catturato andrebbe perso in silenzio.
"""
from __future__ import annotations

import os
import sqlite3

import db
import backup
import crypto
import journal
import links
import planning
import projects
import review
import search as search_module
import spaced_repetition
from crypto import (
    EncryptedDatabase,
    VaultCorruptedError,
    WeakPassphraseError,
    WrongPassphraseError,
)

DB_PATH = "ledger.db"


class VaultNotOpenError(RuntimeError):
    """Chiamata API arrivata prima dello sblocco del vault."""


class Api:
    def __init__(self, db_path: str = DB_PATH):
        self._edb = EncryptedDatabase(db_path)
        self._dirty = False

    # --- accesso al DB ---

    @property
    def _conn(self) -> sqlite3.Connection:
        conn = self._edb.conn
        if conn is None:
            raise VaultNotOpenError("Vault non aperto: sblocca Ledger prima di scrivere.")
        return conn

    def _touch(self) -> None:
        """Segna che ci sono modifiche non ancora cifrate su disco."""
        self._dirty = True

    # --- lifecycle / cifratura ---

    def is_first_run(self) -> bool:
        return crypto.is_first_run(self._edb.db_path)

    def is_open(self) -> bool:
        return self._edb.conn is not None

    def open_vault(self, passphrase: str) -> dict:
        # Gli errori tornano al frontend come testo: mai la passphrase, mai
        # una traccia di stack.
        if self._edb.conn is not None:
            # Riaprire sopra una sessione viva scarterebbe le modifiche
            # ancora solo in memoria, e al primo avvio rigenererebbe il
            # salt rendendo indecifrabile quanto gia' salvato.
            return {"ok": True, "already_open": True}
        try:
            conn = self._edb.open(passphrase)
        except WeakPassphraseError as exc:
            return {"ok": False, "error": str(exc)}
        except WrongPassphraseError:
            return {"ok": False, "error": "Passphrase errata."}
        except VaultCorruptedError as exc:
            return {"ok": False, "error": str(exc)}
        except OSError:
            return {"ok": False, "error": "Impossibile leggere il file del vault."}
        db.init_schema(conn)
        search_module.init_fts_schema(conn)
        links.init_links_schema(conn)
        return {"ok": True}

    def save_vault(self) -> dict:
        if self._edb.conn is None:
            return {"ok": False, "error": "Vault non aperto."}
        self._edb.save()
        self._dirty = False
        return {"ok": True}

    def autosave(self) -> dict:
        """Salvataggio periodico chiamato dal frontend: cifra su disco solo
        se qualcosa e' cambiato, cosi' un'app aperta e ferma non riscrive
        il vault ogni volta.
        """
        if self._edb.conn is None or not self._dirty:
            return {"ok": True, "saved": False}
        self._edb.save()
        self._dirty = False
        return {"ok": True, "saved": True}

    def close_vault(self) -> dict:
        was_open = self._edb.conn is not None
        db_path = self._edb.db_path
        self._edb.close()
        self._dirty = False
        # Solo se c'era davvero una sessione da salvare: altrimenti la
        # chiusura (invocata sia dall'evento finestra sia da main) farebbe
        # partire due backup identici a ogni uscita.
        if was_open:
            backup.auto_backup_if_configured(db_path)
        return {"ok": True}

    # --- CRUD ---

    def create_block(
        self,
        type: str,
        parent_id: str | None = None,
        content: dict | list | None = None,
        properties: dict | None = None,
        schema: dict | None = None,
        order_index: int = 0,
        block_id: str | None = None,
    ) -> str:
        conn = self._conn
        new_id = db.create_block(
            conn,
            type,
            parent_id,
            content,
            properties,
            schema,
            order_index,
            block_id,
        )
        links.sync_links_for_block(conn, db.get_block(conn, new_id))
        self._touch()
        return new_id

    def get_block(self, block_id: str) -> dict | None:
        return db.get_block(self._conn, block_id)

    def list_blocks(self, parent_id: str | None = None) -> list[dict]:
        return db.list_blocks(self._conn, parent_id)

    def update_block(self, block_id: str, fields: dict) -> dict:
        conn = self._conn
        db.update_block(conn, block_id, **fields)
        if "content" in fields:
            links.sync_links_for_block(conn, db.get_block(conn, block_id))
        self._touch()
        return {"ok": True}

    def delete_block(self, block_id: str) -> dict:
        conn = self._conn
        db.delete_block(conn, block_id)
        links.delete_links_for_block(conn, block_id)
        self._touch()
        return {"ok": True}

    def delete_block_tree(self, block_id: str) -> dict:
        """Cancella un blocco con tutta la sua discendenza (una pagina si
        porta dietro i propri blocchi, un progetto le proprie pagine).
        """
        conn = self._conn
        removed = db.delete_block_tree(conn, block_id)
        for removed_id in removed:
            links.delete_links_for_block(conn, removed_id)
        self._touch()
        return {"ok": True, "removed": len(removed)}

    # --- query generica ---

    def query_blocks(
        self,
        parent_id=db.UNSET,
        filters: list[dict] | None = None,
        sort: list[dict] | None = None,
        group_by: str | None = None,
    ):
        return db.query_blocks(
            self._conn,
            parent_id=parent_id,
            filters=filters,
            sort=sort,
            group_by=group_by,
        )

    # --- ricerca full-text (Fase 5) ---

    def search(self, query: str, limit: int = 50) -> list[dict]:
        return search_module.search(self._conn, query, limit)

    # --- backlink (Fase 6) ---

    def get_backlinks(self, block_id: str) -> list[dict]:
        return links.backlinks_for(self._conn, block_id)

    # --- journaling (Fase 6bis) ---

    def ensure_today_journal(self) -> dict:
        entry = journal.ensure_today_entry(self._conn)
        self._touch()
        return entry

    def get_streak(self) -> int:
        return journal.current_streak(self._conn)

    def ensure_reflection_page(self, period: str) -> dict:
        page = journal.ensure_reflection_page(self._conn, period)
        self._touch()
        return page

    # --- knowledge booster / SM-2 (Fase 7) ---

    def create_concept(self, argomento: str) -> dict:
        concept = spaced_repetition.create_concept(self._conn, argomento)
        self._touch()
        return concept

    def due_today_concepts(self) -> list[dict]:
        return spaced_repetition.due_today(self._conn)

    def review_concept(self, concept_id: str, confidenza: int) -> dict:
        concept = spaced_repetition.review_concept(self._conn, concept_id, confidenza)
        self._touch()
        return concept

    # --- system design / template Progetti (Fase 8) ---

    def ensure_projects_database(self) -> dict:
        projects_db = projects.ensure_projects_database(self._conn)
        self._touch()
        return projects_db

    def create_project(self, nome: str) -> dict:
        project = projects.create_project(self._conn, nome)
        self._touch()
        return project

    def list_projects(self) -> list[dict]:
        return projects.list_projects(self._conn)

    # --- code planning mode (Fase 9) ---

    def create_code_planning_page(self) -> dict:
        page = planning.create_code_planning_page(self._conn)
        self._touch()
        return page

    def export_page_markdown(self, page_id: str) -> dict:
        import webview

        conn = self._conn
        markdown = planning.export_to_markdown(conn, page_id)
        page = db.get_block(conn, page_id)
        title = (page.get("content") or {}).get("title", "pagina")
        safe_name = "".join(c for c in title if c.isalnum() or c in (" ", "-", "_")).strip() or "pagina"

        window = webview.windows[0] if webview.windows else None
        if window is None:
            return {"ok": False, "error": "Finestra non disponibile"}

        result = window.create_file_dialog(
            webview.SAVE_DIALOG, save_filename=f"{safe_name}.md"
        )
        if not result:
            return {"ok": False, "error": "Esportazione annullata"}

        path = result if isinstance(result, str) else result[0]
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(markdown)
        except OSError:
            return {"ok": False, "error": "Impossibile scrivere il file scelto."}
        return {"ok": True, "path": os.path.abspath(path)}

    # --- quick capture / inbox (Fase 10) ---

    def list_inbox(self) -> list[dict]:
        return db.query_blocks(
            self._conn,
            filters=[
                {"field": "type", "op": "=", "value": "text"},
                {"field": "parent_id", "op": "=", "value": None},
                {"field": "properties.inbox", "op": "=", "value": True},
            ],
            sort=[{"field": "created_at", "dir": "desc"}],
        )

    def inbox_count(self) -> int:
        return len(self.list_inbox())

    def promote_inbox_item(self, block_id: str) -> dict:
        conn = self._conn
        item = db.get_block(conn, block_id)
        if item is None:
            return {"ok": False, "error": "Elemento non trovato."}
        text = (item.get("content") or {}).get("text", "")
        title = (text[:50] or "Nuova pagina").strip()

        page_id = db.create_block(conn, type="page", parent_id=None, content={"title": title})
        text_id = db.create_block(conn, type="text", parent_id=page_id, content={"text": text})
        # La nuova pagina puo' contenere wikilink, e diventa a sua volta un
        # bersaglio: vanno ricalcolati i link in uscita e quelli che il
        # titolo appena creato rende risolvibili.
        links.sync_links_for_block(conn, db.get_block(conn, text_id))

        db.delete_block(conn, block_id)
        links.delete_links_for_block(conn, block_id)
        self._touch()
        return db.get_block(conn, page_id)

    def discard_inbox_item(self, block_id: str) -> dict:
        conn = self._conn
        db.delete_block(conn, block_id)
        links.delete_links_for_block(conn, block_id)
        self._touch()
        return {"ok": True}

    # --- weekly review (Fase 11) ---

    def get_weekly_review(self) -> dict:
        return review.weekly_review(self._conn)

    # --- backup cifrato locale (Fase 12) ---

    def backup_now(self) -> dict:
        import webview

        if self._edb.conn is None:
            return {"ok": False, "error": "Vault non aperto."}
        self._edb.save()
        self._dirty = False

        window = webview.windows[0] if webview.windows else None
        if window is None:
            return {"ok": False, "error": "Finestra non disponibile"}

        result = window.create_file_dialog(webview.FOLDER_DIALOG)
        if not result:
            return {"ok": False, "error": "Backup annullato"}
        dest_dir = result if isinstance(result, str) else result[0]

        try:
            path = backup.backup_now(self._edb.db_path, dest_dir)
        except OSError:
            return {"ok": False, "error": "Impossibile scrivere nella cartella scelta."}
        return {"ok": True, "path": path}

    def get_last_backup_info(self) -> dict:
        return backup.read_config(self._edb.db_path)
