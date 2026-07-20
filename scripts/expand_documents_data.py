"""Expand documents (DocEdit) base data.

The DocEdit site ships with 18 documents / 40 revisions / 6 folders / 5 users,
which leaves the document list and revision histories nearly empty. Adds
deterministic (seeded) synthetic documents with long revision histories plus a
few archive folders, all themed to Meridian Systems (MeridianFlow /
MeridianLens / MeridianVault) like the existing corpus.

Task-safety constraints honored:
- NO new users: "Marcus Chen" stays unique and the share dialog (which lists
  all users) stays a 5-entry dropdown.
- Every new document is dated strictly BEFORE 2025-03-10 (the oldest existing
  created_at / updated_at), so the current 18 docs stay on top of the index
  under both the default "updated" sort and the "created" sort.
- Index renders all non-trashed docs unpaginated -> total kept under ~500.
- Bulk volume goes into revisions, which the UI only renders per-document
  (max ~48 per doc here).

Insert-only; inserted ids recorded under data/backups/ for rollback.

Usage: ~/.conda/envs/miniweb/bin/python scripts/expand_documents_data.py [--dry-run]
"""
import datetime
import json
import random
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "trimmed_miniweb.db"
rng = random.Random(20260720)

# All new docs live in this window, safely before the oldest existing
# doc date (2025-03-10T09:00:00Z created_at / 2025-10-15 updated_at).
DOC_EPOCH_START = datetime.datetime(2023, 11, 6, 8, 0, 0)
DOC_EPOCH_END = datetime.datetime(2025, 2, 21, 18, 0, 0)  # updated_at cap

USERS = [1, 2, 3, 4, 5]  # alex, priya, marcus, jessica, david
# Alex (1) owns comparatively few of the bulk docs; the rest spread out.
OWNER_WEIGHTS = [12, 24, 22, 21, 21]

NEW_FOLDERS = [
    # (name, owner_id, color, created_at)
    ("Archive 2024", 1, "#7F8C8D", "2024-01-08T09:00:00Z"),
    ("Design", 4, "#9B59B6", "2024-02-12T10:30:00Z"),
    ("Hiring", 2, "#16A085", "2024-03-04T11:15:00Z"),
    ("Security", 5, "#C0392B", "2024-03-27T09:45:00Z"),
    ("Customer Research", 4, "#2980B9", "2024-04-15T14:00:00Z"),
    ("Data & Analytics", 3, "#D35400", "2024-05-09T08:30:00Z"),
    ("Compliance", 2, "#2C3E50", "2024-06-18T13:20:00Z"),
    ("Marketing", 4, "#F39C12", "2024-07-30T10:00:00Z"),
]

PRODUCTS = ["MeridianFlow", "MeridianLens", "MeridianVault"]
SQUADS = ["Platform Squad", "Analytics Squad", "Storage Squad", "Growth Squad",
          "Infra Squad", "API Squad"]
COMPONENTS = ["webhook dispatcher", "ingestion pipeline", "OAuth service",
              "billing engine", "notification queue", "search index",
              "export scheduler", "dashboard renderer", "audit log",
              "retention worker", "sync agent", "rate limiter",
              "workflow editor", "alerting rules engine", "session store"]
CUSTOMERS = ["Lakeport Credit Union", "Cascadia Outfitters", "Northgate Labs",
             "Harborview Health", "Bluepine Logistics", "Summit & Co",
             "Ironwood Manufacturing", "Clearwater Analytics Group"]
MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July",
               "August", "September", "October", "November", "December"]
QUARTERS = ["Q4 2023", "Q1 2024", "Q2 2024", "Q3 2024", "Q4 2024"]

USER_NAMES = {1: "Alex Rivera", 2: "Priya Sharma", 3: "Marcus Chen",
              4: "Jessica Okafor", 5: "David Petrov"}


def para(sentences):
    return " ".join(sentences)


