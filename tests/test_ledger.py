"""Test del motore dati e della cifratura. Solo libreria standard:

    python -m unittest discover -s tests -v

Non serve una GUI: tutto quello che sta sotto js_api e' pura logica su
`blocks`. I test coprono cio' che, rompendosi, perde dati o legge in
chiaro qualcosa che dovrebbe essere cifrato.
"""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import api as api_module  # noqa: E402
import backup  # noqa: E402
import crypto  # noqa: E402
import db  # noqa: E402
import journal  # noqa: E402
import links  # noqa: E402
import planning  # noqa: E402
import projects  # noqa: E402
import review  # noqa: E402
import search  # noqa: E402
import spaced_repetition  # noqa: E402


def fresh_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_schema(conn)
    search.init_fts_schema(conn)
    links.init_links_schema(conn)
    return conn


class TestCrypto(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "vault.db")

    def tearDown(self):
        self.dir.cleanup()

    def test_round_trip(self):
        edb = crypto.EncryptedDatabase(self.path)
        conn = edb.open("passphrase-lunga")
        db.init_schema(conn)
        db.create_block(conn, "page", content={"title": "Segreto Atlantide"})
        edb.close()

        reopened = crypto.EncryptedDatabase(self.path)
        conn2 = reopened.open("passphrase-lunga")
        pages = db.query_blocks(conn2, filters=[{"field": "type", "op": "=", "value": "page"}])
        self.assertEqual(pages[0]["content"]["title"], "Segreto Atlantide")
        reopened.close()

    def test_file_on_disk_is_not_readable(self):
        edb = crypto.EncryptedDatabase(self.path)
        conn = edb.open("passphrase-lunga")
        db.init_schema(conn)
        db.create_block(conn, "page", content={"title": "Segreto Atlantide"})
        edb.close()

        with open(self.path, "rb") as f:
            raw = f.read()
        self.assertNotIn(b"Segreto Atlantide", raw)
        self.assertNotIn(b"SQLite format 3", raw)
        self.assertNotIn(b"passphrase-lunga", raw)

    def test_wrong_passphrase(self):
        edb = crypto.EncryptedDatabase(self.path)
        edb.open("passphrase-lunga")
        db.init_schema(edb.conn)
        edb.close()

        with self.assertRaises(crypto.WrongPassphraseError):
            crypto.EncryptedDatabase(self.path).open("passphrase-sbagliata")

    def test_short_passphrase_refused_on_first_run(self):
        with self.assertRaises(crypto.WeakPassphraseError):
            crypto.EncryptedDatabase(self.path).open("corta")
        self.assertFalse(os.path.exists(self.path))

    def test_missing_salt_is_reported(self):
        edb = crypto.EncryptedDatabase(self.path)
        edb.open("passphrase-lunga")
        db.init_schema(edb.conn)
        edb.close()
        os.remove(self.path + crypto.SALT_SUFFIX)

        with self.assertRaises(crypto.VaultCorruptedError):
            crypto.EncryptedDatabase(self.path).open("passphrase-lunga")

    def test_save_keeps_previous_file_on_failure(self):
        edb = crypto.EncryptedDatabase(self.path)
        conn = edb.open("passphrase-lunga")
        db.init_schema(conn)
        edb.save()
        with open(self.path, "rb") as f:
            first = f.read()

        db.create_block(conn, "page", content={"title": "Seconda"})
        edb.save()
        with open(self.path, "rb") as f:
            second = f.read()
        self.assertNotEqual(first, second)
        edb.close()


