"""Expand project-mgmt-issue-tracking (Meridian Tracker) base data.

The tracker ships with 40 issues / 30 comments / 6 sprints, which leaves the
backlog, project boards, and sprint pages nearly empty. Adds deterministic
(seeded) synthetic issues, comments, and a few sprints per project, themed to
each project's real domain (MeridianFlow workflow automation, MeridianVault
storage, MeridianLens analytics, Internal Tools, Website Redesign).

Insert-only; inserted ids recorded under data/backups/ for rollback.

Usage: python scripts/expand_project_mgmt_data.py [--dry-run]
"""
import datetime
import json
import random
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "trimmed_miniweb.db"
rng = random.Random(7)

TODAY = datetime.datetime(2026, 7, 20, 12, 0, 0)

# project_id -> (domain nouns, label pool)
DOMAINS = {
    1: (["approval chain", "task router", "webhook dispatcher", "workflow editor",
         "SLA timer", "escalation rule", "form builder", "audit trail",
         "notification queue", "automation trigger"],
        ["approval-chain", "webhooks", "routing", "notifications", "sla", "editor"]),
    2: (["encryption layer", "version history", "share link", "audit log",
         "folder sync", "retention policy", "upload pipeline", "access control",
         "document preview", "search index"],
        ["encryption", "versioning", "sharing", "audit", "sync", "acl"]),
    3: (["metrics ingestion", "dashboard widget", "alert rule", "funnel report",
         "session replay", "retention chart", "query builder", "export job",
         "anomaly detector", "real-time stream"],
        ["ingestion", "dashboards", "alerts", "reports", "performance"]),
    4: (["CLI deploy command", "dev container", "release script", "lint config",
         "CI cache", "secrets loader", "migration helper", "log shipper"],
        ["cli", "ci", "devx", "tooling", "infra"]),
    5: (["pricing page", "blog CMS", "hero section", "contact form",
         "SEO metadata", "cookie banner", "case-study template", "nav menu"],
        ["design", "cms", "seo", "content", "responsive"]),
}

BUG_TEMPLATES = [
    "{noun} fails when {cond}",
    "{noun} shows stale data after {cond}",
    "Crash in {noun} on {cond}",
    "{noun} times out when {cond}",
    "Incorrect permissions check in {noun}",
    "{noun} drops events under load",
    "Race condition in {noun} during concurrent edits",
]
FEATURE_TEMPLATES = [
    "Add bulk actions to {noun}",
    "Support custom fields in {noun}",
    "Expose {noun} via public API",
    "Add keyboard shortcuts for {noun}",
    "Configurable retry policy for {noun}",
    "Dark mode support for {noun}",
]
TASK_TEMPLATES = [
    "Migrate {noun} to the new schema",
    "Write integration tests for {noun}",
    "Document {noun} configuration",
    "Reduce memory footprint of {noun}",
    "Upgrade dependencies used by {noun}",
    "Instrument {noun} with tracing",
]
STORY_TEMPLATES = [
    "As an admin I can configure {noun} per team",
    "As a user I can preview {noun} changes before saving",
    "As an auditor I can export {noun} history",
]
CONDS = ["the session expires mid-request", "the payload exceeds 1 MB",
         "two tabs are open", "the user has no team assigned",
         "the timezone is not UTC", "the name contains unicode",
         "the request is retried", "pagination goes past page 50"]

COMMENTS = [
    "Reproduced on staging — looks like it regressed in the last release.",
    "Picking this up in the current sprint.",
    "Blocked on the API change in {label}; will revisit once that lands.",
    "Added test coverage; PR is up for review.",
    "Can we get design input on this before implementation?",
    "Downgrading priority after triage — workaround exists.",
    "Confirmed fixed on main, closing after the next deploy.",
    "Splitting this into two follow-up tasks; scope was too big.",
    "Logs attached from the affected time window.",
    "This also affects the mobile layout, updating the description.",
]

NEW_SPRINTS = [
    # (project_id, name, start, end, status, goal)
    (3, "ML Sprint 2", "2026-06-15", "2026-06-28", "closed",
     "Stabilize metrics ingestion and ship the alerting MVP"),
    (4, "IT Sprint 1", "2026-07-06", "2026-07-19", "active",
     "Standardize CI caching and the release tooling"),
    (5, "WR Sprint 1", "2026-05-18", "2026-05-31", "closed",
     "Finish the responsive nav and pricing page refresh"),
]

