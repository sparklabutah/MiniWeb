"""Expand remote-calls (CallHub) base data.

CallHub ships with 420 calls / 158 meetings / 37 recordings / 8 users (623
rows). Adds deterministic (seeded) synthetic historical meetings, recordings,
and calls between the existing 8 Meridian Systems users.

Sizing is capped by page-render constraints, NOT the 5000-row target:
every list page on this site is unpaginated (meetings and recordings render
the full global table; call-log renders the current user's full history), so
each rendered list must stay below ~500 rows. With a fixed 8-user roster
(adding users would change the meaning of the saved "invite everyone"
annotation task) the compliant ceiling is roughly:
  meetings <=~495 global, recordings <=~450 global,
  call_log <=~1960 total (~490 per user, 2 users per call).

Task-safety guarantees:
  * No new meeting title contains "standup" or "engineering" (the
    "most frequent host of the engineering standup" answer stays
    Priya Sharma / rc-u-002).
  * New meeting ids live at mtg-600+ so the runtime id formula
    (mtg-{len+1}) lands on the free mtg-496.. range after insertion.
    (Before this expansion it collided with existing mtg-159.)
  * No new meetings on 2026-07-06 or 2026-07-15; the few new scheduled
    meetings never include rc-u-001 (alex.rivera).
  * All bulk rows are dated OLDER than the existing minimum dates, so
    newest/most-recent extremums are unchanged.

Insert-only; inserted ids recorded under data/backups/ for rollback.

Usage: ~/.conda/envs/miniweb/bin/python scripts/expand_remote_calls_data.py [--dry-run]
"""
import datetime
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from random import Random

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "trimmed_miniweb.db"
BACKUP_DIR = ROOT / "data" / "backups" / "remote-calls-expansion-2026-07-20"

rng = Random(20260720)

USERS = ["rc-u-001", "rc-u-002", "rc-u-003", "rc-u-004",
         "rc-u-005", "rc-u-006", "rc-u-007", "rc-u-008"]
ALEX = "rc-u-001"

# Existing generic title vocabulary + a few on-brand additions.
# NEVER include "standup" or "engineering" (saved task) or task-created
# titles ("Shareholder updates", "Project Discussion").
WORK_TITLES = [
    "Partner Demo", "Quarterly Review", "Security Review", "Vendor Sync",
    "Roadmap Session", "Marketing Weekly", "Support Escalation",
    "Design Critique", "Data Review", "Bug Triage", "All Hands",
    "Budget Sync", "Customer Onboarding Call", "Hiring Debrief",
    "Release Go/No-Go", "Incident Postmortem", "API Design Review",
    "Sales Pipeline Review", "UX Research Readout", "Infra Cost Review",
    "Team Retro", "Demo Prep", "Compliance Training",
    "Client Kickoff - Lakeport Retail", "Cascadia Partners Sync",
    "Meridian Onboarding Session", "QA Sync", "Sprint Retrospective",
    "Analytics Deep Dive", "Migration Planning",
]
PERSONAL_TITLES = [
    "Family Call - Weekend Plans", "Catch-up with Jake", "Coffee Chat",
    "Family Call - Holiday Plans", "Book Club Call", "Trip Planning Call",
]
CALL_NOTES = [
    "Quick sync about the release checklist",
    "Follow-up on the vendor contract",
    "Walked through the onboarding doc",
    "Discussed the demo feedback",
    "Rescheduled the review to next week",
    "Checked in on the migration status",
    "Debrief after the client call",
    "Aligned on budget numbers",
]

# ---------------------------------------------------------------------------
# Generation targets (see module docstring for why these are the ceiling)
# ---------------------------------------------------------------------------
N_MEETINGS = 337            # 158 -> 495 (< ~500 global unpaginated page)
N_SCHEDULED = 5             # future, never involving alex
MEETING_ID_START = 600      # mtg-600.. ; keeps runtime mtg-{len+1} free
PER_USER_CALL_TARGET = 490  # call-log page rows per user (< ~500)
RECORD_PROB = 0.90          # share of new completed meetings recorded
TWO_PART_PROB = 0.80        # long (>=60 min) recordings split in two parts


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + "-07:00"


def rand_dt(start, end, hour_lo=8, hour_hi=18):
    days = (end - start).days
    d = start + datetime.timedelta(days=rng.randint(0, days))
    return d.replace(hour=rng.randint(hour_lo, hour_hi),
                     minute=rng.choice([0, 0, 15, 30, 30, 45]),
                     second=0)