class TestBlocks(unittest.TestCase):
    def setUp(self):
        self.conn = fresh_conn()

    def test_crud(self):
        block_id = db.create_block(self.conn, "page", content={"title": "Uno"})
        self.assertEqual(db.get_block(self.conn, block_id)["content"]["title"], "Uno")

        db.update_block(self.conn, block_id, content={"title": "Due"})
        self.assertEqual(db.get_block(self.conn, block_id)["content"]["title"], "Due")

        db.delete_block(self.conn, block_id)
        self.assertIsNone(db.get_block(self.conn, block_id))

    def test_update_rejects_unknown_field(self):
        block_id = db.create_block(self.conn, "page")
        with self.assertRaises(ValueError):
            db.update_block(self.conn, block_id, titolo="non esiste")

    def test_delete_tree_removes_descendants(self):
        page = db.create_block(self.conn, "page", content={"title": "Radice"})
        child = db.create_block(self.conn, "text", parent_id=page, content={"text": "figlio"})
        grandchild = db.create_block(self.conn, "text", parent_id=child, content={"text": "nipote"})

        removed = db.delete_block_tree(self.conn, page)
        self.assertEqual(set(removed), {page, child, grandchild})
        self.assertIsNone(db.get_block(self.conn, grandchild))

    def test_query_filters_and_grouping(self):
        db.create_block(self.conn, "database_row", properties={"stato": "aperto"})
        db.create_block(self.conn, "database_row", properties={"stato": "chiuso"})

        aperti = db.query_blocks(
            self.conn, filters=[{"field": "properties.stato", "op": "=", "value": "aperto"}]
        )
        self.assertEqual(len(aperti), 1)

        grouped = db.query_blocks(
            self.conn,
            filters=[{"field": "type", "op": "=", "value": "database_row"}],
            group_by="properties.stato",
        )
        self.assertEqual(sorted(grouped), ["aperto", "chiuso"])

    def test_sort_survives_mixed_types(self):
        """Le properties sono JSON libero: la stessa chiave puo' essere
        numero in una riga e testo in un'altra. L'ordinamento non deve
        sollevare TypeError e far sparire l'intera vista.
        """
        for value in (3, "beta", None, 1, "alfa", True):
            db.create_block(self.conn, "database_row", properties={"x": value})

        ordered = db.query_blocks(
            self.conn,
            filters=[{"field": "type", "op": "=", "value": "database_row"}],
            sort=[{"field": "properties.x", "dir": "asc"}],
        )
        self.assertEqual(len(ordered), 6)
        self.assertIsNone(ordered[-1]["properties"]["x"])

    def test_parent_id_unset_vs_none(self):
        root = db.create_block(self.conn, "page")
        db.create_block(self.conn, "text", parent_id=root)

        self.assertEqual(len(db.query_blocks(self.conn)), 2)
        self.assertEqual(len(db.query_blocks(self.conn, parent_id=None)), 1)
        self.assertEqual(len(db.query_blocks(self.conn, parent_id=root)), 1)


class TestSearch(unittest.TestCase):
    def setUp(self):
        self.conn = fresh_conn()

    def test_finds_and_follows_updates(self):
        block_id = db.create_block(self.conn, "text", content={"text": "appunti sul teorema di Bayes"})
        self.assertEqual(len(search.search(self.conn, "Bayes")), 1)

        db.update_block(self.conn, block_id, content={"text": "appunti sul teorema di Pitagora"})
        self.assertEqual(search.search(self.conn, "Bayes"), [])
        self.assertEqual(len(search.search(self.conn, "Pitagora")), 1)

        db.delete_block(self.conn, block_id)
        self.assertEqual(search.search(self.conn, "Pitagora"), [])

    def test_query_with_fts_syntax_does_not_crash(self):
        db.create_block(self.conn, "text", content={"text": "nota qualsiasi"})
        for query in ('"', "AND", "nota OR", "*", "^nota", "()"):
            with self.subTest(query=query):
                search.search(self.conn, query)

    def test_indexes_properties_too(self):
        db.create_block(self.conn, "concept", properties={"argomento": "entropia"})
        self.assertEqual(len(search.search(self.conn, "entropia")), 1)


class TestLinks(unittest.TestCase):
    def setUp(self):
        self.conn = fresh_conn()

    def test_wikilink_creates_backlink(self):
        target = db.create_block(self.conn, "page", content={"title": "Fisica"})
        source_id = db.create_block(self.conn, "text", content={"text": "vedi [[Fisica]] domani"})
        links.sync_links_for_block(self.conn, db.get_block(self.conn, source_id))

        backlinks = links.backlinks_for(self.conn, target)
        self.assertEqual([b["id"] for b in backlinks], [source_id])

    def test_removing_wikilink_removes_backlink(self):
        target = db.create_block(self.conn, "page", content={"title": "Fisica"})
        source_id = db.create_block(self.conn, "text", content={"text": "[[Fisica]]"})
        links.sync_links_for_block(self.conn, db.get_block(self.conn, source_id))

        db.update_block(self.conn, source_id, content={"text": "niente link"})
        links.sync_links_for_block(self.conn, db.get_block(self.conn, source_id))
        self.assertEqual(links.backlinks_for(self.conn, target), [])

    def test_unresolved_wikilink_is_ignored(self):
        source_id = db.create_block(self.conn, "text", content={"text": "[[Pagina che non esiste]]"})
        links.sync_links_for_block(self.conn, db.get_block(self.conn, source_id))
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) AS n FROM links").fetchone()["n"], 0
        )