def make_doc_body(kind, ctx):
    """Return (title, content) for a document of the given kind."""
    p = ctx["product"]
    comp = ctx["component"]
    squad = ctx["squad"]
    cust = ctx["customer"]
    month = ctx["month"]
    year = ctx["year"]
    quarter = ctx["quarter"]
    author = ctx["author"]
    n = ctx["n"]

    if kind == "meeting":
        title = f"{squad} Sync Notes - {month} {ctx['day']}, {year}"
        content = (
            f"{title}\n\nAttendees: " + ", ".join(ctx["attendees"]) + f"\nFacilitator: {author}\n\n"
            f"Agenda:\n1. {p} {comp} status\n2. Open incidents review\n3. {quarter} planning follow-ups\n\n"
            "Discussion:\n"
            f"- {comp.capitalize()} rollout is at {rng.randint(20, 95)}% of tenants; no regressions reported this week.\n"
            f"- {rng.choice(CUSTOMERS)} asked about SSO group mapping; Priya to draft a support doc.\n"
            f"- Error budget for the {comp} is at {rng.randint(40, 98)}%; we agreed to hold off on risky deploys until next week.\n"
            f"- Reviewed the {quarter} OKR draft; the {squad.lower()} owns two key results this cycle.\n\n"
            "Action Items:\n"
            f"[ ] {rng.choice(list(USER_NAMES.values()))}: file follow-up tickets for the {comp} alerts\n"
            f"[ ] {rng.choice(list(USER_NAMES.values()))}: update the runbook section on rollbacks\n"
            f"[ ] {author}: circulate notes to the wider team"
        )
    elif kind == "prd":
        title = f"PRD: {p} {comp.title()} Improvements"
        content = (
            f"{title}\n\nAuthor: {author}\nStatus: {rng.choice(['Draft', 'In Review', 'Approved', 'Archived'])}\n"
            f"Target release: {quarter}\n\n"
            "1. Background\n"
            f"Customers on {p} report friction with the current {comp}. Support volume attributed to it grew "
            f"{rng.randint(8, 40)}% quarter over quarter, and {cust} escalated twice in {month}.\n\n"
            "2. Goals\n"
            f"- Reduce {comp} related support tickets by {rng.randint(20, 60)}%\n"
            f"- P95 latency under {rng.choice([150, 200, 250, 300])}ms\n"
            "- No net-new configuration required for existing tenants\n\n"
            "3. Requirements\n"
            f"3.1 The {comp} must expose per-tenant usage metrics.\n"
            "3.2 Admins can configure thresholds from the settings page.\n"
            "3.3 Changes are audit-logged with actor and timestamp.\n\n"
            "4. Out of Scope\n"
            f"- Rewriting the {rng.choice(COMPONENTS)}\n- Mobile-specific UI work\n\n"
            "5. Open Questions\n"
            f"- Do we gate this behind a feature flag for the first {rng.randint(2, 6)} weeks?\n"
            "- Does pricing need to reflect the higher quota tiers?"
        )
    elif kind == "retro":
        title = f"Sprint {n} Retro Notes - {squad}"
        content = (
            f"{title}\n\nDate: {year}-{ctx['month_num']:02d}-{ctx['day']:02d}\nScribe: {author}\n\n"
            "What went well:\n"
            f"- Shipped the {comp} changes two days early\n"
            "- Pairing rotation kept review latency low\n"
            f"- On-call was quiet: {rng.randint(0, 3)} pages all sprint\n\n"
            "What didn't go well:\n"
            f"- Flaky integration tests around the {rng.choice(COMPONENTS)} cost us roughly a day\n"
            "- Two stories were underestimated and carried over\n\n"
            "Experiments for next sprint:\n"
            f"- Timebox spikes to {rng.choice([1, 2])} day(s)\n"
            "- Add a mid-sprint scope check on Wednesday\n\n"
            f"Velocity: {rng.randint(18, 42)} points completed of {rng.randint(42, 55)} planned."
        )
    elif kind == "onepager":
        title = f"{p} {quarter} {rng.choice(['Planning One-Pager', 'Capacity Plan', 'OKR Draft'])}"
        content = (
            f"{title}\n\nOwner: {author}\nTeam: {squad}\n\n"
            "Summary\n"
            f"This one-pager proposes the {squad.lower()} focus for {quarter}: hardening the {comp} and "
            f"closing the top adoption gaps reported by {cust} and two other design partners.\n\n"
            "Key Results\n"
            f"1. {comp.capitalize()} error rate below {rng.choice([0.1, 0.5, 1.0])}%\n"
            f"2. Migration of {rng.randint(40, 95)}% of tenants to the new configuration format\n"
            f"3. Onboarding time cut from {rng.randint(5, 9)} days to {rng.randint(1, 4)} days\n\n"
            "Risks\n"
            f"- Dependency on the {rng.choice(COMPONENTS)} refactor landing in time\n"
            "- Holiday freeze shortens the usable sprint window\n\n"
            "Asks\n"
            f"- One additional reviewer from the {rng.choice(SQUADS)}\n"
            "- Budget sign-off for the load-testing environment"
        )
    elif kind == "interview":
        title = f"Interview Debrief - {rng.choice(['Senior', 'Staff', 'Mid-level'])} {rng.choice(['Backend', 'Frontend', 'Platform', 'Data'])} Engineer ({month} {year})"
        content = (
            f"{title}\n\nPanel: " + ", ".join(ctx["attendees"]) + f"\nHiring manager: {author}\n\n"
            f"Round summary\nCandidate {rng.choice(['A', 'B', 'C', 'D'])}-{rng.randint(100, 999)} completed the "
            "system design and coding rounds.\n\n"
            "Signals\n"
            f"- Strong on distributed systems fundamentals; walked through a {comp} design confidently\n"
            "- Communication clear, asked good clarifying questions\n"
            f"- Coding round: {rng.choice(['all', 'most', 'two of three'])} test cases passing within time\n\n"
            "Concerns\n"
            f"- Limited exposure to {rng.choice(['Kubernetes', 'Terraform', 'streaming systems', 'frontend testing'])}\n\n"
            f"Recommendation: {rng.choice(['Hire', 'Strong hire', 'No hire', 'Hold for another round'])}. "
            "Debrief scheduled with the panel this Friday."
        )
    elif kind == "research":
        title = f"Customer Research: {cust} ({month} {year})"
        content = (
            f"{title}\n\nResearcher: {author}\nFormat: {rng.choice(['45-min remote interview', 'on-site visit', 'usability session'])}\n\n"
            "Context\n"
            f"{cust} has used {p} for {rng.randint(1, 5)} years across {rng.randint(2, 12)} teams. "
            f"We spoke with their {rng.choice(['ops lead', 'engineering manager', 'IT director', 'data analyst'])} "
            f"about the {comp}.\n\n"
            "Top findings\n"
            f"1. The {comp} settings page is hard to discover; two participants searched the docs first.\n"
            f"2. Exported reports are re-imported into spreadsheets - an API would remove a weekly manual step.\n"
            f"3. Permissions confusion: viewers expected comment access by default.\n\n"
            "Quotes\n"
            f"\"We built a cron job just to work around the {comp} limits.\"\n"
            "\"Onboarding a new teammate still takes most of a morning.\"\n\n"
            "Recommended follow-ups\n"
            f"- Ship the {comp} quick-start checklist\n"
            "- Add an in-product link to the permission matrix"
        )
    elif kind == "postmortem":
        title = f"Incident Review: {p} {comp} degradation ({year}-{ctx['month_num']:02d}-{ctx['day']:02d})"
        content = (
            f"{title}\n\nSeverity: SEV-{rng.randint(2, 4)}\nDuration: {rng.randint(12, 190)} minutes\n"
            f"Author: {author}\nStatus: {rng.choice(['Reviewed', 'Draft', 'Actions in progress'])}\n\n"
            "Impact\n"
            f"Roughly {rng.randint(2, 35)}% of {p} tenants saw elevated latency or errors from the {comp}. "
            f"{rng.choice(CUSTOMERS)} raised a support ticket during the window.\n\n"
            "Timeline (UTC)\n"
            f"{rng.randint(8, 11)}:{rng.randint(10, 59)} - Alert fired: {comp} error rate above threshold\n"
            f"{rng.randint(11, 13)}:{rng.randint(10, 59)} - Rollback initiated after correlating with the morning deploy\n"
            f"{rng.randint(13, 15)}:{rng.randint(10, 59)} - Metrics recovered; incident closed\n\n"
            "Root cause\n"
            f"A configuration change assumed the {rng.choice(COMPONENTS)} was already migrated; the fallback path "
            "held a lock during retries, exhausting the worker pool.\n\n"
            "Action items\n"
            f"[ ] Add a canary check for {comp} saturation\n"
            "[ ] Make the fallback path lock-free\n"
            "[ ] Document the rollback in the deployment runbook"
        )
    else:  # memo / misc
        title = f"{rng.choice(['Memo', 'Proposal', 'Decision Log', 'FAQ', 'Checklist'])}: {p} {comp.title()}"
        content = (
            f"{title}\n\nAuthor: {author}\nLast updated: {year}-{ctx['month_num']:02d}-{ctx['day']:02d}\n\n"
            f"Purpose\nShared reference for how the {squad.lower()} handles the {p} {comp}: ownership, "
            "escalation, and routine maintenance.\n\n"
            "Key points\n"
            f"- Ownership: {rng.choice(list(USER_NAMES.values()))} is the directly responsible individual.\n"
            f"- Escalation: page the on-call if the {comp} backlog exceeds {rng.randint(500, 5000):,} items.\n"
            f"- Maintenance window: {rng.choice(['Tuesdays', 'Wednesdays', 'Thursdays'])} {rng.randint(6, 9)}:00 UTC.\n"
            f"- Related dashboards live in the {rng.choice(['DevOps', 'Analytics'])} folder.\n\n"
            "Notes\n"
            f"The previous approach relied on the legacy {rng.choice(COMPONENTS)} and was retired in {month} {year}. "
            "Historical context is preserved in the revision history of this document."
        )
    return title, content


