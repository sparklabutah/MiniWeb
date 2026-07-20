"""Expand project-homepages base data (FlowNet resources + team roster).

The FlowNet project homepage ships with 11 rows total (8 resources, 2 users,
1 project row). A single-paper research homepage cannot realistically carry
thousands of rows, so this scales it to its plausible ceiling (~60 rows):
a full artifact library (tutorial videos, talk recordings, versioned datasets,
preprints, release notes, supplementary packs) and a fuller team roster of
Meridian Systems contributors.

Task-safety constraints honored (data/annotations/Minh/project-homepages_09e45e,
search "code" in the search box -> expected answer "Apache-2.0"):
  * The project row (which holds sections.code_link.license = "Apache-2.0")
    is NOT touched, and none of the 8 existing resources are modified.
  * No new resource or user contains the substring "code" (also guarding
    "encode(r)"/"decode") in any searched field, so the recorded search for
    "code" returns exactly the same result set as before.
  * No new row mentions a software license name (MIT/GPL/BSD/Apache/CC-BY) or
    the word "license"; the license column of every new resource is '' —
    Apache-2.0 remains the only license the site surfaces for the paper.
Insert-only; existing rows are never updated or deleted.

Inserted ids are recorded in
data/backups/project-homepages-expansion-2026-07-20/inserted_ids.json.

Usage: python scripts/expand_project_homepages_data.py [--dry-run]
"""
import json
import random
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "trimmed_miniweb.db"
BACKUP_DIR = ROOT / "data" / "backups" / "project-homepages-expansion-2026-07-20"

rng = random.Random(2025)

BASE = "https://flownet.meridiansystems.com"
BLOG = "https://engineering.meridiansystems.com/blog"

