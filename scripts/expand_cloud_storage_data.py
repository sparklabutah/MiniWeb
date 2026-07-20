"""Expand cloud-storage-file-transfer (MeridianCloud) base data.

The site ships with 508 rows (453 files, 28 folders, 12 shares, 10 transfers,
5 users). This adds deterministic (seeded) synthetic rows to reach 5000+ while
keeping every saved annotation task valid:

- The drive view (routes.py index) renders ALL non-trashed files with no
  pagination, so active files stay capped below ~500 total: only 45 new active
  files are added, all owned by non-main users, dated 2024-2025 so the top of
  the default modified-desc list and the Recent top-20 are unchanged.
- 100 additional files are trashed (is_trashed=1) so they never appear in the
  drive/starred/shared/folder views; the Trash page renders ~100 rows.
- Bulk volume goes to transfers (older 2024-2026 send history, statuses
  completed/expired only — never active) and shares. Neither has an unbounded
  HTML page; per-file detail pages are capped (<=18 transfers, <=6 shares per
  file).
- ZERO new rows have starred=1 (task: "number of starred files" == 5).
- ZERO new files in any folder owned by alex.chen (user 1), especially folder 1
  "Projects" (task: "star all pdf documents in Projects").
- No new names contain "Q4"/"roadmap" (task: Q4 roadmap doc stays the unique
  search hit) or "Machine Learning"/"Paper Notes" (invite task), and no
  recipient email uses marcroy@gmail.com.
- Share rows are first backfilled from existing files' shared_with JSON lists
  (making base data MORE consistent), then new-file shares + link shares.

Insert-only — existing rows are never touched. Inserted ids are recorded in
data/backups/cloud-storage-file-transfer-expansion-2026-07-20/inserted_ids.json.

Usage: ~/.conda/envs/miniweb/bin/python scripts/expand_cloud_storage_data.py [--dry-run]
"""
import datetime
import json
import random
import sqlite3
import string
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "trimmed_miniweb.db"

rng = random.Random(20260720)

MAIN_USER = 1  # alex.chen — never owns new active files/folders

# tokens that must never appear in any new name/path (annotation tasks)
FORBIDDEN = ("q4", "roadmap", "machine learning", "paper notes", "marcroy")

NEW_USERS = [
    ("sofia.reyes", "Sofia Reyes", "QA Engineer"),
    ("james.okafor", "James Okafor", "Backend Developer"),
    ("mei.tanaka", "Mei Tanaka", "Data Analyst"),
    ("liam.oconnor", "Liam O'Connor", "Site Reliability Engineer"),
    ("hannah.lindqvist", "Hannah Lindqvist", "Marketing Manager"),
    ("omar.haddad", "Omar Haddad", "Security Engineer"),
    ("grace.wu", "Grace Wu", "Frontend Developer"),
    ("tyler.nguyen", "Tyler Nguyen", "Support Lead"),
    ("isabella.moretti", "Isabella Moretti", "Content Strategist"),
    ("noah.petersen", "Noah Petersen", "Sales Engineer"),
    ("aisha.bello", "Aisha Bello", "HR Coordinator"),
    ("carlos.mendes", "Carlos Mendes", "Mobile Developer"),
    ("emily.novak", "Emily Novak", "Finance Analyst"),
    ("ravi.patel", "Ravi Patel", "Platform Engineer"),
    ("julia.kowalski", "Julia Kowalski", "Office Manager"),
]

AVATAR_COLORS = ["#4285F4", "#EA4335", "#34A853", "#FBBC04", "#9C27B0",
                 "#0f9d58", "#ab47bc", "#db4437", "#f4b400", "#9E9E9E"]
FOLDER_COLORS = AVATAR_COLORS

