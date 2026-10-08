import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from annotation import final_set, macro_browser, task_audit


class TaskAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        ann = Path(self.tmp.name) / "ann"
        d = ann / "alice" / "news_0001"
        d.mkdir(parents=True)
        task = {"task_id": "news_0001", "site": "news", "instruction": "Search for x and post it.",
                "macros": ["search", "create_by_form"], "macro_spans": {"search": [1, 1], "create_by_form": [2, 2]},
                "macro_subtasks": {"search": "Search x", "create_by_form": "Post it"}}
        (d / "task.json").write_text(json.dumps(task))
        (d / "verifier.json").write_text(json.dumps({"macros": {"search": {"type": "page_visited", "url": "/q"}}}))
        (d / "before_review.json").write_text(json.dumps({"task": {**task, "instruction": "search x then post"},
                                                          "verifier": {"macros": {}}}))
        (d / "trajectory.json").write_text(json.dumps([
            {"type": "action", "action": "type", "target": "input 'Search'", "value": "x", "url": "/sites/news/"},
            {"type": "observation", "screenshot": "screenshots/step_000.png"},
            {"type": "action", "action": "click", "target": "button 'Post'", "url": "/sites/news/new"}]))
        idx = ann / ".task_audit" / "_index"
        idx.mkdir(parents=True)
        (idx / "index.json").write_text(json.dumps({"families": {"search": "Text entry"}, "tasks": [
            {"task_id": "news_0001", "folder": "alice", "site": "news", "sites": ["news"], "split": "test",
             "status": "valid", "changed_fields": ["instruction"], "verifier_repaired": True, "rerecorded": False,
             "walk": False},
            {"task_id": "gone_0002", "folder": "alice", "site": "news", "sites": ["news"], "split": "train",
             "status": "stale", "changed_fields": [], "verifier_repaired": False, "rerecorded": False,
             "walk": False}]}))
        self.patches = [mock.patch.object(task_audit, "ANNOTATIONS_DIR", ann),
                        mock.patch.object(macro_browser, "ANNOTATIONS_DIR", ann)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def client(self):
        from flask import Flask
        from annotation.app import annotation_bp
        app = Flask(__name__)
        app.secret_key = "test"
        app.register_blueprint(annotation_bp, url_prefix="/annotate")
        c = app.test_client()
        with c.session_transaction() as s:
            s.update(annotator_authenticated=True, annotator_name="alice")
        return c

    def test_lists_present_tasks_and_serves_both_versions(self):
        c = self.client()
        rows = c.get("/annotate/api/task_audit/tasks").get_json()["tasks"]
        self.assertEqual([r["task_id"] for r in rows], ["news_0001"])          # the missing folder is skipped
        t = c.get("/annotate/api/task_audit/task/news_0001").get_json()
        self.assertEqual(t["original"]["instruction"], "search x then post")
        self.assertEqual(t["current"]["instruction"], "Search for x and post it.")
        self.assertEqual([(p["instance"], p["span"], p["family"]) for p in t["primitives"]],
                         [("search", [1, 1], "Text entry"), ("create_by_form", [2, 2], "")])
        self.assertEqual([a["frame"] for a in t["recordings"]["gold"]], ["screenshots/step_000.png"] * 2)
        self.assertIsNone(t["recordings"]["walk"])
        self.assertEqual(c.get("/annotate/api/task_audit/task/nope").status_code, 404)

    def test_label_rules_and_last_wins(self):
        c = self.client()
        post = lambda **b: c.post("/annotate/api/task_audit/label", json={"task_id": "news_0001", **b})  # noqa: E731
        self.assertEqual(post(task="great", changes="accept").status_code, 400)
        self.assertEqual(post(task="ok").status_code, 400)                              # a modified task needs it
        self.assertEqual(post(task="ok", changes="maybe").status_code, 400)
        self.assertEqual(post(task="fix", changes="accept", notes="a").status_code, 200)
        self.assertEqual(post(task="broken", changes="reject").status_code, 200)
        mine = task_audit.labels("alice")
        self.assertEqual((mine["news_0001"]["task"], mine["news_0001"]["changes"]), ("broken", "reject"))
        self.assertTrue(c.get("/annotate/api/task_audit/tasks").get_json()["tasks"][0]["labeled"])
        self.assertEqual(len(c.get("/annotate/api/task_audit/labels.json").get_json()), 1)

    def test_labels_stay_writable_under_the_lock(self):
        self.assertTrue(final_set.write_allowed("/annotate/api/task_audit/label"))


if __name__ == "__main__":
    unittest.main()