KINDS = ["meeting", "prd", "retro", "onepager", "interview", "research",
         "postmortem", "memo"]
KIND_WEIGHTS = [24, 13, 14, 10, 8, 9, 8, 14]

REV_SUMMARIES = [
    "Fixed typos and tightened wording in the {section} section",
    "Added {name}'s feedback from the review thread",
    "Updated the {section} section with current numbers",
    "Reworked the {section} section for clarity",
    "Added action items from the follow-up discussion",
    "Marked completed action items as done",
    "Clarified ownership and escalation path",
    "Added links to related dashboards and tickets",
    "Removed outdated references to the legacy pipeline",
    "Incorporated comments from {name}",
    "Expanded the timeline with additional detail",
    "Adjusted formatting and heading levels",
    "Updated status after the {quarter} checkpoint",
    "Appended notes from the weekly sync",
    "Corrected metrics after re-running the numbers",
    "Restored a paragraph removed by mistake",
    "Added open questions raised during review",
    "Trimmed the summary to one page",
]
SECTIONS = ["summary", "goals", "risks", "timeline", "requirements",
            "action items", "background", "findings"]


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def rand_dt(rng_, start, end):
    span = int((end - start).total_seconds())
    return start + datetime.timedelta(seconds=rng_.randint(0, span))