ROOT_FOLDERS = ["Archive 2025", "Engineering", "Compliance", "Team Events"]
SUB_FOLDER_NAMES = [
    "Invoices 2024", "Invoices 2025", "Retro Notes", "Load Test Results",
    "Release Notes", "Customer Feedback", "Brand Assets", "Print Materials",
    "Conference Talks", "Payroll Exports", "Audit Trails", "SOC2 Evidence",
    "Runbooks", "Postmortems", "Icons", "Stock Photos", "Contract Drafts",
    "Interview Packets", "Benchmarks", "Migration Plans", "Newsletter Drafts",
    "Offsite 2025", "Hackathon", "Demo Videos", "API Specs", "Style Guides",
    "Expense Reports", "Training Materials", "Product Screenshots",
    "Localization", "Beta Program", "Backups", "Sales Decks", "Case Studies",
    "Press Kit", "Onboarding Docs", "QA Checklists", "Sprint Boards",
    "Sketches", "User Research", "Changelogs", "Certificates",
    "Vendor Quotes", "Analytics Exports", "Legacy Exports", "Team Photos",
]

# existing folders owned by non-main users that can absorb a few files
OTHER_USER_FOLDERS = [16, 17, 18, 20, 21, 22, 23, 24, 25, 27, 28]

SUBJECTS = [
    "Onboarding checklist", "Vendor comparison", "Sprint retro summary",
    "Load test report", "Release checklist", "Customer interview notes",
    "Brand color audit", "Print quote", "Conference slides",
    "Payroll export", "Access review", "Incident postmortem",
    "Deploy runbook", "Icon set", "Team offsite photos", "Contract draft",
    "Interview scorecard", "Benchmark results", "Migration plan",
    "Newsletter draft", "Hackathon ideas", "Demo recording notes",
    "API spec", "Style guide", "Expense report", "Training deck",
    "Product screenshots", "Localization strings", "Beta feedback",
    "Backup manifest", "Sales deck", "Case study", "Press release",
    "QA checklist", "Sprint board export", "Wireframe sketch",
    "User research findings", "Changelog", "Compliance certificate",
    "Vendor quote", "Analytics export", "Standup notes", "Budget worksheet",
    "Capacity plan", "Error budget review", "Design tokens",
    "Meeting recording transcript", "Security scan results",
    "Performance profile", "Marketing calendar",
]
SUFFIXES = ["", "", "", " v2", " v3", " draft", " FINAL", " OLD", " — copy",
            " 2024", " 2025", " (updated)", " (archived)"]

TYPE_EXT = {
    "document": [".docx", ".txt", ".pdf", ".md"],
    "spreadsheet": [".xlsx", ".csv"],
    "image": [".png", ".jpg", ".svg"],
    "presentation": [".pptx"],
    "archive": [".zip", ".tar.gz"],
    "code": [".py", ".json", ".yaml"],
    "design": [".fig", ".design"],
}
TYPES = list(TYPE_EXT)
TYPE_WEIGHTS = [30, 20, 18, 10, 6, 8, 8]

TEAM_ALIASES = [
    "dev-team@meridiansystems.com", "ops-team@meridiansystems.com",
    "board@meridiansystems.com", "archives@meridiansystems.com",
    "security-review@meridiansystems.com", "design-team@meridiansystems.com",
    "finance@meridiansystems.com", "hr@meridiansystems.com",
]
EXTERNAL_EMAILS = [
    "cto@acmecorp.com", "procurement@acmecorp.com",
    "ux-review@designpartners.io", "print@lakeportprints.com",
    "legal@hartwellassoc.com", "billing@northstarvendors.com",
    "audit@cascadiacompliance.com", "events@lakeportvenues.com",
    "freelance-designer@gmail.com", "contract.writer@gmail.com",
    "photo.studio.lakeport@gmail.com",
]

MAX_TRANSFERS_PER_FILE = 18
MAX_SHARES_PER_FILE = 6


def clean(name):
    low = name.lower()
    assert not any(tok in low for tok in FORBIDDEN), f"forbidden token in {name!r}"
    return name


