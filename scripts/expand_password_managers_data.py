"""Expand password-managers (VaultGuard) base data.

VaultGuard ships with 114 entries / 18 audit events / 4 vaults, which leaves
the audit log and the vault ecosystem sparse. Adds deterministic (seeded)
synthetic data:

  - 12 new vaults owned by Priya Sharma (user 2) and Marcus Chen (user 3):
    personal vaults, Meridian work vaults (QA test accounts, vendor portals,
    client credentials, legacy archive), TrailSync QA, freelance clients.
  - ~4400 new entries spread across those new vaults (logins, secure notes,
    credit cards) with Lakeport/Meridian/Cascadia-flavored fictional brands.
  - 480 new audit_log events (view_password / autofill / edit_entry /
    login_success / login_failed / breach_scan) across all three users.

Task-safety guarantees (annotation "oldest password" task -> Lakeport Public
Library, entry_007, last_changed 2025-01-20T14:00:00Z):
  - NO new entries are added to the main user's accessible vaults
    (vault_001..vault_004); Alex Rivera's UI ranking is untouched.
  - Every new entry's created_at AND updated_at are strictly NEWER than
    2025-01-20T14:00:00Z (floor used: 2025-02-15).
  - No new entry title duplicates an existing title.
  - security_report row (precomputed aggregate) is not modified.

Page-render ceiling: /audit-log renders the whole table unpaginated, so the
audit log is capped at 498 total rows (< ~500). Per-vault entry pages render
one vault at a time; every vault stays under 500 entries.

Insert-only; inserted ids recorded under
data/backups/password-managers-expansion-2026-07-20/inserted_ids.json.

Usage: ~/.conda/envs/miniweb/bin/python scripts/expand_password_managers_data.py [--dry-run]
"""
import json
import random
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "trimmed_miniweb.db"
rng = random.Random(20260720)

Z = "%Y-%m-%dT%H:%M:%SZ"
# every new entry date must be strictly newer than Lakeport (2025-01-20T14:00:00Z)
CREATED_FLOOR = datetime(2025, 2, 15)
CREATED_CEIL = datetime(2026, 5, 20)
UPDATED_CEIL = datetime(2026, 6, 20)
AUDIT_FLOOR = datetime(2025, 7, 1)
AUDIT_CEIL = datetime(2026, 6, 25)
AUDIT_TOTAL_CEILING = 498  # unpaginated /audit-log page: keep < ~500 rows

SYMS = "!@#$%^&*-_+="


def iso(dt):
    return dt.strftime(Z)


def rand_dt(a, b):
    span = int((b - a).total_seconds())
    return a + timedelta(seconds=rng.randint(0, max(span, 1)))


def gen_password(strength):
    n = {"weak": rng.randint(7, 9), "fair": rng.randint(10, 12),
         "strong": rng.randint(13, 16), "excellent": rng.randint(18, 24)}[strength]
    pools = "abcdefghijkmnpqrstuvwxyz" + "ABCDEFGHJKLMNPQRSTUVWXYZ" + "23456789"
    if strength in ("strong", "excellent"):
        pools += SYMS
    if strength == "weak":
        word = rng.choice(["sunset", "coffee", "kitten", "summer", "lakeside",
                           "garden", "harbor", "meadow"])
        return word + str(rng.randint(10, 99))
    return "".join(rng.choice(pools) for _ in range(n))


# ---------------------------------------------------------------------------
# Name pools (fictional, PNW-flavored to match Lakeport/Meridian/Cascadia)
# ---------------------------------------------------------------------------

PLACE = ["Harborview", "Silverpine", "Bluecrest", "Northgate", "Stonebridge",
         "Clearwater", "Redcedar", "Fairhaven", "Maplewood", "Ironpeak",
         "Summitline", "Westbrook", "Larkspur", "Pinehurst", "Galewood",
         "Foxglove", "Rainshadow", "Driftwood", "Alderpoint", "Mossbrook"]
BIZ = ["Logistics", "Dental", "Analytics", "Manufacturing", "Media",
       "Consulting", "Robotics", "Foods", "Outfitters", "Capital",
       "Mutual", "Labs", "Freight", "Clinics", "Hardware", "Textiles",
       "Brewing", "Optics", "Staffing", "Energy"]
PORTAL_KIND = ["Vendor Portal", "Admin Console", "Billing Portal",
               "Support Desk", "SSO Gateway", "Invoicing"]
