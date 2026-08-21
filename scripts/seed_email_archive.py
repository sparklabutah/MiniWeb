"""Seed a historical email archive (2023 -> mid-2026) for cross-site search tasks.

The WebMail corpus is Enron-2001 noise plus a handful of recent bridge emails, so
"dig into old emails" tasks had nothing real to find. This adds ~150 dated,
deterministic emails to the 5 users' inboxes whose contents reference REAL
entities on other sites, so cross-site search macros are gradeable end-to-end:

  - banking payees   -> monthly utility/rent bills (payee name, PAY- account, amount)
  - banking txns     -> card-charge alerts matching real transactions
  - SkyLodge Travel  -> booking confirmations (booking #, total, date) + confirmation codes
  - Cascadia Insurance -> policy renewal notices (policy number, premium, renewal date)
  - e-commerce       -> order/shipping confirmations naming real products + prices
  - calendar-todo    -> event invitations/reminders (title, location, start)
  - generic          -> newsletters, security codes, delivery notices (searchable filler)

Deterministic (random.Random(42)) + idempotent: message_id PK is
<archive-NNNN@miniweb.local> and rows are INSERT OR REPLACE'd into the BASE
email_emails table. Re-run after any DB rebuild (then push to railway).
NOTE: the email site caches the corpus per process — restart the server after seeding.

Run: ~/.conda/envs/miniweb/bin/python scripts/seed_email_archive.py
"""
import random
import sys
import pathlib
from datetime import datetime, timedelta

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from app import create_app  # noqa: E402

USERS = {
    1: "alex.rivera@meridiansystems.com",
    2: "priya.sharma@meridiansystems.com",
    3: "marcus.chen@meridiansystems.com",
    4: "jessica.okafor@meridiansystems.com",
    7: "david.petrov@meridiansystems.com",
}
# auto-login user (1) gets the lion's share so tasks "just work"
RECIPIENT_CYCLE = [1, 1, 1, 2, 1, 3, 1, 4, 1, 7]

rng = random.Random(42)
emails = []  # (from_, to, subject, date_dt, body)


def add(from_, uid, subject, dt, body):
    emails.append((from_, USERS[uid], subject, dt, body))


def dt_in(year, month, day=None, hour=None):
    return datetime(year, month, day or rng.randint(2, 27),
                    hour if hour is not None else rng.randint(7, 20),
                    rng.choice([0, 5, 12, 24, 31, 45, 58]))


def code(prefix, n, length=6):
    """Deterministic pseudo-code from a namespace + number (stable across runs)."""
    r = random.Random(f"{prefix}-{n}")
    return "".join(r.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(length))


