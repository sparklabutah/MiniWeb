"""Create + register the sports-esports `comments` table.

Match comments had no base table, so posted comments saved to the session
overlay but `db.query` could never read them back (the collection wasn't
registered) — they vanished. This creates and registers the table from the
schema. Idempotent. Run with the miniweb conda python; re-run after any DB
rebuild, then push the DB to railway.
"""
import importlib.util
import sys

sys.path.insert(0, ".")
from app import create_app, db

spec = importlib.util.spec_from_file_location("sp_schema", "sites/sports-esports/schema.py")
schema = importlib.util.module_from_spec(spec)
spec.loader.exec_module(schema)


def main():
    c = schema.TABLES["comments"]
    app = create_app()
    with app.app_context():
        conn = db._get_conn()
        db.create_site_table(conn, c["table_name"], c["columns"], c.get("indexes"))
        db.register_table("sports-esports", "comments", c["table_name"], pk_column="id", conn=conn)
        conn.commit()
        print(f"OK: {db.get_table_name('sports-esports', 'comments')} "
              f"({db.count('sports-esports', 'comments')} rows)")


if __name__ == "__main__":
    main()
