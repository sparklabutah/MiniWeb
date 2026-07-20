"""Second expansion for project-mgmt-issue-tracking (Meridian Tracker).

Round 1 (scripts/expand_project_mgmt_data.py) brought the site to 356 rows.
This round tops the site up to >=5000 total rows with deterministic (seeded)
synthetic data:

- 4 new projects in the existing Meridian portfolio style (MeridianConnect,
  MeridianPulse, MeridianGuard, MeridianDesk) with prefixes registered in
  sites/project-mgmt-issue-tracking/routes.py `_PROJECT_PREFIXES`.
- 31 historical/active sprints (biweekly windows preceding existing sprints).
- ~1360 issues, the bulk done/closed and attached to closed sprints so that
  every unpaginated page render stays small: backlog (sprint=0 and status not
  done/closed) stays well under 500 total, each project board < 250 issues,
  each sprint < 150 issues.
- ~3400 comments (1-5 per new issue; comments render per-issue only).

Task-safety: the saved annotation task filters the backlog by
project=MeridianLens(3) + type=feature + priority=critical, which matches 0
issues today. New backlog-eligible issues in project 3 are never critical, so
the filtered result stays identical. Dropdown option values are untouched
(type/priority options are hardcoded in the template; project options use ids,
so MeridianLens keeps value 3).

Insert-only; inserted ids recorded under
data/backups/project-mgmt-expansion2-2026-07-20/ for rollback.

Usage: python scripts/expand_project_mgmt_data2.py [--dry-run]
"""
import datetime
import json
import random
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "trimmed_miniweb.db"
rng = random.Random(2026_07_20)

TODAY = datetime.datetime(2026, 7, 20, 12, 0, 0)

# ---------------------------------------------------------------------------
# New projects (Meridian portfolio style, matching existing descriptions)
# ---------------------------------------------------------------------------

NEW_PROJECTS = [
    # (name, description, owner_id, created_at)  -- ids assigned at runtime
    ("MeridianConnect",
     "Integration hub connecting Meridian products to third-party systems: "
     "OAuth connectors, field mappings, webhook relays, and sync pipelines.",
     2, "2025-10-06T09:00:00"),
    ("MeridianPulse",
     "Uptime and incident monitoring: status pages, probes, on-call "
     "rotations, SLO reporting, and alert escalation policies.",
     7, "2025-12-01T10:00:00"),
    ("MeridianGuard",
     "Identity and access management: SSO, SCIM provisioning, MFA, session "
     "controls, and role-based access across the Meridian suite.",
     2, "2026-01-19T09:30:00"),
    ("MeridianDesk",
     "Customer support portal: ticket queues, SLA tracking, knowledge base, "
     "satisfaction surveys, and email-to-ticket automation.",
     12, "2026-02-09T11:00:00"),
]
# prefix per new project name (also added to routes.py _PROJECT_PREFIXES)
NEW_PREFIXES = {"MeridianConnect": "MC", "MeridianPulse": "MP",
                "MeridianGuard": "MG", "MeridianDesk": "MD"}

# ---------------------------------------------------------------------------
# Domain vocabulary per project (1-5 reused from round 1)
# ---------------------------------------------------------------------------

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
    # new projects keyed by name; remapped to ids at runtime
    "MeridianConnect": (
        ["OAuth connector", "Salesforce sync", "webhook relay", "rate limiter",
         "field mapping editor", "connection health check", "retry queue",
         "API gateway route", "credential vault", "event bus bridge"],
        ["oauth", "sync", "connectors", "gateway", "mappings", "reliability"]),
    "MeridianPulse": (
        ["uptime probe", "status page", "incident timeline", "on-call rotation",
         "latency heatmap", "maintenance window", "alert digest", "SLO report",
         "probe scheduler", "escalation policy"],
        ["uptime", "incidents", "oncall", "slo", "probes", "statuspage"]),
    "MeridianGuard": (
        ["SSO handshake", "SCIM provisioning", "MFA enrollment",
         "session revocation", "role matrix", "API token rotation",
         "password policy", "login audit trail", "device trust check",
         "recovery flow"],
        ["sso", "scim", "mfa", "sessions", "rbac", "audit"]),
    "MeridianDesk": (
        ["ticket queue", "canned response", "SLA badge", "customer portal login",
         "attachment scanner", "satisfaction survey", "agent workspace",
         "knowledge-base article editor", "macro runner",
         "email-to-ticket parser"],
        ["tickets", "sla", "portal", "kb", "surveys", "email"]),
}

