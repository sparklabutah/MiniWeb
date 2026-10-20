"""The public demo (MINIWEB_DEMO=1): the site tables refuse writes while sessions keep theirs, the translation site
replays the recorded translations without writing, and scripts/demo_setup.py finds those recordings."""
import importlib.util
import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from helpers.paths import REPO_ROOT
from miniweb.app import db

_spec = importlib.util.spec_from_file_location("demo_setup", REPO_ROOT / "scripts" / "demo_setup.py")
demo_setup = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(demo_setup)


class WriteGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / "miniweb.db")
        con = sqlite3.connect(self.path)
        con.execute("CREATE TABLE shop_items (id INTEGER PRIMARY KEY, name TEXT)")
        con.execute("INSERT INTO shop_items VALUES (1, 'lamp')")
        con.execute("CREATE TABLE shop_orders (id INTEGER PRIMARY KEY, item INTEGER)")   # empty: a runtime seed
        con.commit()
        con.close()
        self.old_path = db._DB_PATH
        db.close()
        db.init_db(self.path)
        db.register_table("shop", "items", "shop_items")
        db.get_conn().commit()
        db.enable_write_guard()

    def tearDown(self):
        db._guarded = None
        db.close()
        db._DB_PATH = self.old_path
        db._registry_cache.clear()
        self.tmp.cleanup()

    def test_site_tables_refuse_writes(self):
        conn = db.get_conn()
        for sql in ("INSERT INTO shop_items VALUES (2, 'desk')", "UPDATE shop_items SET name = 'x'",
                    "DELETE FROM shop_items", "DROP TABLE shop_items"):
            with self.subTest(sql=sql), self.assertRaises(sqlite3.DatabaseError):
                conn.execute(sql)
        self.assertEqual(conn.execute("SELECT name FROM shop_items").fetchall()[0][0], "lamp")

    def test_sessions_and_new_tables_still_write(self):
        db.save_item("shop", "items", 2, {"id": 2, "name": "desk"}, sid="visitor")
        self.assertEqual(db.get_item("shop", "items", 2, sid="visitor")["name"], "desk")
        self.assertIsNone(db.get_item("shop", "items", 2, sid="other"))
        db.get_conn().execute("INSERT INTO shop_orders VALUES (1, 1)")    # a site's one-time seed
        db.register_table("shop", "items", "shop_items")                  # sites register again at runtime

    def test_every_thread_is_guarded(self):
        errors = []

        def write():
            try:
                db.get_conn().execute("DELETE FROM shop_items")
            except sqlite3.DatabaseError as e:
                errors.append(e)
            finally:
                db.close()

        t = threading.Thread(target=write)
        t.start()
        t.join()
        self.assertEqual(len(errors), 1)


class TranslationReplayTests(unittest.TestCase):
    def test_recorded_text_gets_the_recorded_translation(self):
        spec = importlib.util.spec_from_file_location(
            "translation_routes", REPO_ROOT / "src" / "miniweb" / "sites" / "translation" / "routes.py")
        routes = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(routes)
        with tempfile.TemporaryDirectory() as d:
            replay = Path(d) / "replay.json"
            replay.write_text(json.dumps([{"source": "en", "target": "es", "text": "today no work",
                                           "translated": "Hoy no trabajo"}]))
            with mock.patch.object(routes, "_DEMO", True), mock.patch.object(routes, "_REPLAY_PATH", replay), \
                    mock.patch.object(routes, "_replay", None), \
                    mock.patch.object(routes, "_llm_translate", side_effect=AssertionError("no LLM in the demo")):
                self.assertEqual(routes._translate_text("today no work", "en", "es"), "Hoy no trabajo")
                with mock.patch.object(routes, "_model_translate", return_value=None):
                    self.assertTrue(routes._translate_text("good morning", "en", "es"))   # the dictionaries


class DemoSetupTests(unittest.TestCase):
    def test_recorded_translations(self):
        entry = {"method": "POST", "path": demo_setup.TRANSLATE, "body": {"text": " hi ", "source": "en", "target": "fr"},
                 "response": {"translated_text": "salut"}}
        with tempfile.TemporaryDirectory() as d:
            for i, log in enumerate(([entry], {"server_log": [dict(entry, response={"translated_text": "bonjour"})]})):
                task = Path(d) / "A1" / f"t{i}"
                task.mkdir(parents=True)
                (task / ("server_log.json" if i == 0 else "verification_walk.json")).write_text(json.dumps(log))
            self.assertEqual(demo_setup.recorded_translations(d), {("en", "fr", "hi"): "salut"})

    def test_quality_summary_reads_fetched_runs(self):
        """scripts/fetch_tasks.py writes verifier_runs.json entries without their source."""
        from miniweb.annotation import quality
        with tempfile.TemporaryDirectory() as d:
            Path(d, "verifier_runs.json").write_text(json.dumps({"runs": {"gold": {"passed": True},
                                                                           "walk": {"passed": True}}}))
            s = quality.summary(Path(d), {"instruction": "x"})
            self.assertEqual(sorted(r["source"] for r in s["runs"]), ["gold", "walk"])