# (type, title, url, format, size_mb, description, date_added, duration_minutes)
RESOURCES = [
    # ---- tutorial video series -----------------------------------------
    ("video", "FlowNet Tutorial Part 1: Installation and First Run",
     f"{BASE}/video/tutorial-01-install.mp4", "video/mp4", 96.0,
     "Step-by-step walkthrough of installing FlowNet and running the demo workflow on a laptop.",
     "2025-09-04", 14),
    ("video", "FlowNet Tutorial Part 2: Modeling Your Workflow Graph",
     f"{BASE}/video/tutorial-02-graph.mp4", "video/mp4", 121.0,
     "How to describe queues, processing nodes, and task metadata so FlowNet can learn a routing policy.",
     "2025-09-11", 19),
    ("video", "FlowNet Tutorial Part 3: Training a Routing Policy",
     f"{BASE}/video/tutorial-03-training.mp4", "video/mp4", 143.0,
     "Configuring the PPO training loop, choosing reward weights, and reading the training curves.",
     "2025-09-18", 22),
    ("video", "FlowNet Tutorial Part 4: Evaluation and Baselines",
     f"{BASE}/video/tutorial-04-evaluation.mp4", "video/mp4", 117.0,
     "Reproducing the benchmark numbers from the paper and comparing against heuristic routers.",
     "2025-09-25", 18),
    ("video", "FlowNet Tutorial Part 5: Deploying Behind a Shadow Router",
     f"{BASE}/video/tutorial-05-deployment.mp4", "video/mp4", 132.0,
     "Safely rolling a learned policy into production with shadow routing and automatic fallback.",
     "2025-10-02", 21),
    # ---- talk recordings -----------------------------------------------
    ("video", "Meridian Systems Tech Talk: FlowNet in Production",
     f"{BASE}/video/meridian-tech-talk-2025.mp4", "video/mp4", 240.0,
     "Internal tech talk on the first six months of FlowNet routing live MeridianFlow traffic.",
     "2025-10-16", 38),
    ("video", "Cascadia Systems Seminar: Adaptive Task Routing",
     f"{BASE}/video/cascadia-seminar-2025.mp4", "video/mp4", 301.0,
     "Invited seminar recording covering the motivation, method, and open questions.",
     "2025-11-06", 52),
    ("video", "Lakeport ML Meetup: Lessons from Deploying RL",
     f"{BASE}/video/lakeport-meetup-2026.mp4", "video/mp4", 188.0,
     "Community meetup talk by Aisha Patel on practical pitfalls of reinforcement learning in enterprise systems.",
     "2026-01-22", 31),
    ("video", "Guest Lecture: Reinforcement Learning for Systems Problems",
     f"{BASE}/video/guest-lecture-2026.mp4", "video/mp4", 412.0,
     "Recorded university guest lecture by Alex Rivera using FlowNet as the running example.",
     "2026-03-05", 74),
    # ---- slides ---------------------------------------------------------
    ("slides", "FlowNet Tutorial Slide Deck (Parts 1-5)",
     f"{BASE}/slides/flownet-tutorial-slides.pdf", "application/pdf", 18.4,
     "Combined slide deck accompanying the five-part tutorial video series.",
     "2025-10-02", 0),
    ("slides", "Meridian Tech Talk Slides: FlowNet in Production",
     f"{BASE}/slides/meridian-tech-talk-2025.pdf", "application/pdf", 9.7,
     "Slides from the internal production-deployment tech talk, including rollout dashboards.",
     "2025-10-16", 0),
    ("slides", "Cascadia Systems Seminar Slides",
     f"{BASE}/slides/cascadia-seminar-2025.pdf", "application/pdf", 11.2,
     "Slides from the invited Cascadia Systems Seminar on adaptive task routing.",
     "2025-11-06", 0),
    ("slides", "Journal Club Discussion Deck",
     f"{BASE}/slides/flownet-journal-club.pdf", "application/pdf", 4.9,
     "A discussion-oriented deck for reading groups: assumptions, threats to validity, and open questions.",
     "2025-12-04", 0),
    ("slides", "Guest Lecture Slides: RL for Systems Problems",
     f"{BASE}/slides/guest-lecture-2026.pdf", "application/pdf", 14.6,
     "Slides from the university guest lecture, with extended background material on MDP formulations.",
     "2026-03-05", 0),
    ("slides", "FlowNet Onboarding Deck for New Contributors",
     f"{BASE}/slides/flownet-onboarding.pdf", "application/pdf", 6.3,
     "Orientation deck for new project contributors: architecture map, module ownership, and roadmap.",
     "2026-04-09", 0),
    # ---- papers / reports ----------------------------------------------
    ("paper_pdf", "FlowNet arXiv Preprint (v1, May 2025)",
     f"{BASE}/papers/flownet-arxiv-v1.pdf", "application/pdf", 3.8,
     "Original arXiv preprint posted ahead of the ICML review cycle.",
     "2025-05-22", 0),
    ("paper_pdf", "FlowNet arXiv Preprint (v2, camera-ready alignment)",
     f"{BASE}/papers/flownet-arxiv-v2.pdf", "application/pdf", 4.1,
     "Revised preprint aligned with the ICML camera-ready, with corrected Table 3 and expanded related work.",
     "2025-07-25", 0),
    ("paper_pdf", "Workshop Paper: Reward Shaping for Workflow Routing",
     f"{BASE}/papers/flownet-workshop-reward-shaping.pdf", "application/pdf", 1.9,
     "Four-page workshop paper studying reward-weight sensitivity in the FlowNet objective.",
     "2025-12-13", 0),
    ("paper_pdf", "Technical Report TR-2026-01: FlowNet at Scale",
     f"{BASE}/papers/flownet-tr-2026-01.pdf", "application/pdf", 5.6,
     "Extended technical report on scaling the learned router to multi-region MeridianFlow clusters.",
     "2026-02-18", 0),
    ("paper_pdf", "FlowNet One-Page Executive Summary",
     f"{BASE}/papers/flownet-exec-summary.pdf", "application/pdf", 0.8,
     "Non-technical one-page overview of the project for stakeholders and partner teams.",
     "2025-08-28", 0),
    # ---- posters --------------------------------------------------------
    ("poster", "Meridian Research Day Poster 2025",
     f"{BASE}/poster/flownet-research-day-2025.pdf", "application/pdf", 7.2,
     "Poster presented at the internal Meridian Systems research day, updated with production results.",
     "2025-10-30", 0),
    ("poster", "Systems Workshop Poster: Shadow Deployment Study",
     f"{BASE}/poster/flownet-shadow-deploy-poster.pdf", "application/pdf", 6.8,
     "Workshop poster summarizing the three-month shadow deployment ablation.",
     "2025-12-13", 0),
    # ---- datasets -------------------------------------------------------
    ("dataset", "FlowNet Benchmark Dataset v1.1 (patch release)",
     f"{BASE}/data/flownet-benchmark-v1.1.tar.gz", "application/gzip", 2410.0,
     "Patch release fixing timestamp drift in 4 of the 90 trace days; results in the paper are unaffected.",
     "2025-09-09", 0),
    ("dataset", "FlowNet Benchmark Validation Split",
     f"{BASE}/data/flownet-benchmark-val-split.tar.gz", "application/gzip", 480.0,
     "Held-out validation traces used for early stopping in all reported experiments.",
     "2025-09-09", 0),
    ("dataset", "Ablation Traces: Queue-Depth Perturbation Suite",
     f"{BASE}/data/flownet-ablation-queue-depth.tar.gz", "application/gzip", 640.0,
     "Synthetic trace suite with controlled queue-depth spikes used in the robustness ablations.",
     "2025-11-20", 0),
    ("dataset", "Replay Traces Q4 2025 (anonymized)",
     f"{BASE}/data/flownet-replay-2025q4.tar.gz", "application/gzip", 1870.0,
     "Quarterly refresh of anonymized MeridianFlow replay traffic for longitudinal evaluation.",
     "2026-01-15", 0),
    ("dataset", "Replay Traces Q1 2026 (anonymized)",
     f"{BASE}/data/flownet-replay-2026q1.tar.gz", "application/gzip", 1930.0,
     "Quarterly refresh of anonymized replay traffic, including the February failover window.",
     "2026-04-14", 0),
    ("dataset", "Hyperparameter Sweep Results (raw metrics)",
     f"{BASE}/data/flownet-sweep-metrics.parquet", "application/octet-stream", 210.0,
     "Raw metric tables for the 312-run hyperparameter sweep behind Figure 5.",
     "2025-08-07", 0),
    ("dataset", "Scheduler Stress-Test Traces",
     f"{BASE}/data/flownet-stress-traces.tar.gz", "application/gzip", 820.0,
     "High-load synthetic traces used for the tail-latency stress evaluation in the tech report.",
     "2026-02-18", 0),
    # ---- supplementary --------------------------------------------------
    ("supplementary", "Hyperparameter Reference Sheet",
     f"{BASE}/papers/flownet-hyperparameters.pdf", "application/pdf", 0.4,
     "Single-table reference of every hyperparameter used in the paper, tutorials, and tech report.",
     "2025-08-07", 0),
    ("supplementary", "Extended Ablation Appendix (v2)",
     f"{BASE}/papers/flownet-ablation-appendix-v2.pdf", "application/pdf", 2.7,
     "Updated appendix adding the queue-depth perturbation and reward-shaping ablations.",
     "2025-11-27", 0),
    ("supplementary", "Convergence Analysis Addendum",
     f"{BASE}/papers/flownet-convergence-addendum.pdf", "application/pdf", 1.3,
     "Addendum tightening the convergence bound of Theorem 2 under bounded queue growth.",
     "2025-10-09", 0),
    ("supplementary", "Reproducibility Checklist and Environment Notes",
     f"{BASE}/papers/flownet-repro-checklist.pdf", "application/pdf", 0.6,
     "Completed reproducibility checklist with hardware, seeds, and environment details for every table.",
     "2025-07-25", 0),
    ("supplementary", "Architecture Diagram Pack (editable)",
     f"{BASE}/papers/flownet-diagrams.zip", "application/zip", 22.5,
     "Editable diagrams of the graph module, temporal attention block, and hierarchical action space.",
     "2025-09-30", 0),
    ("supplementary", "Reviewer Q&A Digest",
     f"{BASE}/papers/flownet-reviewer-qa.pdf", "application/pdf", 0.9,
     "Curated questions from the review cycle and poster sessions with the authors' answers.",
     "2025-08-20", 0),
    # ---- blog posts / release notes ------------------------------------
    ("blog_post", "FlowNet v0.2 Release Notes",
     f"{BLOG}/flownet-v0-2-release-notes", "text/html", 0.0,
     "Release notes for v0.2: faster trace loader, deterministic evaluation seeds, and a smaller demo config.",
     "2025-10-21", 0),
    ("blog_post", "FlowNet v0.3 Release Notes",
     f"{BLOG}/flownet-v0-3-release-notes", "text/html", 0.0,
     "Release notes for v0.3: multi-region routing support and the shadow-deployment harness.",
     "2026-01-29", 0),
    ("blog_post", "FlowNet v1.0 Release Notes",
     f"{BLOG}/flownet-v1-0-release-notes", "text/html", 0.0,
     "Release notes for the stable v1.0: frozen policy format, long-term support plan, and upgrade guide.",
     "2026-05-12", 0),
    ("blog_post", "Six Months After ICML: What Held Up in Production",
     f"{BLOG}/flownet-six-months-after-icml", "text/html", 0.0,
     "A retrospective on which paper results held up after six months of live traffic, and which needed retuning.",
     "2026-02-03", 0),
    ("blog_post", "Community Roundup: FlowNet Ports and Extensions",
     f"{BLOG}/flownet-community-roundup-2026", "text/html", 0.0,
     "A roundup of community projects building on FlowNet, from a Kubernetes operator to a Ray integration.",
     "2026-06-10", 0),
    ("blog_post", "How We Anonymize Workflow Traces",
     f"{BLOG}/flownet-trace-anonymization", "text/html", 0.0,
     "Behind the scenes of the benchmark dataset: the anonymization pipeline and what we redact and why.",
     "2025-06-19", 0),
    ("blog_post", "Reading the FlowNet Training Curves",
     f"{BLOG}/flownet-reading-training-curves", "text/html", 0.0,
     "A practical guide to diagnosing reward collapse and exploration stalls when training routing policies.",
     "2025-11-13", 0),
]