BUG_TEMPLATES = [
    "{noun} fails when {cond}",
    "{noun} shows stale data after {cond}",
    "Crash in {noun} on {cond}",
    "{noun} times out when {cond}",
    "Incorrect permissions check in {noun}",
    "{noun} drops events under load",
    "Race condition in {noun} during concurrent edits",
    "{noun} returns 500 when {cond}",
    "Duplicate entries created by {noun} when {cond}",
    "{noun} ignores the configured timezone",
]
FEATURE_TEMPLATES = [
    "Add bulk actions to {noun}",
    "Support custom fields in {noun}",
    "Expose {noun} via public API",
    "Add keyboard shortcuts for {noun}",
    "Configurable retry policy for {noun}",
    "Dark mode support for {noun}",
    "Add CSV export to {noun}",
    "Allow scheduling {noun} runs",
    "Add role-based visibility to {noun}",
]
TASK_TEMPLATES = [
    "Migrate {noun} to the new schema",
    "Write integration tests for {noun}",
    "Document {noun} configuration",
    "Reduce memory footprint of {noun}",
    "Upgrade dependencies used by {noun}",
    "Instrument {noun} with tracing",
    "Clean up feature flags around {noun}",
    "Backfill missing metrics for {noun}",
]
STORY_TEMPLATES = [
    "As an admin I can configure {noun} per team",
    "As a user I can preview {noun} changes before saving",
    "As an auditor I can export {noun} history",
    "As a team lead I can subscribe to {noun} digests",
]
CONDS = ["the session expires mid-request", "the payload exceeds 1 MB",
         "two tabs are open", "the user has no team assigned",
         "the timezone is not UTC", "the name contains unicode",
         "the request is retried", "pagination goes past page 50",
         "the account has more than 100 members", "a proxy strips the headers",
         "the browser blocks third-party cookies", "the disk is nearly full"]

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
    "Retro note: we should add a regression test for {label}.",
    "Deployed behind a flag; enabling for internal users first.",
    "Customer confirmed the fix on their instance.",
    "Moving back to open — QA found an edge case with {label}.",
    "Estimation bumped to reflect the extra migration work.",
    "Paired with Priya on this; root cause was a stale cache entry.",
    "Docs updated alongside the code change.",
    "Verified on the release branch, good to go.",
]

SPRINT_GOALS = [
    "Stabilize {a} and burn down {b} bugs",
    "Ship the {a} improvements and start on {b}",
    "Harden {a}; reduce alert noise around {b}",
    "Deliver {a} MVP and clean up {b} debt",
    "Polish {a} and close out remaining {b} issues",
    "Focus on {a} reliability and {b} test coverage",
]

# per existing project: list of (name, start, end) for new CLOSED sprints
# (biweekly windows immediately preceding the earliest existing sprint)
EXISTING_NEW_SPRINTS = {
    1: [("MF Sprint 8", "2026-03-09", "2026-03-22"),
        ("MF Sprint 9", "2026-03-23", "2026-04-05"),
        ("MF Sprint 10", "2026-04-06", "2026-04-19"),
        ("MF Sprint 11", "2026-04-20", "2026-05-03"),
        ("MF Sprint 12", "2026-05-04", "2026-05-17"),
        ("MF Sprint 13", "2026-05-18", "2026-05-31")],
    2: [("MV Sprint 4", "2026-04-13", "2026-04-26"),
        ("MV Sprint 5", "2026-04-27", "2026-05-10"),
        ("MV Sprint 6", "2026-05-11", "2026-05-24"),
        ("MV Sprint 7", "2026-05-25", "2026-06-07")],
    3: [("ML Sprint 1", "2026-06-01", "2026-06-14")],
    # 4 (Internal Tools) ran kanban-style before IT Sprint 1 — no back sprints
    # 5 (Website Redesign) started at WR Sprint 1 — no back sprints
}

# new projects: 4 closed + 1 active sprint each, biweekly
NEW_PROJECT_SPRINT_WINDOWS = [
    ("Sprint 1", "2026-05-04", "2026-05-17", "closed"),
    ("Sprint 2", "2026-05-18", "2026-05-31", "closed"),
    ("Sprint 3", "2026-06-01", "2026-06-14", "closed"),
    ("Sprint 4", "2026-06-15", "2026-06-28", "closed"),
    ("Sprint 5", "2026-07-13", "2026-07-26", "active"),
]

# new issues per project (existing ids 1-5; new projects by name)
NEW_ISSUE_COUNTS = {1: 170, 2: 170, 3: 170, 4: 150, 5: 150,
                    "MeridianConnect": 145, "MeridianPulse": 140,
                    "MeridianGuard": 135, "MeridianDesk": 130}


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def parse_date(s):
    return datetime.datetime.strptime(s, "%Y-%m-%d")