CLIENT_KIND = ["Client Portal", "Project Workspace", "Deliverables Drive",
               "Status Dashboard", "Contract Vault", "Reporting Login"]
CONSUMER_A = ["Riverbend", "PulsePoint", "Everbloom", "Nightowl", "Trailhead",
              "Cloudberry", "Firefly", "Windrose", "Snowline", "Basecamp",
              "Otterly", "Peakform", "Lumen", "Tidewater", "Cedarline",
              "Brightside", "Quailrun", "Skagit", "Wren", "Juniper"]
CONSUMER_B = ["Grocers", "Streaming", "Botanicals", "Books", "Gear Co.",
              "Fitness", "Records", "Kitchenware", "Photo Cloud", "Banking",
              "Insurance", "Airlines Rewards", "Pharmacy", "Pet Supply",
              "Ticketing", "News+", "Cycling Club", "Coffee Roasters",
              "Home Security", "Meal Kits"]
GAME_A = ["Star", "Iron", "Shadow", "Frost", "Ember", "Void", "Storm",
          "Rune", "Drift", "Nova", "Pixel", "Turbo"]
GAME_B = ["forge Online", "fall Arena", "keep Legends", "bound Tactics",
          "front Racing", "spire Chronicles", "watch League", "craft Realms",
          "born Saga", "core Uprising"]
LEGACY_SYS = ["Intranet", "Timesheet System", "HR Portal", "Wiki", "Build Server",
              "SVN Server", "Bug Tracker", "File Share", "VPN Concentrator",
              "Backup Console", "Phone System", "Badge System", "CMS",
              "FTP Server", "Mail Relay", "Print Server", "Inventory DB",
              "Expense Tool", "CRM (retired)", "Monitoring (Nagios)"]
FIRST = ["Jordan", "Casey", "Morgan", "Riley", "Avery", "Quinn", "Dana",
         "Rowan", "Skyler", "Reese", "Emerson", "Finley", "Harper", "Kendall",
         "Logan", "Micah", "Noel", "Payton", "Sage", "Tatum"]
LAST = ["Alvarez", "Bennett", "Calloway", "Donovan", "Eastman", "Fujita",
        "Grantham", "Holloway", "Ibarra", "Jennings", "Kowalski", "Lindqvist",
        "Moreno", "Novak", "Okafor", "Pruitt", "Quintana", "Reinhart",
        "Sandoval", "Tremblay"]
QA_PRODUCTS = ["MeridianFlow", "MeridianVault", "MeridianLens"]
TAG_POOLS = {
    "qa": ["qa", "test-account", "staging", "meridian"],
    "vendor": ["vendor", "meridian", "procurement", "b2b"],
    "client": ["client", "meridian", "delivery", "b2b"],
    "legacy": ["legacy", "archived", "meridian", "decommissioned"],
    "onboard": ["contractor", "onboarding", "meridian", "temporary"],
    "personal": ["personal", "shopping", "subscription", "finance", "travel"],
    "gaming": ["gaming", "entertainment", "subscription"],
    "trailsync": ["trailsync", "qa", "staging", "side-project"],
    "freelance": ["freelance", "client", "invoicing"],
    "community": ["community", "lakeport", "volunteer", "local"],
}

USER_INFO = {
    2: {"name": "Priya Sharma", "email": "priya.sharma@outlook.com",
        "usernames": ["priya.sharma", "psharma", "priya.sharma@outlook.com",
                      "priya.sharma@meridiansystems.com"],
        "devices": ["Priya's ThinkPad", "Priya's Pixel 8"],
        "ips": ["98.232.117.204", "10.0.1.63", "172.16.4.21"]},
    3: {"name": "Marcus Chen", "email": "marcus.chen@gmail.com",
        "usernames": ["marcus.chen@gmail.com", "mchen_dev", "marcusc",
                      "marcus.chen"],
        "devices": ["Marcus's MacBook Air", "Marcus's Galaxy S24"],
        "ips": ["67.171.88.19", "192.168.1.144"]},
    1: {"name": "Alex Rivera", "email": "alex.rivera@gmail.com",
        "usernames": ["alex.rivera"],
        "devices": ["Alex's MacBook Pro", "Alex's iPhone 15",
                    "Work Laptop - Meridian"],
        "ips": ["73.180.42.115", "10.0.1.47"]},
}

