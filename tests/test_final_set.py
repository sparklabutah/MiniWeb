import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from annotation import final_set, grader_audit


class FinalSetLockTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        yml = self.root / "final_set.yaml"
        yml.write_text("locked: true\nprimitives: [search, create_by_form]\ntasks: [news_0001]\n")
        self.patches = [mock.patch.object(final_set, "PATH", str(yml)),
                        mock.patch.dict(os.environ, {"MINIWEB_UNLOCK": ""}),
                        mock.patch.object(grader_audit, "ANNOTATIONS_DIR", self.root / "ann")]
        for p in self.patches:
            p.start()
        final_set._data.cache_clear()
        case = self.root / "ann" / ".grader_audit" / "g001"
        case.mkdir(parents=True)
        (case / "case.json").write_text(json.dumps({"id": "g001", "instruction": "Search for x.", "images": [],
                                                    "events": [], "primitives": [{"instance": "search"},
                                                                                 {"instance": "search#2"}]}))

    def tearDown(self):
        for p in self.patches:
            p.stop()
        final_set._data.cache_clear()
        self.tmp.cleanup()

    def client(self):
        from flask import Flask
        from annotation.app import annotation_bp
        app = Flask(__name__)
        app.secret_key = "test"
        app.register_blueprint(annotation_bp, url_prefix="/annotate")
        c = app.test_client()
        with c.session_transaction() as s:
            s.update(annotator_authenticated=True, annotator_name="Minh")
        return c

    def test_lock_and_override(self):
        self.assertTrue(final_set.locked())
        self.assertEqual(final_set.keep_primitives(["search", "save_by_form", "create_by_form"]),
                         ["search", "create_by_form"])
        with mock.patch.dict(os.environ, {"MINIWEB_UNLOCK": "1"}):
            self.assertFalse(final_set.locked())

    def test_locked_tool_refuses_edits_and_registration(self):
        from annotation import macros
        with self.assertRaises(ValueError):
            macros.register_macro("new_macro", "form", "Something new")
        c = self.client()
        r = c.post("/annotate/api/update_task_field", json={"task_id": "t", "field": "instruction", "value": "x"})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(c.delete("/annotate/api/tasks/t").status_code, 403)
        self.assertEqual(c.post("/annotate/api/auto_logout").status_code, 200)   # sessions stay open

    def test_audit_labels_are_open_under_the_lock_and_validated(self):
        c = self.client()
        bad = c.post("/annotate/api/grader_audit/label", json={"case_id": "g001", "primitives": {"search": "pass"}})
        self.assertEqual(bad.status_code, 400)                                   # every primitive needs a label
        ok = c.post("/annotate/api/grader_audit/label",
                    json={"case_id": "g001", "primitives": {"search": "pass", "search#2": "unsure"}, "notes": "n"})
        self.assertEqual(ok.status_code, 200)
        c.post("/annotate/api/grader_audit/label", json={"case_id": "g001", "primitives": {"search": "fail",
                                                                                          "search#2": "fail"}})
        got = c.get("/annotate/api/grader_audit/case/g001").json["my_label"]
        self.assertEqual(got["primitives"], {"search": "fail", "search#2": "fail"})   # the last label wins
        cases = c.get("/annotate/api/grader_audit/cases").json["cases"]
        self.assertEqual(cases, [{"id": "g001", "overlap": False, "labeled": True}])
        self.assertEqual(c.get("/annotate/api/grader_audit/case/..%2Fx").status_code, 404)
        self.assertEqual(len(grader_audit.all_labels()), 1)


if __name__ == "__main__":
    unittest.main()