def main():
    dry = "--dry-run" in sys.argv
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.row_factory = sqlite3.Row

    next_doc = db.execute("SELECT MAX(id)+1 FROM documents_documents").fetchone()[0]
    next_rev = db.execute("SELECT MAX(id)+1 FROM documents_revisions").fetchone()[0]
    next_folder = db.execute("SELECT MAX(id)+1 FROM documents_folders").fetchone()[0]
    oldest_existing = db.execute(
        "SELECT MIN(created_at), MIN(updated_at) FROM documents_documents").fetchone()
    assert DOC_EPOCH_END.strftime("%Y-%m-%dT%H:%M:%SZ") < min(oldest_existing), \
        "new-doc window must end before the oldest existing document"

    existing_folder_ids = [r["id"] for r in db.execute("SELECT id FROM documents_folders")]

    folders_new = []
    for name, owner, color, created in NEW_FOLDERS:
        folders_new.append({"id": next_folder, "name": name, "owner_id": owner,
                            "color": color, "created_at": created})
        next_folder += 1
    all_folder_ids = existing_folder_ids + [f["id"] for f in folders_new]

    docs_new, revs_new = [], []
    n_docs = 430
    # revision-count profile: most docs modest, a tail of long histories
    for i in range(n_docs):
        owner = rng.choices(USERS, weights=OWNER_WEIGHTS)[0]
        kind = rng.choices(KINDS, weights=KIND_WEIGHTS)[0]
        created = rand_dt(rng, DOC_EPOCH_START,
                          DOC_EPOCH_END - datetime.timedelta(days=30))
        author = USER_NAMES[owner]
        attendees = rng.sample(list(USER_NAMES.values()), rng.randint(2, 4))
        if author not in attendees:
            attendees[0] = author
        ctx = {
            "product": rng.choice(PRODUCTS),
            "component": rng.choice(COMPONENTS),
            "squad": rng.choice(SQUADS),
            "customer": rng.choice(CUSTOMERS),
            "month": MONTH_NAMES[created.month - 1],
            "month_num": created.month,
            "day": created.day,
            "year": created.year,
            "quarter": rng.choice(QUARTERS),
            "author": author,
            "attendees": attendees,
            "n": rng.randint(1, 23),
        }
        title, content = make_doc_body(kind, ctx)

        # collaborators (JSON string, like existing rows)
        others = [u for u in USERS if u != owner]
        n_collab = rng.choices([0, 1, 2, 3], weights=[38, 30, 22, 10])[0]
        collabs = [{"user_id": u, "permission": rng.choices(
                        ["view", "comment", "edit"], weights=[30, 25, 45])[0]}
                   for u in rng.sample(others, n_collab)]

        # revision history: mostly modest, some long-lived docs
        profile = rng.choices(["short", "medium", "long"], weights=[68, 24, 8])[0]
        n_revs = {"short": rng.randint(4, 12),
                  "medium": rng.randint(13, 25),
                  "long": rng.randint(26, 48)}[profile]
        # long histories imply a long life; keep updated_at in-window
        life_days = min(rng.randint(n_revs, n_revs * 12),
                        (DOC_EPOCH_END - created).days)
        updated = min(created + datetime.timedelta(days=max(life_days, 1),
                                                   hours=rng.randint(0, 9)),
                      DOC_EPOCH_END)

        trashed = 1 if rng.random() < 0.022 else 0
        starred = 0 if trashed else (1 if rng.random() < 0.03 else 0)
        folder_id = rng.choice(all_folder_ids) if rng.random() < 0.86 else 0

        doc = {
            "id": next_doc,
            "title": title,
            "content": content,
            "owner_id": owner,
            "folder_id": folder_id,
            "collaborators": json.dumps(collabs),
            "word_count": len(content.split()),
            "is_starred": starred,
            "is_trashed": trashed,
            "created_at": iso(created),
            "updated_at": iso(updated),
        }
        next_doc += 1
        docs_new.append(doc)

        # revisions: creation first, then edits spread across the doc's life,
        # last one exactly at updated_at
        editors = [owner] + [c["user_id"] for c in collabs
                             if c["permission"] == "edit"]
        times = sorted(rand_dt(rng, created + datetime.timedelta(hours=1),
                               updated - datetime.timedelta(minutes=5))
                       for _ in range(n_revs - 2))
        times = [created] + times + [updated]
        for j, ts in enumerate(times):
            if j == 0:
                summary = f"Created document: {title[:60]}"
                who = owner
            else:
                who = rng.choice(editors)
                summary = rng.choice(REV_SUMMARIES).format(
                    section=rng.choice(SECTIONS),
                    name=rng.choice([n for u, n in USER_NAMES.items() if u != who]),
                    quarter=ctx["quarter"])
            revs_new.append({"id": next_rev, "document_id": doc["id"],
                             "user_id": who, "timestamp": iso(ts),
                             "summary": summary})
            next_rev += 1

    print(f"folders: +{len(folders_new)}, documents: +{len(docs_new)}, "
          f"revisions: +{len(revs_new)}")
    trashed_n = sum(d["is_trashed"] for d in docs_new)
    starred_n = sum(d["is_starred"] for d in docs_new)
    print(f"  (new docs: {trashed_n} trashed, {starred_n} starred, "
          f"max updated_at {max(d['updated_at'] for d in docs_new)})")
    if dry:
        for d in docs_new[:6]:
            print("  doc", d["id"], d["owner_id"], d["created_at"][:10],
                  "|", d["title"][:70])
        for r in revs_new[:4]:
            print("  rev", r["id"], r["document_id"], r["timestamp"][:10],
                  "|", r["summary"][:70])
        return

    bdir = ROOT / "data" / "backups" / "documents-expansion-2026-07-20"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "inserted_ids.json").write_text(json.dumps({
        "folders": [f["id"] for f in folders_new],
        "documents": [d["id"] for d in docs_new],
        "revisions": [r["id"] for r in revs_new]}, indent=1))

    for table, rows in (("folders", folders_new), ("documents", docs_new),
                        ("revisions", revs_new)):
        if not rows:
            continue
        cols = list(rows[0].keys())
        db.executemany(
            f"INSERT INTO documents_{table} ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' * len(cols))})",
            [[r[c] for c in cols] for r in rows])
    # keep external-content FTS indexes in sync
    db.execute("INSERT INTO fts_documents_documents(fts_documents_documents) "
               "VALUES('rebuild')")
    db.execute("INSERT INTO fts_documents_revisions(fts_documents_revisions) "
               "VALUES('rebuild')")
    db.commit()
    print(f"inserted; rollback ids at {bdir}/inserted_ids.json")


if __name__ == "__main__":
    main()
