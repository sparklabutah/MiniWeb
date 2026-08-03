"""Create + register the sports-esports runtime tables (`comments`,
`subscriptions`).

These collections had no base table, so writes saved to the session overlay
but `db.query` could never read them back (the collection wasn't registered) —
comments vanished and league notification subscriptions never persisted. This
creates and registers them from the schema. Idempotent. Run with the miniweb
conda python; re-run after any DB rebuild, then push the DB to railway.
"""
import importlib.util
import sys

sys.path.insert(0, ".")
from app import create_app, db

spec = importlib.util.spec_from_file_location("sp_schema", "sites/sports-esports/schema.py")
schema = importlib.util.module_from_spec(spec)
spec.loader.exec_module(schema)


def main():
    app = create_app()
    with app.app_context():
        conn = db._get_conn()
        for coll in ("comments", "subscriptions"):
            c = schema.TABLES[coll]
            db.create_site_table(conn, c["table_name"], c["columns"], c.get("indexes"))
            db.register_table("sports-esports", coll, c["table_name"], pk_column="id", conn=conn)
        conn.commit()
        for coll in ("comments", "subscriptions"):
            print(f"OK: {db.get_table_name('sports-esports', coll)} "
                  f"({db.count('sports-esports', coll)} rows)")


if __name__ == "__main__":
    main()
