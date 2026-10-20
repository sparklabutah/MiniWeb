"""Files that requests leave on disk (app/uploads.py): each session has its own, a browser's file name cannot leave the
session's folder, and the files go with the session."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from flask import Flask, request, session

from miniweb.app import db, uploads


class SessionUploadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.root = root / "uploads"
        self.patch = mock.patch.object(uploads, "ROOT", self.root)
        self.patch.start()
        self.old_path = db._DB_PATH
        db.close()
        db.init_db(str(root / "miniweb.db"))

        app = Flask(__name__)
        app.secret_key = "test"

        @app.route("/as")
        def login():
            session["_data_overlay_sid"] = request.args["sid"]
            return "ok"

        @app.route("/save", methods=["POST"])
        def save():
            file = uploads.path("shop", request.form["name"])
            file.write_text(session["_data_overlay_sid"])
            return file.name

        @app.route("/files/<name>")
        def serve(name):
            return uploads.send("shop", name)

        self.app = app

    def tearDown(self):
        self.patch.stop()
        db.close()
        db._DB_PATH = self.old_path
        self.tmp.cleanup()

    def visitor(self, sid):
        client = self.app.test_client()
        client.get("/as", query_string={"sid": sid})
        return client

    def test_each_session_sees_only_its_own_file(self):
        a, b = self.visitor("aaa"), self.visitor("bbb")
        a.post("/save", data={"name": "icon.svg"})
        b.post("/save", data={"name": "icon.svg"})
        self.assertEqual(a.get("/files/icon.svg").data, b"aaa")
        self.assertEqual(b.get("/files/icon.svg").data, b"bbb")
        self.assertEqual(self.visitor("ccc").get("/files/icon.svg").status_code, 404)
        self.assertEqual(self.app.test_client().get("/files/icon.svg").status_code, 404)   # no session yet

    def test_served_files_cannot_run_scripts(self):
        a = self.visitor("aaa")
        a.post("/save", data={"name": "icon.svg"})
        response = a.get("/files/icon.svg")
        self.assertEqual(response.headers["Content-Security-Policy"], "sandbox")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")

    def test_file_names_stay_inside_the_session_folder(self):
        a = self.visitor("aaa")
        self.assertEqual(a.post("/save", data={"name": "../../templates/evil.html"}).data, b"templates_evil.html")
        self.assertEqual([p.relative_to(self.root).as_posix() for p in self.root.rglob("*") if p.is_file()],
                         ["aaa/shop/templates_evil.html"])
        forged = self.visitor("../x")     # a session id from a cookie signed with a leaked key
        self.assertEqual(forged.post("/save", data={"name": "a.txt"}).status_code, 400)

    def test_files_go_with_the_session(self):
        for sid in ("aaa", "bbb", "ccc"):
            self.visitor(sid).post("/save", data={"name": "a.txt"})
        db.reset_session("aaa")
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["bbb", "ccc"])
        conn = db.get_conn()
        conn.execute("INSERT INTO sessions (session_id, last_access) VALUES ('bbb', '2000-01-01T00:00:00')")
        conn.commit()
        db.evict_stale_sessions()
        self.assertEqual([p.name for p in self.root.iterdir()], ["ccc"])
        db.reset_all()
        self.assertEqual(list(self.root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
