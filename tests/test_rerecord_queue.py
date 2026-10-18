import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from annotation import rerecord_queue


class RerecordQueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ann = Path(self.tmp.name) / "ann"
        for folder, tid in (("alice", "news_0001"), ("bob", "shop_0002")):
            d = self.ann / folder / tid
            d.mkdir(parents=True)
            (d / "task.json").write_text(json.dumps({"task_id": tid, "rerecorded_at": "2026-10-01T09:00:00"}))
        q = self.ann / ".rerecord_queue" / "_queue"
        q.mkdir(parents=True)
        (q / "queue.json").write_text(json.dumps({"since": "2026-10-18T00:00:00", "tasks": [
            {"task_id": "news_0001", "folder": "alice", "start_url": "/sites/news/", "steps": ["Post it"]},
            {"task_id": "shop_0002", "folder": "bob", "start_url": "/sites/shop/item/3", "steps": ["Buy it"]}]}))
        self.patch = mock.patch.object(rerecord_queue, "ANNOTATIONS_DIR", self.ann)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def rerecord(self, folder, tid):
        (self.ann / folder / tid / "task.json").write_text(json.dumps({"task_id": tid,
                                                                       "rerecorded_at": "2026-10-18T22:00:00"}))

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

    def test_hands_out_pending_tasks_in_order(self):
        c = self.client()
        loc = c.get("/annotate/rerecord-queue").headers["Location"]
        self.assertIn("rerecord=news_0001", loc)          # an older re-record does not count
        self.assertIn("annotator=alice", loc)
        self.assertIn("queue=1", loc)
        self.assertIn("rerecord=shop_0002", c.get("/annotate/rerecord-queue?after=news_0001").headers["Location"])
        self.assertIn("rerecord=news_0001", c.get("/annotate/rerecord-queue?after=shop_0002").headers["Location"])
        self.rerecord("alice", "news_0001")
        self.assertIn("rerecord=shop_0002", c.get("/annotate/rerecord-queue").headers["Location"])
        self.rerecord("bob", "shop_0002")
        r = c.get("/annotate/rerecord-queue")
        self.assertEqual(r.status_code, 200)
        self.assertIn("All 2 tasks", r.get_data(as_text=True))

    def test_entry_reports_position_and_progress(self):
        self.rerecord("alice", "news_0001")
        e = rerecord_queue.entry("shop_0002")
        self.assertEqual((e["position"], e["total"], e["done"], e["start_url"]), (2, 2, 1, "/sites/shop/item/3"))
        self.assertIsNone(rerecord_queue.entry("other_0003"))

    def test_no_queue(self):
        (self.ann / ".rerecord_queue" / "_queue" / "queue.json").unlink()
        self.assertEqual(self.client().get("/annotate/rerecord-queue").status_code, 404)


if __name__ == "__main__":
    unittest.main()