class TestSpacedRepetition(unittest.TestCase):
    def setUp(self):
        self.conn = fresh_conn()

    def test_new_concept_is_due_today(self):
        concept = spaced_repetition.create_concept(self.conn, "SM-2")
        due = spaced_repetition.due_today(self.conn)
        self.assertEqual([c["id"] for c in due], [concept["id"]])

    def test_good_answer_pushes_review_forward(self):
        concept = spaced_repetition.create_concept(self.conn, "SM-2")
        updated = spaced_repetition.review_concept(self.conn, concept["id"], 5)
        self.assertGreater(updated["properties"]["prossima_revisione"], date.today().isoformat())
        self.assertEqual(spaced_repetition.due_today(self.conn), [])

    def test_failed_answer_resets_repetitions(self):
        concept = spaced_repetition.create_concept(self.conn, "SM-2")
        spaced_repetition.review_concept(self.conn, concept["id"], 5)
        spaced_repetition.review_concept(self.conn, concept["id"], 5)
        failed = spaced_repetition.review_concept(self.conn, concept["id"], 1)
        self.assertEqual(failed["properties"]["ripetizioni"], 0)
        self.assertEqual(failed["properties"]["intervallo"], 1)

    def test_easiness_never_below_floor(self):
        concept = spaced_repetition.create_concept(self.conn, "SM-2")
        for _ in range(10):
            result = spaced_repetition.review_concept(self.conn, concept["id"], 0)
        self.assertGreaterEqual(result["properties"]["ef"], spaced_repetition.MIN_EASINESS)


class TestJournal(unittest.TestCase):
    def setUp(self):
        self.conn = fresh_conn()

    def test_today_entry_is_created_once(self):
        first = journal.ensure_today_entry(self.conn)
        second = journal.ensure_today_entry(self.conn)
        self.assertEqual(first["id"], second["id"])

    def test_streak_counts_only_filled_days(self):
        today = date.today()
        for offset in (0, 1, 2):
            day = (today - timedelta(days=offset)).isoformat()
            entry = db.create_block(
                self.conn, "journal_entry", properties={"data": day, "gratitudine": []}
            )
            if offset < 2:  # il piu' vecchio resta vuoto: spezza la serie
                db.create_block(self.conn, "text", parent_id=entry, content={"text": "scritto"})

        self.assertEqual(journal.current_streak(self.conn), 2)

    def test_reflection_page_is_idempotent(self):
        first = journal.ensure_reflection_page(self.conn, "weekly")
        second = journal.ensure_reflection_page(self.conn, "weekly")
        self.assertEqual(first["id"], second["id"])

    def test_reflection_period_is_validated(self):
        with self.assertRaises(ValueError):
            journal.ensure_reflection_page(self.conn, "daily")


class TestProjectsAndPlanning(unittest.TestCase):
    def setUp(self):
        self.conn = fresh_conn()

    def test_project_gets_child_pages(self):
        row = projects.create_project(self.conn, "Ledger")
        pagine = row["properties"]["pagine"]
        self.assertEqual(sorted(pagine), ["architettura", "decisioni", "vincoli"])
        for page_id in pagine.values():
            self.assertEqual(db.get_block(self.conn, page_id)["type"], "page")

    def test_listing_projects_does_not_create_the_database(self):
        self.assertEqual(projects.list_projects(self.conn), [])
        self.assertEqual(
            db.query_blocks(self.conn, filters=[{"field": "type", "op": "=", "value": "database"}]), []
        )

    def test_markdown_export(self):
        page = planning.create_code_planning_page(self.conn)
        db.create_block(
            self.conn,
            "checklist",
            parent_id=page["id"],
            content={"items": [{"text": "fatto", "checked": True}, {"text": "da fare", "checked": False}]},
            order_index=99,
        )
        db.create_block(
            self.conn,
            "diagram",
            parent_id=page["id"],
            content={"source": "graph TD\n  A --> B"},
            order_index=100,
        )

        markdown = planning.export_to_markdown(self.conn, page["id"])
        self.assertTrue(markdown.startswith("# Nuovo piano"))
        self.assertIn("## Contesto", markdown)
        self.assertIn("- [x] fatto", markdown)
        self.assertIn("- [ ] da fare", markdown)
        self.assertIn("```mermaid", markdown)


