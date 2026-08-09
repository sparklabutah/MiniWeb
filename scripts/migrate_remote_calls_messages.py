#!/usr/bin/env python3
"""Create + register the remote-calls (CallHub) `messages` table.

The in-call chat stores messages in the `messages` collection, but the table
was never created/registered — so sends went to the session overlay while
db.query() read a non-existent base table and returned nothing (chat appeared
empty after sending). schema.py now declares the table; this migration creates
and registers it for an already-built DB (a full build_db would also do so).

Idempotent. Run: PYTHONPATH=. ~/.conda/envs/miniweb/bin/python scripts/migrate_remote_calls_messages.py
"""
import app.db as db


def main():
    conn = db._get_conn()
    conn.execute("CREATE TABLE IF NOT EXISTS remote_calls_messages "
                 "(meeting_id TEXT PRIMARY KEY, msgs TEXT NOT NULL DEFAULT '[]')")
    conn.commit()
    db.register_table("remote-calls", "messages", "remote_calls_messages", "meeting_id", conn=conn)
    conn.commit()
    print("table:", db.get_table_name("remote-calls", "messages"),
          "| pk:", db.get_pk_column("remote-calls", "messages"))


if __name__ == "__main__":
    main()