# (id, name, type, owner, shared, members, icon, color, theme, target_entries)
NEW_VAULTS = [
    ("vault_005", "Priya - Personal", "personal", 2, 0, [2], "user", "#4A90D9", "personal", 410),
    ("vault_006", "Priya - Finance & Travel", "personal", 2, 0, [2], "briefcase", "#16A085", "personal", 330),
    ("vault_007", "Meridian QA Test Accounts", "shared", 2, 1, [2, 3], "shield", "#E67E22", "qa", 430),
    ("vault_008", "Meridian Vendor Portals", "shared", 2, 1, [2, 3], "briefcase", "#C0392B", "vendor", 390),
    ("vault_009", "Meridian Client Credentials", "shared", 2, 1, [2, 3], "shield", "#2ECC71", "client", 410),
    ("vault_010", "Meridian Contractor Onboarding", "work", 2, 0, [2], "user", "#8E44AD", "onboard", 300),
    ("vault_011", "Meridian Legacy Systems Archive", "shared", 2, 1, [2, 3], "briefcase", "#7F8C8D", "legacy", 420),
    ("vault_012", "Marcus - Personal", "personal", 3, 0, [3], "user", "#4A90D9", "personal", 400),
    ("vault_013", "Marcus - Gaming", "personal", 3, 0, [3], "rocket", "#9B59B6", "gaming", 280),
    ("vault_014", "TrailSync QA Seeds", "work", 3, 0, [3], "rocket", "#2980B9", "trailsync", 350),
    ("vault_015", "Marcus - Freelance Clients", "work", 3, 0, [3], "briefcase", "#D35400", "freelance", 340),
    ("vault_016", "Lakeport Community Accounts", "personal", 3, 0, [3], "user", "#27AE60", "community", 360),
]


def slug(s):
    return "".join(c for c in s.lower().replace(" ", "").replace(".", "")
                   if c.isalnum())


def make_title(theme, used):
    """Generate a globally unique title for the vault theme."""
    for _ in range(60):
        if theme == "qa":
            t = f"QA Test {rng.choice(QA_PRODUCTS)} #{rng.randint(1, 9999):04d}"
        elif theme == "vendor":
            t = f"{rng.choice(PLACE)} {rng.choice(BIZ)} - {rng.choice(PORTAL_KIND)}"
        elif theme == "client":
            t = f"{rng.choice(PLACE)} {rng.choice(BIZ)} - {rng.choice(CLIENT_KIND)}"
        elif theme == "legacy":
            t = f"Legacy {rng.choice(LEGACY_SYS)} ({rng.randint(2009, 2021)})"
        elif theme == "onboard":
            t = f"Onboarding - {rng.choice(FIRST)} {rng.choice(LAST)} ({rng.choice(['laptop', 'VPN', 'email', 'badge', 'Jira', 'Slack guest'])})"
        elif theme == "gaming":
            t = rng.choice([
                f"{rng.choice(GAME_A)}{rng.choice(GAME_B)}",
                f"{rng.choice(GAME_A)}{rng.choice(GAME_B)} ({rng.choice(['EU', 'NA', 'beta', 'alt'])})",
            ])
        elif theme == "trailsync":
            t = f"TrailSync {rng.choice(['Test User', 'Beta Tester', 'Load Test'])} #{rng.randint(1, 9999):04d}"
        elif theme == "freelance":
            t = f"{rng.choice(PLACE)} {rng.choice(BIZ)} - {rng.choice(['Site Admin', 'Hosting', 'DNS', 'Analytics', 'Deploy Key', 'Staging Login'])}"
        elif theme == "community":
            t = f"{rng.choice(['Lakeport', 'Cascadia', 'Meridian County'])} {rng.choice(['Rec League', 'Food Co-op', 'Trail Assoc.', 'Book Club', 'Garden Society', 'PTA Portal', 'Volunteer Hub', 'Farmers Market', 'Arts Council', 'Kayak Club'])} - {rng.choice(FIRST)}"
        else:  # personal
            t = f"{rng.choice(CONSUMER_A)} {rng.choice(CONSUMER_B)}"
            if rng.random() < 0.35:
                t += f" ({rng.choice(['family', 'annual plan', 'rewards', 'premium', 'legacy acct'])})"
        key = t.lower()
        if key not in used:
            used.add(key)
            return t
    # deterministic fallback
    n = len(used)
    t = f"{rng.choice(CONSUMER_A)} {rng.choice(CONSUMER_B)} #{n}"
    used.add(t.lower())
    return t