# (root_user_id, username, full_name, email_local, role, department)
USERS = [
    (2, "priya_sharma", "Priya Sharma", "priya.sharma", "advisor", "Engineering"),
    (7, "david_petrov", "David Petrov", "david.petrov", "maintainer", "Engineering"),
    (3, "marcus_chen", "Marcus Chen", "marcus.chen", "contributor", "Engineering"),
    (12, "natalie_kim", "Natalie Kim", "natalie.kim", "contributor", "Data Science"),
    (5, "ryan_tanaka", "Ryan Tanaka", "ryan.tanaka", "contributor", "Engineering"),
    (11, "brian_reeves", "Brian Reeves", "brian.reeves", "contributor", "Infrastructure"),
]

# Substrings that must never appear in searchable text of new rows.
# "code" also covers encode/decode/codebase; license names guard the
# search_by_query task whose expected answer is Apache-2.0.
FORBIDDEN = ("code", "apache", "gpl", "bsd", "cc-by", "license", "mit")


def _guard(text, label):
    low = f" {text.lower()} "
    for w in FORBIDDEN:
        assert w not in low, f"{label} contains forbidden substring {w!r}"
    # 'mit' only as a standalone word (avoid false hits on 'submitted' etc.)
    tokens = {t.strip(".,:;()[]") for t in low.split()}
    assert "mit" not in tokens, f"{label} contains standalone 'MIT'"


