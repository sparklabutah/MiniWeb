"""The server finds its database the way the README sets it up: the .env example parses (inline comments included),
and the default database is where scripts/restore_site_db.py writes it."""
import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import miniweb.app as A
from helpers.paths import REPO_ROOT

README_ENV = '''MINIWEB_DB="data/miniweb.db"
MINIWEB_ANNOTATORS="alice:secret,bob:secret"     # annotation-tool logins
GEMINI_API_KEY=abc                               # or GOOGLE_GENAI_USE_VERTEXAI + GOOGLE_CREDENTIALS_JSON
GOOGLE_CREDENTIALS_JSON="{
  \\"type\\": \\"service_account\\"
}"
OPENAI_API_KEY='sk-1'
'''


class DotenvTests(unittest.TestCase):
    def parse(self, text):
        with tempfile.TemporaryDirectory() as d:
            Path(d, ".env").write_text(text)
            with mock.patch.object(A, "REPO_ROOT", Path(d)), mock.patch.dict(os.environ, {}, clear=True):
                A._load_dotenv()
                return dict(os.environ)

    def test_readme_example(self):
        self.assertEqual(self.parse(README_ENV), {
            "MINIWEB_DB": "data/miniweb.db",
            "MINIWEB_ANNOTATORS": "alice:secret,bob:secret",
            "GEMINI_API_KEY": "abc",
            "GOOGLE_CREDENTIALS_JSON": '{\n  "type": "service_account"\n}',
            "OPENAI_API_KEY": "sk-1",
        })

    def test_example_file_parses(self):
        env = self.parse((REPO_ROOT / ".env.example").read_text())
        self.assertEqual(env["MINIWEB_DB"], "data/miniweb.db")


class DatabasePathTests(unittest.TestCase):
    def db_path(self, value):
        from miniweb.app import db
        env = {k: v for k, v in os.environ.items() if k != "MINIWEB_DB"}
        if value is not None:
            env["MINIWEB_DB"] = value
        try:
            with mock.patch.dict(os.environ, env, clear=True):
                importlib.reload(db)
                return db._DB_PATH
        finally:
            importlib.reload(db)

    def test_default_is_where_restore_writes(self):
        self.assertEqual(self.db_path(None), str(REPO_ROOT / "data" / "miniweb.db"))
        self.assertIn('os.path.join(ROOT, "data", "miniweb.db")', (REPO_ROOT / "scripts" / "restore_site_db.py").read_text())

    def test_relative_paths_are_relative_to_the_repository(self):
        self.assertEqual(self.db_path("data/other.db"), str(REPO_ROOT / "data" / "other.db"))
        self.assertEqual(self.db_path("/srv/miniweb.db"), "/srv/miniweb.db")