NOTE_TMPL = [
    "", "", "", "",
    "Imported from browser export on {d}.",
    "Rotated after phishing advisory in {m}.",
    "Shared credentials - do not change without notifying the team.",
    "Account uses security questions; answers stored in secure note.",
    "Auto-renews annually. Cancel 30 days before renewal.",
    "2FA enabled via authenticator app.",
    "Temporary account - review at next quarterly cleanup.",
]


def make_entry(eid, vault, theme, owner_uid, used_titles):
    title = make_title(theme, used_titles)
    created = rand_dt(CREATED_FLOOR, CREATED_CEIL)
    updated = created + timedelta(days=rng.randint(0, 240),
                                  hours=rng.randint(0, 20))
    updated = min(updated, UPDATED_CEIL)
    last_used = rand_dt(updated, UPDATED_CEIL)

    r = rng.random()
    if theme in ("qa", "trailsync", "onboard", "legacy"):
        category = "login" if r < 0.96 else "secure_note"
    else:
        category = "login" if r < 0.88 else ("secure_note" if r < 0.965 else "credit_card")

    info = USER_INFO[owner_uid]
    site_slug = slug(title.split(" - ")[0].split(" #")[0].split(" (")[0])[:24] or "portal"
    tags = sorted(rng.sample(TAG_POOLS[theme], rng.randint(1, 3)))
    note = rng.choice(NOTE_TMPL).format(
        d=created.strftime("%Y-%m-%d"),
        m=created.strftime("%B %Y"))

    entry = {
        "id": eid, "vault_id": vault, "title": title,
        "url": "", "username": "", "password": "",
        "category": category, "notes": note,
        "created_at": iso(created), "updated_at": iso(updated),
        "last_used": iso(last_used), "strength": "",
        "favorite": 1 if rng.random() < 0.03 else 0,
        "tags": json.dumps(tags), "card_details": "",
    }

    if category == "login":
        strength = rng.choices(["excellent", "strong", "fair", "weak"],
                               weights=[50, 32, 12, 6])[0]
        entry["strength"] = strength
        entry["password"] = gen_password(strength)
        if theme == "qa":
            n = title.split("#")[-1]
            entry["username"] = f"qa+{n}@meridiansystems.com"
            entry["url"] = f"https://staging.{title.split()[2].lower()}.com/login"
        elif theme == "trailsync":
            n = title.split("#")[-1]
            entry["username"] = f"test+{n}@trailsync.app"
            entry["url"] = "https://staging.trailsync.app/login"
        elif theme == "onboard":
            person = title.split(" - ")[1].split(" (")[0]
            uname = person.lower().replace(" ", ".")
            entry["username"] = f"{uname}@meridiansystems.com"
            entry["url"] = "https://onboarding.meridiansystems.com"
        elif theme in ("vendor", "client", "freelance"):
            entry["username"] = rng.choice([
                f"meridian-ops@{site_slug}.com",
                info["email"],
                f"{info['usernames'][0].split('@')[0].replace('.', '')}@{site_slug}.com",
            ]) if theme != "freelance" else rng.choice([
                f"admin@{site_slug}.com", info["email"]])
            entry["url"] = f"https://portal.{site_slug}.com"
        elif theme == "legacy":
            entry["username"] = rng.choice(["administrator", "svc_legacy",
                                            "root", info["usernames"][1]])
            entry["url"] = f"https://{site_slug}.internal.meridiansystems.com"
        else:  # personal / gaming / community
            entry["username"] = rng.choice(info["usernames"])
            entry["url"] = f"https://www.{site_slug}.com"
    elif category == "secure_note":
        entry["notes"] = rng.choice([
            f"WiFi password for {title}: {gen_password('strong')}",
            f"License key: {rng.randint(10000, 99999)}-{rng.randint(10000, 99999)}-{rng.randint(10000, 99999)}",
            f"Recovery codes: {', '.join(str(rng.randint(100000, 999999)) for _ in range(4))}",
            f"Security answers for {title}. First school = Lakeport Elementary.",
            f"Door/locker code: {rng.randint(1000, 9999)}",
        ])
    else:  # credit_card
        brand = rng.choice(["Visa", "Mastercard", "Amex"])
        holder = info["name"]
        entry["card_details"] = json.dumps({
            "cardholder_name": holder,
            "card_number_last4": f"{rng.randint(1000, 9999)}",
            "expiration": f"{rng.randint(1, 12):02d}/{rng.randint(2026, 2030)}",
            "brand": brand,
            "billing_address": f"{rng.randint(100, 9999)} {rng.choice(PLACE)} {rng.choice(['Ave', 'St', 'Ln', 'Dr'])}, Lakeport, WA 984{rng.randint(0, 9)}{rng.randint(0, 9)}",
        })
        entry["title"] = f"{brand} Card - {title}"
        if entry["title"].lower() in used_titles:
            entry["title"] += f" ({eid[-4:]})"
        used_titles.add(entry["title"].lower())
    return entry