class TestReview(unittest.TestCase):
    def setUp(self):
        self.conn = fresh_conn()

    def test_overdue_rows_are_found_by_schema(self):
        db_id = db.create_block(
            self.conn,
            "database",
            content={"title": "Task"},
            schema={"campi": [{"nome": "Scadenza", "tipo": "date"}]},
        )
        ieri = (date.today() - timedelta(days=1)).isoformat()
        domani = (date.today() + timedelta(days=1)).isoformat()
        db.create_block(self.conn, "database_row", parent_id=db_id, properties={"Scadenza": ieri})
        db.create_block(self.conn, "database_row", parent_id=db_id, properties={"Scadenza": domani})

        overdue = review.overdue_tasks(self.conn)
        self.assertEqual(len(overdue), 1)
        self.assertEqual(overdue[0]["_scadenza_valore"], ieri)

    def test_weekly_review_has_all_sections(self):
        data = review.weekly_review(self.conn)
        self.assertEqual(
            sorted(data), ["concetti_da_rivedere", "pagine_modificate", "task_scaduti"]
        )


class TestBackup(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "vault.db")

    def tearDown(self):
        self.dir.cleanup()

    def test_backup_copies_db_and_salt(self):
        edb = crypto.EncryptedDatabase(self.path)
        edb.open("passphrase-lunga")
        db.init_schema(edb.conn)
        edb.close()

        dest = os.path.join(self.dir.name, "backup")
        copied = backup.backup_now(self.path, dest)
        self.assertTrue(os.path.exists(copied))
        names = os.listdir(dest)
        self.assertTrue(any(".salt." in n for n in names), names)
        self.assertEqual(backup.read_config(self.path)["backup_dir"], dest)

    def test_corrupted_config_is_ignored(self):
        with open(self.path + backup.CONFIG_SUFFIX, "w", encoding="utf-8") as f:
            f.write("{ questo non e' json")
        self.assertEqual(backup.read_config(self.path), {})
        backup.auto_backup_if_configured(self.path)  # non deve sollevare


class TestApi(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.api = api_module.Api(db_path=os.path.join(self.dir.name, "vault.db"))

    def tearDown(self):
        self.api.close_vault()
        self.dir.cleanup()

    def test_calls_before_unlock_fail_clearly(self):
        """Senza vault aperto una chiamata deve fallire con un messaggio,
        non con un AttributeError su una connessione inesistente.
        """
        with self.assertRaises(api_module.VaultNotOpenError):
            self.api.create_block("text", None, {"text": "ciao"})

    def test_second_open_does_not_discard_the_session(self):
        self.assertTrue(self.api.open_vault("passphrase-lunga")["ok"])
        block_id = self.api.create_block("page", None, {"title": "Viva"})

        again = self.api.open_vault("passphrase-lunga")
        self.assertTrue(again["ok"])
        self.assertTrue(again.get("already_open"))
        self.assertIsNotNone(self.api.get_block(block_id))

    def test_autosave_only_writes_when_dirty(self):
        self.api.open_vault("passphrase-lunga")
        self.api.create_block("page", None, {"title": "Uno"})
        self.assertTrue(self.api.autosave()["saved"])
        self.assertFalse(self.api.autosave()["saved"])

    def test_promoted_inbox_item_becomes_a_page(self):
        self.api.open_vault("passphrase-lunga")
        item_id = self.api.create_block("text", None, {"text": "idea da sviluppare"}, {"inbox": True})
        self.assertEqual(self.api.inbox_count(), 1)

        page = self.api.promote_inbox_item(item_id)
        self.assertEqual(page["type"], "page")
        self.assertEqual(page["content"]["title"], "idea da sviluppare")
        self.assertEqual(self.api.inbox_count(), 0)
        self.assertIsNone(self.api.get_block(item_id))


if __name__ == "__main__":
    unittest.main()
