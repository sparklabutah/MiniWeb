#!/usr/bin/env python3
"""Give every banking credit card a full (synthetic) card number + CVV + expiry.

These are FAKE test values (not real cards): a fixed non-issuer BIN, a
deterministic middle, and the card's existing last-4. Writes to the BASE
`banking_cc_users` table (fixture data). Idempotent. Adds the columns if the
DB predates the schema change.

Run: PYTHONPATH=. ~/.conda/envs/miniweb/bin/python scripts/seed_bank_cards.py
"""
import app.db as db

TABLE = "banking_cc_users"


def _ensure_columns():
    have = {c["name"] for c in db.execute(f"PRAGMA table_info({TABLE})", (), fetch="all")}
    conn = db._get_conn()
    for col in ("card_number", "cvv", "card_expiry"):
        if col not in have:
            conn.execute(f"ALTER TABLE {TABLE} ADD COLUMN {col} TEXT NOT NULL DEFAULT ''")
    conn.commit()


def main():
    _ensure_columns()
    rows = db.execute(f"SELECT id, card_number_last4 FROM {TABLE}", (), fetch="all")
    conn = db._get_conn()
    for r in rows:
        cid = r["id"]
        last4 = (r["card_number_last4"] or "0000")[-4:].rjust(4, "0")
        # deterministic 8-digit middle from the card id; BIN 4539 (test range)
        middle = f"{(cid * 13375013) % 100000000:08d}"
        number = f"4539 {middle[:4]} {middle[4:]} {last4}"
        cvv = f"{(cid * 619 + 204) % 900 + 100:03d}"     # deterministic 3-digit
        expiry = f"{(cid % 12) + 1:02d}/28"               # MM/28
        conn.execute(
            f"UPDATE {TABLE} SET card_number=?, cvv=?, card_expiry=? WHERE id=?",
            (number, cvv, expiry, cid))
    conn.commit()

    for r in db.execute(f"SELECT name, card_number, cvv, card_expiry FROM {TABLE}", (), fetch="all"):
        print(f"  {r['name']:16s}  {r['card_number']}  cvv {r['cvv']}  exp {r['card_expiry']}")


if __name__ == "__main__":
    main()