def build_meetings_and_recordings(next_rec_num):
    meetings, recordings = [], []
    # completed bulk: strictly older than existing min meeting date 2025-05-23
    lo = datetime.datetime(2024, 5, 1)
    hi = datetime.datetime(2025, 5, 15)
    for i in range(N_MEETINGS - N_SCHEDULED):
        mid = f"mtg-{MEETING_ID_START + i}"
        mtype = rng.choices(["video", "audio", "work", "personal"],
                            weights=[55, 30, 11, 4])[0]
        title = rng.choice(PERSONAL_TITLES if mtype == "personal"
                           else WORK_TITLES)
        host = rng.choice(USERS)
        others = rng.sample([u for u in USERS if u != host],
                            rng.randint(1, 4))
        participants = [host] + others
        duration = rng.choices([15, 25, 30, 45, 60, 90],
                               weights=[18, 10, 22, 20, 18, 12])[0]
        date = rand_dt(lo, hi)
        recorded = mtype != "personal" and rng.random() < RECORD_PROB
        meetings.append({
            "id": mid, "title": title, "host_id": host,
            "participants": json.dumps(participants),
            "date": iso(date), "duration_minutes": duration,
            "type": mtype, "recording_available": 1 if recorded else 0,
            "status": "completed",
        })
        if recorded:
            parts = 2 if duration >= 60 and rng.random() < TWO_PART_PROB else 1
            for p in range(parts):
                rec_id = f"rec-{next_rec_num:03d}"
                next_rec_num += 1
                rdur = max(8, (duration // parts) - rng.randint(0, 4))
                rdate = date + datetime.timedelta(minutes=(duration // 2) * p)
                fmt = rng.choices(["mp4", "webm"], weights=[85, 15])[0]
                rtitle = title if parts == 1 else f"{title} - Part {p + 1}"
                recordings.append({
                    "id": rec_id, "meeting_id": mid, "title": rtitle,
                    "recorded_by": host, "date": iso(rdate),
                    "duration_minutes": rdur,
                    "file_size_mb": round(rdur * rng.uniform(2.0, 2.9), 1),
                    "format": fmt,
                    "download_url": f"https://callhub.io/recordings/{rec_id}.{fmt}",
                    "transcript_available": 1 if rng.random() < 0.6 else 0,
                    "access": rng.choices(["team", "private", "organization"],
                                          weights=[70, 25, 5])[0],
                    "views": rng.randint(0, 12),
                })

    # a few future scheduled meetings, never involving alex, never on
    # 2026-07-06 / 2026-07-15
    slo = datetime.datetime(2026, 7, 27)
    shi = datetime.datetime(2026, 8, 21)
    non_alex = [u for u in USERS if u != ALEX]
    for i in range(N_SCHEDULED):
        mid = f"mtg-{MEETING_ID_START + (N_MEETINGS - N_SCHEDULED) + i}"
        host = rng.choice(non_alex)
        others = rng.sample([u for u in non_alex if u != host],
                            rng.randint(1, 3))
        meetings.append({
            "id": mid, "title": rng.choice(WORK_TITLES), "host_id": host,
            "participants": json.dumps([host] + others),
            "date": iso(rand_dt(slo, shi, 9, 16)),
            "duration_minutes": rng.choice([30, 45, 60]),
            "type": rng.choice(["video", "audio"]),
            "recording_available": 0, "status": "scheduled",
        })
    return meetings, recordings


def build_calls(db, next_call_num):
    # per-user involvement quota so no user's call-log page exceeds ~490 rows
    existing = Counter()
    for caller, callee in db.execute(
            "SELECT caller_id, callee_id FROM remote_calls_call_log"):
        existing[caller] += 1
        existing[callee] += 1
    quota = {u: max(0, PER_USER_CALL_TARGET - existing[u]) for u in USERS}
    total = sum(quota.values())
    if total % 2:  # need an even number of participant slots
        quota[max(quota, key=quota.get)] -= 1

    # calls: strictly older than existing min call date 2025-08-30
    lo = datetime.datetime(2024, 6, 1)
    hi = datetime.datetime(2025, 8, 20)
    calls = []
    while sum(quota.values()) > 0:
        # always pair the two users with the most remaining quota
        # (guarantees no self-pair and exact quota exhaustion)
        a, b = sorted(quota, key=lambda u: (-quota[u], rng.random()))[:2]
        if quota[b] == 0:
            break
        quota[a] -= 1
        quota[b] -= 1
        caller, callee = (a, b) if rng.random() < 0.5 else (b, a)
        status = rng.choices(["completed", "missed", "declined"],
                             weights=[69, 21, 10])[0]
        calls.append({
            "id": f"rc-cl-{next_call_num:04d}",
            "caller_id": caller, "callee_id": callee,
            "type": rng.choices(["audio", "video"], weights=[54, 46])[0],
            "date": iso(rand_dt(lo, hi, 7, 21)),
            "duration_seconds": rng.randint(45, 3900)
                                if status == "completed" else 0,
            "status": status,
            "note": rng.choice(CALL_NOTES) if (status == "completed"
                                               and rng.random() < 0.05) else "",
        })
        next_call_num += 1
    return calls


def main():
    dry = "--dry-run" in sys.argv
    db = sqlite3.connect(DB_PATH, timeout=60)

    # -- pre-flight: id ranges must be free -------------------------------
    existing_meeting_ids = {r[0] for r in db.execute(
        "SELECT id FROM remote_calls_meetings")}
    new_meeting_ids = {f"mtg-{MEETING_ID_START + i}" for i in range(N_MEETINGS)}
    assert not (new_meeting_ids & existing_meeting_ids), "meeting id collision"
    # runtime creation uses mtg-{len(meetings)+1}: must stay collision-free
    runtime_next = len(existing_meeting_ids) + N_MEETINGS + 1
    for n in range(runtime_next, runtime_next + 50):
        assert f"mtg-{n:03d}" not in (existing_meeting_ids | new_meeting_ids), \
            f"runtime-created id mtg-{n:03d} would collide"

    next_rec = db.execute(
        "SELECT MAX(CAST(SUBSTR(id, 5) AS INT)) FROM remote_calls_recordings"
    ).fetchone()[0] + 1
    next_call = db.execute(
        "SELECT MAX(CAST(SUBSTR(id, 7) AS INT)) FROM remote_calls_call_log "
        "WHERE id LIKE 'rc-cl-%'").fetchone()[0] + 1

    meetings, recordings = build_meetings_and_recordings(next_rec)
    calls = build_calls(db, next_call)

    # -- task-safety guards ----------------------------------------------
    for m in meetings:
        t = m["title"].lower()
        assert "standup" not in t and "engineering" not in t, m
        assert not (m["date"].startswith("2026-07-06")
                    or m["date"].startswith("2026-07-15")), m
        if m["status"] == "scheduled":
            assert ALEX not in json.loads(m["participants"]), m

    print(f"meetings: +{len(meetings)} (scheduled {N_SCHEDULED}), "
          f"recordings: +{len(recordings)}, calls: +{len(calls)}")
    inv = Counter()
    for c in calls:
        inv[c["caller_id"]] += 1
        inv[c["callee_id"]] += 1
    print("new call involvement per user:", dict(sorted(inv.items())))

    if dry:
        for m in meetings[:4]:
            print("  M", m["id"], m["status"], m["date"], "|", m["title"])
        for r in recordings[:3]:
            print("  R", r["id"], r["meeting_id"], r["date"], "|", r["title"])
        for c in calls[:4]:
            print("  C", c["id"], c["caller_id"], "->", c["callee_id"],
                  c["status"], c["date"])
        return

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    (BACKUP_DIR / "inserted_ids.json").write_text(json.dumps({
        "meetings": [m["id"] for m in meetings],
        "recordings": [r["id"] for r in recordings],
        "call_log": [c["id"] for c in calls]}, indent=1))

    for table, rows in (("meetings", meetings), ("recordings", recordings),
                        ("call_log", calls)):
        cols = list(rows[0].keys())
        db.executemany(
            f"INSERT INTO remote_calls_{table} ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' * len(cols))})",
            [[r[c] for c in cols] for r in rows])

    # FTS sync (brief rule 9). These fts5 tables use content_rowid=id with
    # TEXT primary keys, so the index stays empty after rebuild and
    # app.db.search keeps using its LIKE fallback — rebuild is still issued
    # so the index is formally in sync with the content tables.
    for t in ("meetings", "recordings", "call_log"):
        db.execute(f"INSERT INTO fts_remote_calls_{t}(fts_remote_calls_{t}) "
                   f"VALUES('rebuild')")
    db.commit()
    print(f"inserted; rollback ids at {BACKUP_DIR}/inserted_ids.json")


if __name__ == "__main__":
    main()