AUDIT_DETAILS = {
    "view_password": ["Viewed password", "Copied password to clipboard",
                      "Viewed password for {t}", "Copied username and password"],
    "autofill": ["Browser autofill triggered for {u}",
                 "Mobile app autofill for {t}"],
    "edit_entry": ["Updated password after scheduled rotation",
                   "Edited notes and tags", "Updated URL for {t}",
                   "Rotated password (quarterly policy)"],
}


def build_audit(rows_budget, all_entries_by_vault, vault_members):
    """Generate audit rows. all_entries_by_vault: vault_id -> [(id,title,url,created_at)]."""
    rows = []
    next_id = 19
    vault_ids = [v for v, es in all_entries_by_vault.items() if es]
    for _ in range(rows_budget):
        aid = f"audit_{next_id:03d}"
        next_id += 1
        r = rng.random()
        if r < 0.86:
            action = rng.choices(["view_password", "autofill", "edit_entry"],
                                 weights=[45, 45, 10])[0]
            vid = rng.choice(vault_ids)
            eid, title, url, created = rng.choice(all_entries_by_vault[vid])
            uid = rng.choice(vault_members[vid])
            floor = max(AUDIT_FLOOR, datetime.strptime(created, Z))
            ts = rand_dt(floor, AUDIT_CEIL)
            info = USER_INFO[uid]
            detail = rng.choice(AUDIT_DETAILS[action]).format(
                t=title, u=(url.replace("https://", "") or title))
            rows.append({"id": aid, "timestamp": iso(ts), "user_id": uid,
                         "action": action, "entry_id": eid, "entry_title": title,
                         "vault_id": vid, "ip_address": rng.choice(info["ips"]),
                         "device": rng.choice(info["devices"]), "details": detail})
        elif r < 0.95:
            uid = rng.choice([1, 2, 3])
            info = USER_INFO[uid]
            ok = rng.random() < 0.8
            ts = rand_dt(AUDIT_FLOOR, AUDIT_CEIL)
            rows.append({
                "id": aid, "timestamp": iso(ts), "user_id": uid,
                "action": "login_success" if ok else "login_failed",
                "entry_id": "", "entry_title": "", "vault_id": "",
                "ip_address": rng.choice(info["ips"]),
                "device": rng.choice(info["devices"]),
                "details": ("Vault unlocked with master password."
                            + (" 2FA verified via authenticator app." if uid != 3 else ""))
                if ok else f"Incorrect master password attempt. {rng.randint(1, 3)} of 5 attempts."})
        else:
            uid = rng.choice([1, 2, 3])
            info = USER_INFO[uid]
            ts = rand_dt(AUDIT_FLOOR, AUDIT_CEIL)
            rows.append({
                "id": aid, "timestamp": iso(ts), "user_id": uid,
                "action": "breach_scan", "entry_id": "", "entry_title": "",
                "vault_id": "", "ip_address": rng.choice(info["ips"]),
                "device": rng.choice(info["devices"]),
                "details": rng.choice([
                    "Automated breach scan completed. No new breaches found.",
                    "Scheduled dark-web scan finished. 0 new alerts.",
                    "Weekly breach scan: all monitored emails clear.",
                ])})
    return rows