def main():
    dry = "--dry-run" in sys.argv
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.row_factory = sqlite3.Row

    users = [r["id"] for r in db.execute(
        "SELECT id FROM project_mgmt_issue_tracking_users")]
    non_alex = [u for u in users if u != 1]
    next_project = db.execute(
        "SELECT MAX(id)+1 FROM project_mgmt_issue_tracking_projects").fetchone()[0]
    next_issue = db.execute(
        "SELECT MAX(id)+1 FROM project_mgmt_issue_tracking_issues").fetchone()[0]
    next_comment = db.execute(
        "SELECT MAX(id)+1 FROM project_mgmt_issue_tracking_comments").fetchone()[0]
    next_sprint = db.execute(
        "SELECT MAX(id)+1 FROM project_mgmt_issue_tracking_sprints").fetchone()[0]

    # ---- projects -----------------------------------------------------------
    projects_new = []
    name_to_pid = {}
    for name, desc, owner, created in NEW_PROJECTS:
        projects_new.append({"id": next_project, "name": name, "key_": "",
                             "description": desc, "owner_id": owner,
                             "status": "active", "created_at": created})
        name_to_pid[name] = next_project
        next_project += 1

    # ---- sprints ------------------------------------------------------------
    sprints_new = []

    def add_sprint(pid, name, start, end, status, nouns):
        nonlocal next_sprint
        a, b = rng.sample(nouns, 2)
        goal = rng.choice(SPRINT_GOALS).format(a=a, b=b)
        sprints_new.append({"id": next_sprint, "project_id": pid, "name": name,
                            "start_date": start, "end_date": end,
                            "status": status, "goal": goal})
        next_sprint += 1

    for pid, windows in EXISTING_NEW_SPRINTS.items():
        for name, start, end in windows:
            add_sprint(pid, name, start, end, "closed", DOMAINS[pid][0])
    for pname in NEW_PREFIXES:
        pid = name_to_pid[pname]
        prefix = NEW_PREFIXES[pname]
        for suffix, start, end, status in NEW_PROJECT_SPRINT_WINDOWS:
            add_sprint(pid, f"{prefix} {suffix}", start, end, status,
                       DOMAINS[pname][0])

    # sprint pools per project (existing + new), keyed by status
    sprint_pool = {}
    rows = [dict(r) for r in db.execute(
        "SELECT * FROM project_mgmt_issue_tracking_sprints")]
    for s in rows + sprints_new:
        sprint_pool.setdefault(s["project_id"], []).append(s)

    # ---- issues + comments --------------------------------------------------
    issues_new, comments_new = [], []
    for key, count in NEW_ISSUE_COUNTS.items():
        pid = key if isinstance(key, int) else name_to_pid[key]
        nouns, labels = DOMAINS[key]
        pool = sprint_pool.get(pid, [])
        closed_sprints = [s for s in pool if s["status"] == "closed"]
        active_sprints = [s for s in pool if s["status"] == "active"]
        for _ in range(count):
            itype = rng.choices(["bug", "feature", "task", "story"],
                                weights=[36, 27, 27, 10])[0]
            noun = rng.choice(nouns)
            title = rng.choice({"bug": BUG_TEMPLATES, "feature": FEATURE_TEMPLATES,
                                "task": TASK_TEMPLATES,
                                "story": STORY_TEMPLATES}[itype])
            title = title.format(noun=noun, cond=rng.choice(CONDS))
            title = title[0].upper() + title[1:]

            status = rng.choices(["done", "closed", "open", "in_progress", "review"],
                                 weights=[45, 33, 13, 6, 3])[0]

            # sprint + dates: bulk lives in closed sprints (bounded per page)
            sprint = 0
            if status in ("done", "closed"):
                if closed_sprints and rng.random() < 0.8:
                    sp = rng.choice(closed_sprints)
                    sprint = sp["id"]
                    start = parse_date(sp["start_date"])
                    end = parse_date(sp["end_date"])
                    created = start - datetime.timedelta(
                        days=rng.randint(1, 40), hours=rng.randint(0, 10))
                    updated = start + datetime.timedelta(
                        days=rng.randint(1, (end - start).days + 3),
                        hours=rng.randint(1, 9))
                else:
                    created = TODAY - datetime.timedelta(
                        days=rng.randint(20, 300), hours=rng.randint(0, 10))
                    updated = created + datetime.timedelta(
                        days=rng.randint(2, 30), hours=rng.randint(1, 9))
            elif status in ("in_progress", "review"):
                # always inside the active sprint (never backlog-eligible)
                if active_sprints:
                    sprint = active_sprints[0]["id"]
                created = TODAY - datetime.timedelta(
                    days=rng.randint(5, 45), hours=rng.randint(0, 10))
                updated = created + datetime.timedelta(
                    days=rng.randint(1, 10), hours=rng.randint(1, 9))
            else:  # open: 35% pulled into the active sprint, else backlog
                if active_sprints and rng.random() < 0.35:
                    sprint = active_sprints[0]["id"]
                created = TODAY - datetime.timedelta(
                    days=rng.randint(10, 280), hours=rng.randint(0, 10))
                updated = created + datetime.timedelta(
                    days=rng.randint(0, 15), hours=rng.randint(1, 9))
            updated = min(updated, TODAY - datetime.timedelta(days=2))
            if updated < created:
                updated = created

            priority = rng.choices(["critical", "high", "medium", "low"],
                                   weights=[7, 25, 43, 25])[0]
            # Task safety: the saved annotation filters the backlog by
            # MeridianLens + feature + critical (currently 0 matches).
            # Never add a critical backlog-eligible issue to project 3.
            if (pid == 3 and sprint == 0
                    and status not in ("done", "closed")
                    and priority == "critical"):
                priority = rng.choice(["high", "medium"])

            # keep the dashboard "My Issues" list (user 1, not done/closed) flat
            if status in ("done", "closed"):
                assignee = rng.choice(users)
            else:
                assignee = rng.choice(non_alex)

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
                "type": itype, "status": status, "priority": priority,
                "assignee_id": assignee,
                "reporter_id": rng.choice(users),
                "created_at": iso(created), "updated_at": iso(updated),
                "labels": json.dumps(rng.sample(labels, rng.randint(1, 2))),
                "story_points": rng.choice([1, 2, 3, 3, 5, 5, 8, 13]),
                "sprint": sprint,
            }
            next_issue += 1
            issues_new.append(issue)

            # comments carry the bulk of the volume; rendered per-issue only
            n_comments = rng.choices([1, 2, 3, 4, 5],
                                     weights=[18, 35, 28, 13, 6])[0]
            for _ in range(n_comments):
                cdate = created + datetime.timedelta(
                    days=rng.randint(0, 18), hours=rng.randint(1, 8))
                cdate = min(cdate, TODAY - datetime.timedelta(days=1))
                text = rng.choice(COMMENTS).format(label=rng.choice(labels))
                comments_new.append({"id": next_comment, "issue_id": issue["id"],
                                     "user_id": rng.choice(users), "text": text,
                                     "created_at": iso(cdate)})
                next_comment += 1

    total = (len(projects_new) + len(sprints_new) + len(issues_new)
             + len(comments_new))
    print(f"projects: +{len(projects_new)}, sprints: +{len(sprints_new)}, "
          f"issues: +{len(issues_new)}, comments: +{len(comments_new)} "
          f"(total +{total})")
    if dry:
        for i in issues_new[:6]:
            print(" ", i["project_id"], i["type"], i["status"], i["priority"],
                  "sprint", i["sprint"], "|", i["title"][:64])
        # sanity previews
        backlog_add = sum(1 for i in issues_new
                          if i["sprint"] == 0
                          and i["status"] not in ("done", "closed"))
        print("backlog-eligible added:", backlog_add)
        return

    bdir = ROOT / "data" / "backups" / "project-mgmt-expansion2-2026-07-20"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "inserted_ids.json").write_text(json.dumps({
        "projects": [p["id"] for p in projects_new],
        "sprints": [s["id"] for s in sprints_new],
        "issues": [i["id"] for i in issues_new],
        "comments": [c["id"] for c in comments_new]}, indent=1))

    for table, rows2 in (("projects", projects_new), ("sprints", sprints_new),
                         ("issues", issues_new), ("comments", comments_new)):
        if not rows2:
            continue
        cols = list(rows2[0].keys())
        db.executemany(
            f"INSERT INTO project_mgmt_issue_tracking_{table} ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' * len(cols))})",
            [[r[c] for c in cols] for r in rows2])

    # keep FTS indexes in sync (content-linked fts5 tables)
    for fts in ("fts_project_mgmt_issue_tracking_issues",
                "fts_project_mgmt_issue_tracking_comments"):
        db.execute(f"INSERT INTO {fts}({fts}) VALUES('rebuild')")
    db.commit()
    print(f"inserted; rollback ids at {bdir}/inserted_ids.json")


if __name__ == "__main__":
    main()