TARGET_ISSUES = {1: 45, 2: 38, 3: 36, 4: 28, 5: 30}


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def main():
    dry = "--dry-run" in sys.argv
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row

    users = [r["id"] for r in db.execute("SELECT id FROM project_mgmt_issue_tracking_users")]
    have = dict(db.execute(
        "SELECT project_id, COUNT(*) FROM project_mgmt_issue_tracking_issues GROUP BY project_id"))
    next_issue = db.execute("SELECT MAX(id)+1 FROM project_mgmt_issue_tracking_issues").fetchone()[0]
    next_comment = db.execute("SELECT MAX(id)+1 FROM project_mgmt_issue_tracking_comments").fetchone()[0]
    next_sprint = db.execute("SELECT MAX(id)+1 FROM project_mgmt_issue_tracking_sprints").fetchone()[0]

    sprints_new = []
    for pid, name, start, end, status, goal in NEW_SPRINTS:
        sprints_new.append({"id": next_sprint, "project_id": pid, "name": name,
                            "start_date": start, "end_date": end,
                            "status": status, "goal": goal})
        next_sprint += 1

    # sprint pools per project: existing + new, keyed by status
    sprint_pool = {}
    rows = [dict(r) for r in db.execute("SELECT * FROM project_mgmt_issue_tracking_sprints")]
    for s in rows + sprints_new:
        sprint_pool.setdefault(s["project_id"], []).append(s)

    issues_new, comments_new = [], []
    for pid, (nouns, labels) in DOMAINS.items():
        for _ in range(TARGET_ISSUES[pid] - have.get(pid, 0)):
            itype = rng.choices(["bug", "feature", "task", "story"],
                                weights=[35, 28, 27, 10])[0]
            noun = rng.choice(nouns)
            title = rng.choice({"bug": BUG_TEMPLATES, "feature": FEATURE_TEMPLATES,
                                "task": TASK_TEMPLATES, "story": STORY_TEMPLATES}[itype])
            title = title.format(noun=noun, cond=rng.choice(CONDS))
            title = title[0].upper() + title[1:]
            status = rng.choices(["open", "in_progress", "review", "done", "closed"],
                                 weights=[38, 18, 10, 22, 12])[0]
            created = TODAY - datetime.timedelta(days=rng.randint(3, 320),
                                                 hours=rng.randint(0, 10))
            updated = created + datetime.timedelta(days=rng.randint(0, 25),
                                                   hours=rng.randint(1, 9))
            updated = min(updated, TODAY)
            # sprint: done/closed issues mostly from closed sprints,
            # in_progress/review from the active sprint, open mostly backlog
            sprint = 0
            pool = sprint_pool.get(pid, [])
            if pool:
                if status in ("done", "closed") and rng.random() < 0.6:
                    closed = [s for s in pool if s["status"] == "closed"]
                    if closed:
                        sprint = rng.choice(closed)["id"]
                elif status in ("in_progress", "review") and rng.random() < 0.75:
                    active = [s for s in pool if s["status"] == "active"]
                    if active:
                        sprint = active[0]["id"]
                elif status == "open" and rng.random() < 0.2:
                    active = [s for s in pool if s["status"] == "active"]
                    if active:
                        sprint = active[0]["id"]
            desc_extra = {
                "bug": "Steps to reproduce are in the linked report. Regression suspected.",
                "feature": "Requested by several customers; needs a short design note first.",
                "task": "Part of ongoing maintenance for this component.",
                "story": "Acceptance criteria to be refined during sprint planning.",
            }[itype]
            issue = {
                "id": next_issue, "project_id": pid, "key_": "",
                "title": title,
                "description": f"{title}. {desc_extra}",
                "type": itype, "status": status,
                "priority": rng.choices(["critical", "high", "medium", "low"],
                                        weights=[8, 25, 42, 25])[0],
                "assignee_id": rng.choice(users),
                "reporter_id": rng.choice(users),
                "created_at": iso(created), "updated_at": iso(updated),
                "labels": json.dumps(rng.sample(labels, rng.randint(1, 2))),
                "story_points": rng.choice([1, 2, 3, 3, 5, 5, 8, 13]),
                "sprint": sprint,
            }
            next_issue += 1
            issues_new.append(issue)

            for _ in range(rng.choices([0, 1, 2, 3], weights=[35, 35, 20, 10])[0]):
                cdate = created + datetime.timedelta(days=rng.randint(0, 20),
                                                     hours=rng.randint(1, 8))
                if cdate > TODAY:
                    continue
                text = rng.choice(COMMENTS).format(label=rng.choice(labels))
                comments_new.append({"id": next_comment, "issue_id": issue["id"],
                                     "user_id": rng.choice(users), "text": text,
                                     "created_at": iso(cdate)})
                next_comment += 1

    print(f"sprints: +{len(sprints_new)}, issues: +{len(issues_new)}, comments: +{len(comments_new)}")
    if dry:
        for i in issues_new[:5]:
            print(" ", i["project_id"], i["type"], i["status"], "|", i["title"][:70])
        return

    bdir = ROOT / "data" / "backups" / "project-mgmt-expansion-2026-07-20"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "inserted_ids.json").write_text(json.dumps({
        "sprints": [s["id"] for s in sprints_new],
        "issues": [i["id"] for i in issues_new],
        "comments": [c["id"] for c in comments_new]}, indent=1))

    for table, rows2 in (("sprints", sprints_new), ("issues", issues_new),
                         ("comments", comments_new)):
        if not rows2:
            continue
        cols = list(rows2[0].keys())
        db.executemany(
            f"INSERT INTO project_mgmt_issue_tracking_{table} ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' * len(cols))})",
            [[r[c] for c in cols] for r in rows2])
    db.commit()
    print(f"inserted; rollback ids at {bdir}/inserted_ids.json")


if __name__ == "__main__":
    main()
