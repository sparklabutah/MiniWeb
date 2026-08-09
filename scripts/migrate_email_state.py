#!/usr/bin/env python3
"""Create + register the email `email_state` table.

Per-session email state overrides (folder / is_starred / is_read) live here so
delete/move/star/read actions persist and stay isolated per session. Previously
these were mutated on in-memory dicts and only persisted for the 'sent' source,
so deleting an inbox/Enron email did nothing.

Idempotent. Run: PYTHONPATH=. ~/.conda/envs/miniweb/bin/python scripts/migrate_email_state.py
"""
import app.db as db


def main():
    conn = db._get_conn()
    conn.execute("CREATE TABLE IF NOT EXISTS email_email_state "
                 "(email_id INTEGER PRIMARY KEY, folder TEXT, is_starred INTEGER, is_read INTEGER)")
    conn.commit()
    db.register_table("email", "email_state", "email_email_state", "email_id", conn=conn)
    conn.commit()
    print("table:", db.get_table_name("email", "email_state"),
          "| pk:", db.get_pk_column("email", "email_state"))


if __name__ == "__main__":
    main()