def build_rows(db):
    new = {"resources": [], "users": []}

    next_res = db.execute(
        "SELECT COALESCE(MAX(id),0)+1 FROM project_homepages_resources").fetchone()[0]
    for rtype, title, url, fmt, size, desc, date_added, minutes in RESOURCES:
        # search text on the site is "title description type"
        _guard(f"{title} {desc} {rtype}", title)
        new["resources"].append({
            "id": next_res, "type": rtype, "title": title, "url": url,
            "format": fmt, "size_mb": size, "description": desc,
            "date_added": date_added, "license": "",
            "duration_minutes": minutes,
        })
        next_res += 1

    next_uid = db.execute(
        "SELECT COALESCE(MAX(id),0)+1 FROM project_homepages_users").fetchone()[0]
    for root_id, username, full_name, email_local, role, dept in USERS:
        _guard(f"{full_name} {role} {dept} Meridian Systems {email_local}",
               full_name)
        new["users"].append({
            "id": next_uid, "root_user_id": root_id, "username": username,
            "full_name": full_name,
            "email": f"{email_local}@meridiansystems.com",
            "role": role, "affiliation": "Meridian Systems",
            "department": dept,
        })
        next_uid += 1
    return new


def main():
    dry = "--dry-run" in sys.argv
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.row_factory = sqlite3.Row

    new = build_rows(db)
    for t, rows in new.items():
        print(f"{t}: +{len(rows)}")

    if dry:
        for t, rows in new.items():
            for r in rows[:2]:
                print(" ", json.dumps(r, default=str)[:150])
        db.close()
        return

    # snapshot of ids matching a "code" search over resources, pre-insert
    pre_code_ids = [r[0] for r in db.execute(
        "SELECT id FROM project_homepages_resources WHERE "
        "LOWER(title||' '||description||' '||type) LIKE '%code%' ORDER BY id")]

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    (BACKUP_DIR / "inserted_ids.json").write_text(json.dumps(
        {f"project_homepages_{t}": [r["id"] for r in rows]
         for t, rows in new.items()}, indent=1))

    for t, rows in new.items():
        cols = list(rows[0].keys())
        sql = (f"INSERT INTO project_homepages_{t} ({', '.join(cols)}) "
               f"VALUES ({', '.join('?' * len(cols))})")
        db.executemany(sql, [[r[c] for c in cols] for r in rows])
    db.commit()

    # ---- post-insert task-constraint verification -----------------------
    post_code_ids = [r[0] for r in db.execute(
        "SELECT id FROM project_homepages_resources WHERE "
        "LOWER(title||' '||description||' '||type) LIKE '%code%' ORDER BY id")]
    assert post_code_ids == pre_code_ids, \
        f"'code' search result set changed: {post_code_ids}"
    lic = db.execute(
        "SELECT COUNT(*) FROM project_homepages_resources WHERE id > 8 AND "
        "(license != '' OR LOWER(title||' '||description) LIKE '%apache%')"
    ).fetchone()[0]
    assert lic == 0, "new resource carries a license string"
    proj_lic = db.execute(
        "SELECT sections FROM project_homepages_project WHERE id='flownet-2025'"
    ).fetchone()[0]
    assert json.loads(proj_lic)["code_link"]["license"] == "Apache-2.0"
    print("constraint checks passed: 'code' search result set unchanged "
          f"({pre_code_ids}); Apache-2.0 still unique in code section")
    print(f"inserted; rollback ids at {BACKUP_DIR}/inserted_ids.json")
    db.close()


if __name__ == "__main__":
    main()