def ts(year_lo, year_hi):
    """Random ISO timestamp between Jan 1 of year_lo and Dec 31 of year_hi."""
    start = datetime.datetime(year_lo, 1, 1)
    end = datetime.datetime(year_hi, 12, 31, 23, 59)
    sec = rng.randint(0, int((end - start).total_seconds()))
    return (start + datetime.timedelta(seconds=sec)).strftime("%Y-%m-%dT%H:%M:%SZ")


def ts_between(lo_iso, hi_iso):
    lo = datetime.datetime.strptime(lo_iso, "%Y-%m-%dT%H:%M:%SZ")
    hi = datetime.datetime.strptime(hi_iso, "%Y-%m-%dT%H:%M:%SZ")
    if hi <= lo:
        return lo_iso
    sec = rng.randint(0, int((hi - lo).total_seconds()))
    return (lo + datetime.timedelta(seconds=sec)).strftime("%Y-%m-%dT%H:%M:%SZ")


def plus_days(iso_ts, days):
    t = datetime.datetime.strptime(iso_ts, "%Y-%m-%dT%H:%M:%SZ")
    return (t + datetime.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    dry = "--dry-run" in sys.argv
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.row_factory = sqlite3.Row
    T = "cloud_storage_file_transfer"

    existing_users = [dict(r) for r in db.execute(f"SELECT * FROM {T}_users ORDER BY id")]
    existing_files = [dict(r) for r in db.execute(f"SELECT * FROM {T}_files ORDER BY id")]
    existing_share_pairs = {(r["file_id"], r["shared_with"]) for r in
                            db.execute(f"SELECT file_id, shared_with FROM {T}_shares")}
    next_id = {t: db.execute(f"SELECT COALESCE(MAX(id),0)+1 FROM {T}_{t}").fetchone()[0]
               for t in ("files", "folders", "shares", "transfers", "users")}

    new = {"users": [], "folders": [], "files": [], "shares": [], "transfers": []}

    # ---- users ----------------------------------------------------------
    for username, name, role in NEW_USERS:
        uid = next_id["users"]
        next_id["users"] += 1
        new["users"].append({
            "id": uid, "username": username,
            "password": "meridian" + (str(uid) * 3)[:3],
            "name": name, "email": f"{username}@meridiansystems.com",
            "role": role, "avatar_color": rng.choice(AVATAR_COLORS),
            "storage_quota_gb": rng.choice([50, 50, 50, 100]),
            "storage_used_bytes": rng.randint(50, 3800) * 1024 * 1024,
        })
    all_user_ids = [u["id"] for u in existing_users] + [u["id"] for u in new["users"]]
    other_user_ids = [u for u in all_user_ids if u != MAIN_USER]
    user_email = {u["id"]: u["email"] for u in existing_users}
    user_email.update({u["id"]: u["email"] for u in new["users"]})

    # ---- folders --------------------------------------------------------
    root_ids = []
    for name in ROOT_FOLDERS:
        fid = next_id["folders"]
        next_id["folders"] += 1
        root_ids.append(fid)
        new["folders"].append({
            "id": fid, "name": clean(name), "parent_id": 0,
            "owner_id": rng.choice([2, 3, 7, 12]),
            "created_at": ts(2024, 2025), "color": rng.choice(FOLDER_COLORS),
        })
    sub_names = SUB_FOLDER_NAMES[:]
    rng.shuffle(sub_names)
    new_folder_ids = list(root_ids)
    for name in sub_names[:46]:
        fid = next_id["folders"]
        next_id["folders"] += 1
        new_folder_ids.append(fid)
        new["folders"].append({
            "id": fid, "name": clean(name),
            "parent_id": rng.choice(root_ids + OTHER_USER_FOLDERS[:4]),
            "owner_id": rng.choice(other_user_ids),
            "created_at": ts(2024, 2025), "color": rng.choice(FOLDER_COLORS),
        })
    folder_created = {f["id"]: f["created_at"] for f in new["folders"]}

    # ---- files ----------------------------------------------------------
    def make_file(owner, folder_id, trashed):
        fid = next_id["files"]
        next_id["files"] += 1
        ftype = rng.choices(TYPES, weights=TYPE_WEIGHTS)[0]
        name = clean(rng.choice(SUBJECTS) + rng.choice(SUFFIXES)
                     + rng.choice(TYPE_EXT[ftype]))
        lo = folder_created.get(folder_id, "2024-03-01T00:00:00Z")
        created = ts_between(max(lo, "2024-03-01T00:00:00Z"), "2025-10-31T00:00:00Z")
        modified = ts_between(created, "2025-12-31T00:00:00Z")
        row = {
            "id": fid, "name": name, "path": f"/files/{fid}",
            "size_bytes": rng.randint(8_000, 80_000_000),
            "type": ftype, "mime_type": "",
            "owner_id": owner, "created_at": created, "modified_at": modified,
            "shared_with": "[]", "folder_id": folder_id,
            "starred": 0,               # NEVER starred (task invariant)
            "is_trashed": 1 if trashed else 0,
            "source_site": "", "source_id": "",
        }
        new["files"].append(row)
        return row

    active_new_files = []
    for _ in range(45):  # keeps drive view at 498 rows (<500, unpaginated)
        folder_id = rng.choice(new_folder_ids + OTHER_USER_FOLDERS)
        active_new_files.append(make_file(rng.choice(other_user_ids), folder_id, False))
    for _ in range(100):  # trash history — hidden from all default views
        folder_id = rng.choice(new_folder_ids + OTHER_USER_FOLDERS + [0, 0])
        owner = rng.choice(all_user_ids)  # trashed alex files are fine (never rendered in drive)
        make_file(owner, folder_id, True)

    # ---- shares ---------------------------------------------------------
    shares_per_file = {}
    for r in db.execute(f"SELECT file_id, COUNT(*) c FROM {T}_shares GROUP BY file_id"):
        shares_per_file[r["file_id"]] = r["c"]

    def add_share(file_id, shared_by, shared_with, created_at, permission=None, link=""):
        if shares_per_file.get(file_id, 0) >= MAX_SHARES_PER_FILE:
            return False
        if shared_with and (file_id, shared_with) in existing_share_pairs:
            return False
        sid = next_id["shares"]
        next_id["shares"] += 1
        new["shares"].append({
            "id": sid, "file_id": file_id, "shared_by": shared_by,
            "shared_with": shared_with,
            "permission": permission or rng.choice(["view", "view", "edit"]),
            "created_at": created_at, "link": link,
        })
        shares_per_file[file_id] = shares_per_file.get(file_id, 0) + 1
        if shared_with:
            existing_share_pairs.add((file_id, shared_with))
        return True

    # (a) backfill share rows implied by existing files' shared_with lists
    for f in existing_files:
        if f["is_trashed"]:
            continue
        try:
            listed = json.loads(f["shared_with"] or "[]")
        except (TypeError, ValueError):
            listed = []
        for uid in listed:
            if uid == f["owner_id"]:
                continue
            add_share(f["id"], f["owner_id"], uid,
                      ts_between(max(f["created_at"], "2024-01-01T00:00:00Z"),
                                 "2026-05-31T00:00:00Z"))

    # (b) shares on new active files (and sync their shared_with JSON)
    for f in active_new_files:
        if rng.random() < 0.7:
            targets = rng.sample([u for u in all_user_ids if u != f["owner_id"]],
                                 rng.randint(1, 3))
            granted = []
            for uid in targets:
                if add_share(f["id"], f["owner_id"], uid,
                             ts_between(f["created_at"], "2026-05-31T00:00:00Z")):
                    granted.append(uid)
            f["shared_with"] = json.dumps(sorted(granted))

    # (c) historic peer-to-peer grants on existing non-trashed files + link shares
    active_existing = [f for f in existing_files if not f["is_trashed"]]
    alnum = string.ascii_letters + string.digits
    attempts = 0
    while len(new["shares"]) < 940 and attempts < 20000:
        attempts += 1
        f = rng.choice(active_existing)
        created = ts_between(max(f["created_at"], "2024-01-01T00:00:00Z"),
                             "2026-05-31T00:00:00Z")
        if rng.random() < 0.12:  # public link share
            link = "https://meridiancloud.com/s/" + "".join(rng.choice(alnum) for _ in range(8))
            add_share(f["id"], f["owner_id"], 0, created, permission="view", link=link)
        else:
            uid = rng.choice([u for u in all_user_ids if u != f["owner_id"]])
            add_share(f["id"], f["owner_id"], uid, created)

    # ---- transfers ------------------------------------------------------
    transfers_per_file = {}
    for r in db.execute(f"SELECT file_id, COUNT(*) c FROM {T}_transfers GROUP BY file_id"):
        transfers_per_file[r["file_id"]] = r["c"]
    all_files = existing_files + new["files"]
    recipients = ([user_email[u] for u in all_user_ids] * 3
                  + TEAM_ALIASES * 4 + EXTERNAL_EMAILS * 3)
    for e in recipients:
        clean(e)

    target_transfers = 3360
    guard = 0
    while len(new["transfers"]) < target_transfers and guard < 200000:
        guard += 1
        f = rng.choice(all_files)
        if transfers_per_file.get(f["id"], 0) >= MAX_TRANSFERS_PER_FILE:
            continue
        created = ts_between(max(f["created_at"], "2024-01-01T00:00:00Z"),
                             "2026-05-31T00:00:00Z")
        expire_days = rng.choice([3, 7, 7, 7, 14, 30])
        status = rng.choices(["completed", "expired"], weights=[68, 32])[0]
        sender = f["owner_id"] if rng.random() < 0.75 else rng.choice(all_user_ids)
        tid = next_id["transfers"]
        next_id["transfers"] += 1
        new["transfers"].append({
            "id": tid, "file_id": f["id"], "sender_id": sender,
            "recipient_email": rng.choice(recipients),
            "status": status, "created_at": created,
            "expires_at": plus_days(created, expire_days),
            "download_count": rng.randint(1, 9) if status == "completed"
                              else rng.choice([0, 0, 0, 1]),
        })
        transfers_per_file[f["id"]] = transfers_per_file.get(f["id"], 0) + 1

    # ---- safety asserts -------------------------------------------------
    assert all(r["starred"] == 0 for r in new["files"])
    assert all(r["folder_id"] not in (1, 2, 3, 4, 5, 11, 19, 26) for r in new["files"]), \
        "no new files in alex-owned folders"
    assert all(r["is_trashed"] == 1 or r["owner_id"] != MAIN_USER for r in new["files"])
    assert all(r["status"] in ("completed", "expired") for r in new["transfers"])
    for r in new["files"]:
        clean(r["name"])
    for r in new["folders"]:
        clean(r["name"])
    active_total = (len([f for f in existing_files if not f["is_trashed"]])
                    + len(active_new_files))
    assert active_total < 500, active_total

    for t in new:
        print(f"{t}: +{len(new[t])}")
    print("total added:", sum(len(v) for v in new.values()))
    if dry:
        for t in new:
            for r in new[t][:2]:
                print(" ", json.dumps(r, default=str)[:170])
        return

    bdir = ROOT / "data" / "backups" / "cloud-storage-file-transfer-expansion-2026-07-20"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "inserted_ids.json").write_text(json.dumps(
        {t: [r["id"] for r in rows] for t, rows in new.items()}, indent=1))

    for t, rows in new.items():
        if not rows:
            continue
        cols = list(rows[0].keys())
        sql = (f"INSERT INTO {T}_{t} ({', '.join(cols)}) "
               f"VALUES ({', '.join('?' * len(cols))})")
        db.executemany(sql, [[r[c] for c in cols] for r in rows])
    # rebuild content-linked FTS indexes for every table we touched
    for t in ("files", "folders", "shares", "transfers"):
        db.execute(f"INSERT INTO fts_{T}_{t}(fts_{T}_{t}) VALUES('rebuild')")
    db.commit()
    print(f"inserted; rollback ids at {bdir}/inserted_ids.json")


if __name__ == "__main__":
    main()