def main():
    dry = "--dry-run" in sys.argv
    db = sqlite3.connect(str(DB_PATH), timeout=60)
    db.row_factory = sqlite3.Row

    existing_titles = {r["title"].lower() for r in db.execute(
        "SELECT title FROM password_managers_entries")}
    existing_entry_ids = {r["id"] for r in db.execute(
        "SELECT id FROM password_managers_entries")}
    existing_vault_ids = {r["id"] for r in db.execute(
        "SELECT id FROM password_managers_vaults")}
    audit_count = db.execute(
        "SELECT COUNT(*) FROM password_managers_audit_log").fetchone()[0]
    max_num = db.execute(
        "SELECT MAX(CAST(SUBSTR(id, 7) AS INT)) FROM password_managers_entries "
        "WHERE id LIKE 'entry~_%' ESCAPE '~'").fetchone()[0] or 0

    used_titles = set(existing_titles)
    vaults_new, entries_new = [], []
    entries_by_new_vault = {}
    next_num = max_num + 1

    for vid, name, vtype, owner, shared, members, icon, color, theme, target in NEW_VAULTS:
        assert vid not in existing_vault_ids, f"vault id collision: {vid}"
        ventries = []
        for _ in range(target):
            eid = f"entry_{next_num:03d}"
            next_num += 1
            assert eid not in existing_entry_ids
            e = make_entry(eid, vid, theme, owner, used_titles)
            ventries.append(e)
        entries_new.extend(ventries)
        entries_by_new_vault[vid] = ventries
        v_created = rand_dt(datetime(2025, 2, 20), datetime(2025, 11, 1))
        v_updated = max(datetime.strptime(e["updated_at"], Z) for e in ventries)
        vaults_new.append({
            "id": vid, "name": name, "type": vtype, "owner_user_id": owner,
            "shared": shared,
            "members": json.dumps([{"user_id": m,
                                    "role": "owner" if (m == owner and not shared)
                                    else ("admin" if m == owner else "member")}
                                   for m in members]),
            "icon": icon, "color": color, "item_count": len(ventries),
            "created_at": iso(v_created), "updated_at": iso(v_updated),
        })

    # audit rows: cap the unpaginated /audit-log page below the ceiling
    audit_budget = AUDIT_TOTAL_CEILING - audit_count
    # membership map: existing vaults + new vaults
    vault_members = {"vault_001": [1], "vault_002": [1],
                     "vault_003": [2, 1, 3], "vault_004": [1, 3]}
    all_by_vault = {}
    for r in db.execute("SELECT id, title, url, created_at, vault_id "
                        "FROM password_managers_entries"):
        all_by_vault.setdefault(r["vault_id"], []).append(
            (r["id"], r["title"], r["url"], r["created_at"]))
    for vrow in NEW_VAULTS:
        vault_members[vrow[0]] = list(vrow[5])
    for vid, ventries in entries_by_new_vault.items():
        all_by_vault[vid] = [(e["id"], e["title"], e["url"], e["created_at"])
                             for e in ventries]
    # drop vaults not in membership map (none expected)
    all_by_vault = {v: es for v, es in all_by_vault.items() if v in vault_members}
    audit_new = build_audit(audit_budget, all_by_vault, vault_members)

    print(f"vaults: +{len(vaults_new)}, entries: +{len(entries_new)}, "
          f"audit_log: +{len(audit_new)} (page ceiling {AUDIT_TOTAL_CEILING})")

    # safety: every new entry newer than Lakeport on both date fields
    lakeport = "2025-01-20T14:00:00Z"
    bad = [e for e in entries_new
           if e["created_at"] <= lakeport or e["updated_at"] <= lakeport]
    assert not bad, f"{len(bad)} entries violate Lakeport date floor"
    per_vault_max = max(len(v) for v in entries_by_new_vault.values())
    assert per_vault_max < 500, "vault page would render >=500 rows"

    if dry:
        for e in entries_new[:6]:
            print(" ", e["vault_id"], e["category"], e["strength"] or "-",
                  "|", e["title"][:60], "|", e["created_at"])
        for a in audit_new[:4]:
            print(" ", a["timestamp"], "u" + str(a["user_id"]), a["action"],
                  "|", (a["entry_title"] or a["details"])[:60])
        return

    bdir = ROOT / "data" / "backups" / "password-managers-expansion-2026-07-20"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "inserted_ids.json").write_text(json.dumps({
        "vaults": [v["id"] for v in vaults_new],
        "entries": [e["id"] for e in entries_new],
        "audit_log": [a["id"] for a in audit_new]}, indent=1))

    for table, rows in (("vaults", vaults_new), ("entries", entries_new),
                        ("audit_log", audit_new)):
        if not rows:
            continue
        cols = list(rows[0].keys())
        db.executemany(
            f"INSERT INTO password_managers_{table} ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' * len(cols))})",
            [[r[c] for c in cols] for r in rows])

    # sync FTS indexes for touched tables that have one
    for t in ("password_managers_entries", "password_managers_audit_log"):
        has = db.execute("SELECT name FROM sqlite_master WHERE name = ?",
                         (f"fts_{t}",)).fetchone()
        if has:
            db.execute(f"INSERT INTO [fts_{t}]([fts_{t}]) VALUES('rebuild')")
    db.commit()
    print(f"inserted; rollback ids at {bdir}/inserted_ids.json")


if __name__ == "__main__":
    main()
