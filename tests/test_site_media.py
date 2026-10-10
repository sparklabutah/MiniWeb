import json
import tempfile
import unittest
from pathlib import Path

from flask import Flask, jsonify

from miniweb.app.media import init_media


class SiteMediaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "img.example.com" / "a").mkdir(parents=True)
        (root / "img.example.com" / "a" / "x.jpg").write_bytes(b"JPEG")
        tile = root / "cartodb-basemaps.global.ssl.fastly.net" / "light_nolabels" / "13" / "1" / "2.png"
        tile.parent.mkdir(parents=True)
        tile.write_bytes(b"PNG")
        rows = [{"url": "https://img.example.com/a/x.jpg", "path": "img.example.com/a/x.jpg", "status": 200},
                {"url": "https://img.example.com/a/gone.jpg", "path": None, "status": 404},
                {"url": "https://img.example.com/a/later.png", "path": "img.example.com/a/later.png", "status": 200}]
        (root / "manifest.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        app = Flask(__name__)

        @app.route("/sites/demo/")
        def page():
            return ('<img src="https://img.example.com/a/x.jpg"><img src="https://img.example.com/a/gone.jpg">'
                    "<script>L.tileLayer('https://cartodb-basemaps-a.global.ssl.fastly.net/light_nolabels/{z}/{x}/{y}.png')"
                    "</script>")

        @app.route("/sites/demo/api")
        def api():
            return jsonify({"image": "https://img.example.com/a/x.jpg"})

        init_media(app, root)
        self.c = app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def test_pages_point_at_the_local_copy(self):
        html = self.c.get("/sites/demo/").get_data(as_text=True)
        self.assertIn('src="/media/img.example.com/a/x.jpg"', html)
        self.assertIn('src="https://img.example.com/a/gone.jpg"', html)       # not downloaded: left alone
        self.assertIn("/media/tiles/light_nolabels/{z}/{x}/{y}.png", html)
        self.assertEqual(self.c.get("/sites/demo/api").get_json()["image"], "/media/img.example.com/a/x.jpg")

    def test_serves_files_and_falls_back_to_the_original(self):
        self.assertEqual(self.c.get("/media/img.example.com/a/x.jpg").data, b"JPEG")
        self.assertEqual(self.c.get("/media/tiles/light_nolabels/13/1/2.png").data, b"PNG")
        r = self.c.get("/media/tiles/light_nolabels/18/5/5.png")
        self.assertEqual((r.status_code, r.location), (302, "https://cartodb-basemaps-a.global.ssl.fastly.net/light_nolabels/18/5/5.png"))
        r = self.c.get("/media/img.example.com/a/later.png")                  # listed but not on disk
        self.assertEqual((r.status_code, r.location), (302, "https://img.example.com/a/later.png"))
        self.assertEqual(self.c.get("/media/nowhere/x.png").status_code, 404)

    def test_no_copy_no_change(self):
        app = Flask(__name__)
        self.assertIsNone(init_media(app, Path(self.tmp.name) / "missing"))


if __name__ == "__main__":
    unittest.main()