app = create_app()
with app.test_request_context():
    from app import db
    conn = db._get_conn()

    # ---- banking: monthly bills from real payees (user 1's payees) ---------
    payees = db.query("banking", "payees", where={"user_id": 1}, limit=20)
    bill_payees = [p for p in payees if p.get("category") not in (None, "", "person")][:5] or payees[:5]
    for p in bill_payees:
        base_amt = {"Xfinity Internet": 79.99, "Puget Sound Energy": 0,
                    "T-Mobile Wireless": 95.00, "Mendez Properties": 2350.00}.get(p["name"], 0)
        for year, month in [(y, m) for y in (2024, 2025) for m in range(1, 13, 2)]:
            amt = base_amt or round(rng.uniform(45, 240), 2)
            if p["name"] == "Puget Sound Energy":       # seasonal energy bill
                amt = round(88 + 60 * (1 if month in (1, 11) else 0.3) + rng.uniform(-8, 8), 2)
            dt = dt_in(year, month, day=3, hour=9)
            add(f"billing@{p['name'].lower().replace(' ', '')}.com", 1,
                f"Your {p['name']} statement for {dt.strftime('%B %Y')}",
                dt,
                f"Dear customer,\n\nYour {p['name']} bill for {dt.strftime('%B %Y')} is ready.\n\n"
                f"Amount due: ${amt:.2f}\nPayee account: {p['account_number']}\n"
                f"Due date: {dt.replace(day=21).strftime('%B %d, %Y')}\n\n"
                f"You can pay this bill from SecureBank Online -> Pay Bills using payee account {p['account_number']}.\n\n"
                f"Thank you,\n{p['name']} Billing")

    # ---- banking: charge alerts matching real transactions -----------------
    txns = db.execute(
        "SELECT * FROM banking_transactions WHERE user_id=1 AND type='debit' "
        "AND amount > 40 ORDER BY id LIMIT 12", ())
    for t in txns:
        try:
            dt = datetime.strptime(t["date"], "%Y-%m-%d").replace(hour=rng.randint(8, 21), minute=rng.randint(0, 59))
        except (ValueError, TypeError):
            continue
        add("alerts@securebank-online.com", 1,
            f"Card charge alert: ${t['amount']:.2f} at {t['description']}",
            dt,
            f"SecureBank Online transaction alert\n\n"
            f"A debit of ${t['amount']:.2f} was posted to your account on {t['date']}.\n"
            f"Merchant: {t['description']}\nCategory: {t.get('category', '')}\nReference: {t.get('reference', '')}\n\n"
            f"If you do not recognize this charge, contact us immediately.")

    # ---- SkyLodge Travel: booking confirmations ----------------------------
    bookings = db.query("flights-hotels", "bookings", limit=30)
    for b in bookings[:14]:
        uid = b.get("user_id") if b.get("user_id") in USERS else 1
        try:
            dt = datetime.strptime(b["booking_date"], "%Y-%m-%d").replace(hour=11, minute=17)
        except (ValueError, TypeError):
            continue
        conf = code("skylodge", b["id"])
        kind = "flight" if b.get("type") == "flight" else "hotel stay"
        add("reservations@skylodgetravel.com", uid,
            f"SkyLodge Travel — your {kind} is confirmed (Booking #{b['id']})",
            dt,
            f"Thank you for booking with SkyLodge Travel!\n\n"
            f"Booking number: {b['id']}\nConfirmation code: {conf}\n"
            f"Type: {b.get('type', '')}\nStatus: {b.get('status', '')}\n"
            f"Total price: ${b.get('total_price', 0):.2f}\nTravelers: {b.get('travelers', 1)}\n"
            f"Booked on: {b['booking_date']}\n\n"
            f"Manage this booking any time on SkyLodge Travel.")

    # ---- Cascadia Insurance: policy renewal notices ------------------------
    policies = db.query("insurance-loans", "policies", limit=20)
    for pol in policies[:10]:
        uid = pol.get("user_id") if pol.get("user_id") in USERS else 1
        try:
            renew = datetime.strptime(pol["renewal_date"], "%Y-%m-%d")
        except (ValueError, TypeError):
            continue
        dt = renew - timedelta(days=30)
        if dt > datetime(2026, 6, 30):      # keep everything in the past
            dt = datetime(2026, rng.randint(1, 5), rng.randint(2, 27), 10, 5)
        add("policies@cascadia-insurance.com", uid,
            f"Renewal notice — {pol.get('type', 'insurance').title()} policy {pol['policy_number']}",
            dt,
            f"Dear {pol.get('policyholder_name', 'policyholder')},\n\n"
            f"Your {pol.get('type', '')} policy {pol['policy_number']} renews on {pol['renewal_date']}.\n"
            f"Monthly premium: ${pol.get('premium_monthly', 0):.2f}\n"
            f"Annual premium: ${pol.get('premium_annual', 0):.2f}\n"
            f"Deductible: ${pol.get('deductible', 0):.2f}\n\n"
            f"No action is needed if your payment method is up to date.\n\n"
            f"Cascadia Insurance & Lending")

    # ---- e-commerce: order + shipping confirmations for real products -----
    # (products table has no id column and prices live in `pricing` as "$9.69")
    products = db.query("e-commerce", "products", limit=40)
    for i, prod in enumerate(products[:12]):
        uid = RECIPIENT_CYCLE[i % len(RECIPIENT_CYCLE)]
        order_no = f"ORD-{2023 + i % 3}-{4100 + i * 37}"
        dt = dt_in(2023 + i % 3, (i * 5) % 12 + 1)
        try:
            price = float(str(prod.get("pricing", "") or prod.get("list_price", "") or "0")
                          .replace("$", "").replace(",", "").split()[0])
        except (ValueError, IndexError):
            price = 0.0
        add("orders@shophub.com", uid,
            f"Order {order_no} confirmed — {prod.get('name', 'your item')}",
            dt,
            f"Thanks for your order!\n\nOrder number: {order_no}\n"
            f"Item: {prod.get('name', '')}\nPrice: ${price:.2f}\n"
            f"Order total: ${round(price * 1.101, 2):.2f} (incl. tax & shipping)\n"
            f"Placed on: {dt.strftime('%B %d, %Y')}\n\n"
            f"Track your package with tracking number {code('track', i, 10)}.")
        add("orders@shophub.com", uid,
            f"Your order {order_no} has shipped",
            dt + timedelta(days=2, hours=5),
            f"Good news — order {order_no} ({prod.get('name', '')}) has shipped.\n"
            f"Tracking number: {code('track', i, 10)}\n"
            f"Estimated delivery: {(dt + timedelta(days=6)).strftime('%B %d, %Y')}")

    # ---- calendar-todo: invitations / reminders ----------------------------
    events = db.query("calendar-todo", "events", limit=20)
    for i, ev in enumerate(events[:8]):
        uid = ev.get("user_id") if ev.get("user_id") in USERS else RECIPIENT_CYCLE[i % len(RECIPIENT_CYCLE)]
        start = str(ev.get("start", ""))[:16].replace("T", " ")
        try:
            dt = datetime.strptime(start[:10], "%Y-%m-%d") - timedelta(days=7)
        except (ValueError, TypeError):
            continue
        if dt > datetime(2026, 6, 30):
            dt = datetime(2026, rng.randint(1, 5), rng.randint(2, 27))
        dt = dt.replace(hour=rng.randint(8, 17), minute=30)
        add("invites@calendartodo.app", uid,
            f"Invitation: {ev.get('title', 'event')}",
            dt,
            f"You have been invited to \"{ev.get('title', '')}\".\n\n"
            f"When: {start}\nWhere: {ev.get('location', 'TBD') or 'TBD'}\n"
            f"Details: {ev.get('description', '') or '—'}\n\n"
            f"This event is on your CalendarTodo calendar.")

    # ---- generic filler: codes, deliveries, newsletters --------------------
    for i in range(18):
        uid = RECIPIENT_CYCLE[i % len(RECIPIENT_CYCLE)]
        kind = i % 3
        dt = dt_in(2023 + i % 4 if i % 4 < 3 else 2026, (i * 7) % 12 + 1)
        if dt > datetime(2026, 6, 30):
            dt = dt.replace(year=2025)
        if kind == 0:
            svc = ["CloudVault", "StreamBox", "FitTrack", "NewsDaily", "PhotoShare", "DevHub"][i % 6]
            add(f"security@{svc.lower()}.com", uid,
                f"Your {svc} verification code",
                dt,
                f"Your one-time verification code is {code(svc, i)}.\n\n"
                f"This code expires in 10 minutes. If you didn't request it, ignore this email.")
        elif kind == 1:
            add("no-reply@parcelrun.com", uid,
                f"Package delivered — {dt.strftime('%B %d')}",
                dt,
                f"Your package with tracking number {code('parcel', i, 10)} was delivered on "
                f"{dt.strftime('%B %d, %Y')} at {dt.strftime('%I:%M %p')}.\n"
                f"Left at: front door.")
        else:
            topic = ["Q{} market roundup", "Weekly digest #{}", "What's new — issue {}"][i % 3].format(i + 4)
            add("newsletter@techweekly.io", uid,
                topic,
                dt,
                f"{topic}\n\nHighlights this week: cloud spend optimization, "
                f"open-source security audits, and the state of web agents.\n\n"
                f"Unsubscribe any time in Settings.")

    # ---- write to the BASE table (idempotent by message_id) ----------------
    table = db.get_table_name("email", "emails")
    n = 0
    for i, (from_, to, subject, dt, body) in enumerate(emails, 1):
        mid = f"<archive-{i:04d}@miniweb.local>"
        conn.execute(
            f"INSERT OR REPLACE INTO [{table}] "
            f"(from_, [to], cc, subject, date, body, message_id, path) "
            f"VALUES (?, ?, '', ?, ?, ?, ?, ?)",
            (from_, to, subject, dt.strftime("%a, %d %b %Y %H:%M:%S -0700"),
             body, mid, f"archive/{i:04d}"))
        n += 1
    conn.commit()

    total = conn.execute(
        f"SELECT COUNT(*) FROM [{table}] WHERE message_id LIKE '<archive-%'").fetchone()[0]
    years = conn.execute(
        f"SELECT substr(date, 13, 4) y, COUNT(*) c FROM [{table}] "
        f"WHERE message_id LIKE '<archive-%' GROUP BY y ORDER BY y").fetchall()
    print(f"seeded {n} archive emails ({total} in table)")
    print("by year:", [(r[0], r[1]) for r in years])
