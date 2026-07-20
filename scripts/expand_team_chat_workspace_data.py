"""Expand team-chat-workspace (Meridian Systems Chat) base data.

The workspace ships with ~3044 rows (2985 messages, 12 users, 10 channels,
30 reactions, 7 threads). Adds deterministic (seeded) synthetic data to reach
>=5000 total rows: 8 new employees, 4 new channels (design, marketing,
customer-success, security), ~1900 messages, ~80 reactions, 6 threads.

Task-safety constraints honoured (insert-only, never UPDATE/DELETE):
- NO messages added to ch-sales (translation/extraction task on June 23 msgs).
- NO messages authored by tc-u001 / alex.rivera anywhere (protects "edit your
  most recent message in Engineering" and "message you posted on Dec 19 2025").
- Messages added to EXISTING channels are all dated 2025-09-01..2025-12-07,
  strictly OLDER than the existing minimum timestamp (2025-12-08), so every
  channel's latest message and all recency extremums are unchanged.
- New-channel messages end 2026-06-22, older than the global max (2026-06-26).
- Reactions/threads only attach to NEW messages, so existing rows'
  reactions_count / thread_count stay untouched.
- Each channel stays under ~500 messages (channel view renders unpaginated).

Insert-only; inserted ids recorded under data/backups/ for rollback.

Usage: python scripts/expand_team_chat_workspace_data.py [--dry-run]
"""
import datetime
import json
import random
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "trimmed_miniweb.db"
rng = random.Random(4242)

P = "team_chat_workspace_"

# ---------------------------------------------------------------------------
# New users (tc-u013..tc-u020) — never tc-u001
# ---------------------------------------------------------------------------
NEW_USERS = [
    ("tc-u013", 13, "elena.vasquez", "Elena Vasquez", "Design", "Senior Product Designer",
     ":art:", "Figma all day", "2023-02-13"),
    ("tc-u014", 14, "james.osei", "James Osei", "Design", "UX Researcher",
     ":mag:", "User interviews this week", "2024-01-08"),
    ("tc-u015", 15, "mei.wong", "Mei Wong", "Marketing", "Content Marketing Manager",
     ":memo:", "Drafting the Q2 newsletter", "2022-11-01"),
    ("tc-u016", 16, "omar.haddad", "Omar Haddad", "Marketing", "Growth Marketing Lead",
     ":chart_with_upwards_trend:", "", "2023-06-19"),
    ("tc-u017", 17, "sofia.lindqvist", "Sofia Lindqvist", "Customer Success", "Support Engineer",
     ":headphones:", "On the support queue", "2023-09-04"),
    ("tc-u018", 18, "derek.coleman", "Derek Coleman", "Engineering", "Security Engineer",
     ":lock:", "Pentest season", "2022-03-14"),
    ("tc-u019", 19, "hannah.brooks", "Hannah Brooks", "Engineering", "QA Engineer",
     ":white_check_mark:", "", "2024-04-22"),
    ("tc-u020", 20, "lucas.moreau", "Lucas Moreau", "Engineering", "Frontend Engineer",
     ":computer:", "Refactoring the sidebar", "2024-09-02"),
]

# ---------------------------------------------------------------------------
# New channels
# ---------------------------------------------------------------------------
NEW_CHANNELS = [
    ("ch-design", "design", "Design critiques, Figma links, and UX research findings",
     "tc-u004", "2025-09-15", 14, "Critique sessions Wed 1pm PT. Drop Figma links with context.", 3),
    ("ch-marketing", "marketing", "Campaigns, launches, content calendar, and brand discussions",
     "tc-u006", "2025-09-22", 11, "Q2 campaign: MeridianFlow 2.0 launch — assets due June 5", 2),
    ("ch-customer-success", "customer-success", "Customer escalations, renewals, and success stories",
     "tc-u009", "2025-10-01", 13, "Escalation SLA: first response within 2 business hours", 4),
    ("ch-security", "security", "Security reviews, vulnerability reports, and compliance work",
     "tc-u007", "2025-10-06", 16, "Report vulns via /security-report. SOC 2 audit prep in pinned doc.", 6),
]

# author pools per channel (never tc-u001)
ENG = ["tc-u002", "tc-u003", "tc-u007", "tc-u008", "tc-u012", "tc-u018", "tc-u019", "tc-u020"]
ALL_NO_ALEX = ["tc-u%03d" % i for i in range(2, 21)]
CHANNEL_AUTHORS = {
    "ch-board-games": ["tc-u003", "tc-u004", "tc-u006", "tc-u009", "tc-u012", "tc-u014", "tc-u015", "tc-u019"],
    "ch-data-science": ["tc-u010", "tc-u003", "tc-u002", "tc-u012", "tc-u004", "tc-u016"],
    "ch-deployments": ENG,
    "ch-engineering": ENG,
    "ch-general": ALL_NO_ALEX,
    "ch-incidents": ENG + ["tc-u009", "tc-u017"],
    "ch-product": ["tc-u004", "tc-u002", "tc-u008", "tc-u005", "tc-u009", "tc-u013", "tc-u014"],
    "ch-random": ALL_NO_ALEX,
    "ch-standup-notes": ENG,
    "ch-design": ["tc-u013", "tc-u014", "tc-u004", "tc-u006", "tc-u020", "tc-u002"],
    "ch-marketing": ["tc-u015", "tc-u016", "tc-u006", "tc-u005", "tc-u004", "tc-u009"],
    "ch-customer-success": ["tc-u009", "tc-u017", "tc-u005", "tc-u004", "tc-u002", "tc-u006"],
    "ch-security": ["tc-u018", "tc-u007", "tc-u002", "tc-u008", "tc-u003", "tc-u019"],
}

FEATURES = ["approval chains", "the webhook dispatcher", "workflow templates", "the audit log",
            "SSO login", "the notification center", "bulk export", "the analytics dashboard",
            "custom fields", "the mobile app", "role-based permissions", "the API rate limiter"]
SERVICES = ["auth-service", "billing-service", "notification-service", "workflow-engine",
            "report-generator", "ingest-pipeline", "search-indexer", "gateway"]
CUSTOMERS = ["Northwind Logistics", "Cascadia Utilities", "Lakeport Medical Group",
             "Pinnacle Insurance", "TerraForm Agriculture", "BlueHarbor Financial",
             "Summit Ridge Bank", "Orchard Grove Schools"]
PEOPLE = ["@priya.sharma", "@marcus.chen", "@jessica.okafor", "@david.petrov",
          "@natalie.kim", "@aisha.patel", "@tom.bradley", "@elena.vasquez",
          "@derek.coleman", "@hannah.brooks", "@lucas.moreau", "@mei.wong"]

T = {
    "ch-engineering": [
        "PR #{n} is up for review — refactors the {svc} retry logic. Should be a quick one.",
        "Anyone seen flaky failures in the {svc} integration tests? Third re-run this morning.",
        "Heads up: bumping the Go version to 1.2{d} on {svc} next sprint. Changelog in the wiki.",
        "{person} can you take a look at the migration in PR #{n}? Touches the workflows table.",
        "TIL: our linter config was silently skipping generated files. Fixed in PR #{n}.",
        "Design doc for the {feat} rework is ready for comments. Link in the eng wiki.",
        "The {svc} memory usage doubled after the last release — profiling now, will report back.",
        "Reminder: architecture review at 2pm, we're covering the {feat} proposal.",
        "Merged PR #{n}. {person} thanks for the thorough review!",
        "Who owns {svc} these days? Getting a deprecation warning from its client library.",
    ],
    "ch-deployments": [
        "Deploying {svc} v{v} to staging. Changes: {feat} fixes and dependency bumps.",
        "{svc} v{v} promoted to production. Canary was green for 30 minutes.",
        "Rollback notice: {svc} v{v} reverted due to elevated 5xx rate. Investigating.",
        "Deploy window opens at 10am — {svc} and {svc2} in the queue today.",
        "Hotfix {svc} v{v} shipped for the {feat} regression. Monitoring dashboards.",
        "Freeze reminder: no deploys Friday. Get your changes in by Thursday 2pm.",
        "Migration for {svc} completed in 4m{d}s, zero downtime. Nice work {person}.",
        "Canary metrics for {svc} v{v}: error rate flat, p95 down 12ms. Promoting.",
    ],
    "ch-incidents": [
        "INC-{n3}: elevated latency on {svc}. Severity 3. {person} investigating.",
        "INC-{n3} update: root cause is connection pool exhaustion in {svc}. Fix in progress.",
        "INC-{n3} resolved. Duration 4{d}m. Post-mortem doc by Friday.",
        "Seeing intermittent timeouts from {svc} in us-east. Anyone else?",
        "Status page updated for the {feat} degradation. Customer comms went out.",
        "Post-mortem for INC-{n3} posted — action items assigned, please review yours.",
        "Paging {person} — {svc} health checks failing on two pods.",
        "All green again. {svc} recovered after the cache flush.",
    ],
    "ch-standup-notes": [
        "Y: shipped {feat} fixes. T: reviewing PR #{n}. B: none.",
        "Y: debugged {svc} test flakes. T: pairing with {person} on {feat}. B: waiting on staging access.",
        "Y: design doc draft. T: incorporating review feedback. B: none.",
        "Y: closed 3 tickets on {feat}. T: starting the {svc} upgrade. B: need prod read access.",
        "Y: interviews. T: {feat} estimates for planning. B: calendar is a mess.",
        "Y: on-call handoff, wrote runbook updates. T: {svc} alert tuning. B: none.",
        "OOO tomorrow — {person} is covering my reviews.",
    ],
    "ch-general": [
        "Welcome aboard {person}! Say hi in your team channels.",
        "All-hands moved to Thursday 11am — same agenda, calendar updated.",
        "The Lakeport office HVAC work finished — 4th floor open again on Monday.",
        "New expense policy doc is up on the intranet. TL;DR: receipts over $2{d}.",
        "Q2 company update from leadership is posted. Great quarter, team!",
        "IT reminder: mandatory security training due by end of month.",
        "Benefits enrollment window opens Monday. HR office hours Tue/Thu.",
        "Congrats to the {feat} team on the launch — customers already noticing!",
        "Parking garage badge readers get replaced this weekend — use the north entrance.",
    ],
    "ch-random": [
        "Coffee machine on 3 is fixed. The espresso is dangerously good now.",
        "Anyone else watching the Cascadia Cup final tonight?",
        "Lunch crew: new taco place on 5th, leaving at 12:15, join us.",
        "My sourdough starter is now older than my tenure here. AMA.",
        "Found a great hiking trail past Lakeport ridge this weekend — photos in thread.",
        "The office plant on 4 has a name now. Say hello to Ferndinand.",
        "Friday playlist suggestions? Building this week's queue.",
        "PSA: the good snacks are restocked. Act accordingly.",
        "Cat picture tax for the new folks incoming.",
    ],
    "ch-board-games": [
        "Thursday lunch: Settlers again or should we try Wingspan?",
        "Bringing Azul and Codenames tomorrow. Sign up in the thread.",
        "GG {person} — that last-round comeback in Ticket to Ride was brutal.",
        "New arrivals on the shelf: Cascadia (fitting) and 7 Wonders Duel.",
        "Tournament bracket is up on the whiteboard by the kitchen.",
        "We need a 4th for the after-work Catan session, any takers?",
        "Rules question from yesterday settled — the official FAQ agrees with {person}.",
    ],
    "ch-data-science": [
        "Retrained the churn model — AUC up to 0.8{d} with the new usage features.",
        "The {feat} funnel dashboard is live in the analytics workspace.",
        "Data catalog updated: added lineage for the {svc} event streams.",
        "Backfill for the events table finished — 1{d}M rows, dedupe checks pass.",
        "Anyone have a good notebook for cohort retention curves? Building one for Q2.",
        "Feature store sync was stuck overnight; re-ran it, metrics are current again.",
        "A/B result on the {feat} experiment: +{d}.2% activation, significant at 95%.",
    ],
    "ch-product": [
        "Roadmap update: {feat} moves to next sprint, {feat2} stays on track.",
        "Customer interview notes from {cust} are in the research repo — worth a read.",
        "Spec for {feat} is ready for eng review. Comments by Wednesday please.",
        "{cust} asked about {feat} on the QBR call — third request this month.",
        "Prioritization call tomorrow: bring your top three asks.",
        "Usage data shows {feat} adoption at 4{d}% after two weeks. Above target.",
        "Drafting the release notes for the next drop — ping me with highlights.",
    ],
    "ch-design": [
        "Critique agenda for Wednesday: {feat} empty states and the onboarding flow.",
        "Figma file for the {feat} redesign is ready — comments welcome until Friday.",
        "Research readout: 6 of 8 participants missed the {feat} entry point. Deck in the drive.",
        "New icon set merged into the design system library — v2.{d} published.",
        "Contrast audit done on the dashboard — two fails, fixes in the tokens PR.",
        "Prototype for the mobile {feat} flow is up, tap through and leave notes.",
        "{person} the spacing tokens you asked about are documented now.",
        "Usability session recordings from {cust} are tagged and in the repo.",
    ],
    "ch-marketing": [
        "Draft of the {feat} launch post is in the content calendar — reviews by Thursday.",
        "Webinar signups at 2{d}0 — pacing ahead of the last one.",
        "New case study with {cust} is live on the website.",
        "Email nurture sequence for trial users shipped — open rate 4{d}% on day one.",
        "Social assets for the launch are in the shared drive, sized for all channels.",
        "SEO review done: the docs pages need better meta descriptions. Tickets filed.",
        "Booth staffing for the Cascadia SaaS Summit — sign-up sheet posted.",
        "{person} can you fact-check the metrics in the {feat} one-pager?",
    ],
    "ch-customer-success": [
        "{cust} renewal closed — 2-year term, expansion on seats. Great save {person}.",
        "Escalation from {cust}: {feat} exports timing out. Eng ticket filed, tracking here.",
        "QBR deck template updated for Q2 — please use the new one going forward.",
        "Health score dip on {cust} — usage down 3{d}% month over month. Scheduling a check-in.",
        "Onboarding for {cust} completed in 12 days, fastest this quarter.",
        "NPS responses are in: 4{d} this quarter, up two points.",
        "{cust} gave us a reference for the {feat} case study. Marketing is thrilled.",
        "Support queue is spiking on {feat} questions — drafting a help-center article.",
    ],
    "ch-security": [
        "Dependency scan flagged a high CVE in {svc} — patch PR #{n} is up.",
        "SOC 2 evidence collection is 8{d}% done. Remaining items assigned in the tracker.",
        "Pentest kickoff Monday — scope doc pinned. External team needs staging access.",
        "Rotated the {svc} API keys — clients updated, old keys revoked.",
        "Phishing drill results: 4 clicks out of 12{d} sends. Training refresher scheduled.",
        "Access review for Q2 done — removed 7 stale accounts, report in the drive.",
        "New secrets-scanning hook enabled on all repos. Docs in the security wiki.",
        "{person} the vuln you reported is confirmed — severity medium, fix in sprint.",
    ],
}

# messages to add per channel (existing channels stay < ~440 total,
# rendered unpaginated by channel_view)
PLAN_EXISTING = {  # dated 2025-09-01 .. 2025-12-07 (older than existing min)
    "ch-board-games": 140, "ch-data-science": 140, "ch-deployments": 140,
    "ch-engineering": 120, "ch-general": 130, "ch-incidents": 140,
    "ch-product": 140, "ch-random": 130, "ch-standup-notes": 140,
}
PLAN_NEW = {"ch-design": 170, "ch-marketing": 170,
            "ch-customer-success": 170, "ch-security": 170}

EMOJI = [":thumbsup:", ":tada:", ":heart:", ":rocket:", ":clap:", ":fire:",
         ":eyes:", ":star:", ":muscle:", ":100:", ":raised_hands:",
         ":white_check_mark:", ":joy:", ":coffee:"]


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def rand_dt(rng, start, end):
    delta = int((end - start).total_seconds())
    return start + datetime.timedelta(seconds=rng.randrange(delta))


def fill(tpl):
    feat, feat2 = rng.sample(FEATURES, 2)
    svc, svc2 = rng.sample(SERVICES, 2)
    return (tpl.replace("{feat2}", feat2).replace("{feat}", feat)
            .replace("{svc2}", svc2).replace("{svc}", svc)
            .replace("{cust}", rng.choice(CUSTOMERS))
            .replace("{person}", rng.choice(PEOPLE))
            .replace("{n3}", str(rng.randrange(900, 999)))
            .replace("{n}", str(rng.randrange(1250, 1900)))
            .replace("{v}", "%d.%d.%d" % (rng.randrange(2, 4), rng.randrange(0, 20), rng.randrange(0, 6)))
            .replace("{d}", str(rng.randrange(1, 9))))


THREAD_SPECS = [
    ("ch-design", "Onboarding flow redesign feedback",
     ["tc-u013", "tc-u014", "tc-u004", "tc-u020"],
     ["First round of feedback: the progress indicator reads as clickable but isn't. Suggest making it either interactive or visually flatter.",
      "Agreed. Also the empty state on step 3 gives no hint about what a 'workspace template' is. A one-line example would help.",
      "From the product side: can we keep the skip option visible? Data shows forced tours hurt activation.",
      "I can prototype both variants this week and we A/B them in the next release."]),
    ("ch-security", "CVE triage for gateway dependency",
     ["tc-u018", "tc-u007", "tc-u003"],
     ["The affected code path is only reachable if HTTP/2 is enabled, which we have on in prod. Treating as high priority.",
      "Patch bumps the library two majors — I'll run the full integration suite against staging before we ship.",
      "Suite is green. Let's ship it in tomorrow's window and backport to the LTS branch."]),
    ("ch-marketing", "Launch post review thread",
     ["tc-u015", "tc-u016", "tc-u006", "tc-u004"],
     ["Draft is solid but the intro buries the lede — move the customer quote up top.",
      "Done. Also swapped the hero screenshot for the annotated one from the demo.",
      "Can we add the migration guide link for existing customers? Support will thank us.",
      "Added. Scheduling for Tuesday 9am PT with the email blast."]),
    ("ch-customer-success", "Escalation: export timeouts",
     ["tc-u017", "tc-u009", "tc-u003", "tc-u017"],
     ["Reproduced it: exports over 50k rows hit the gateway timeout. Affects three accounts so far.",
      "Customer impact is contained — they can chunk exports as a workaround. Comms sent.",
      "Eng fix is to stream the export instead of buffering. PR up, should land this sprint.",
      "Confirmed fixed on staging with a 200k-row export. Closing the escalation after release."]),
    ("ch-design", "Design tokens v2 rollout",
     ["tc-u013", "tc-u020", "tc-u002"],
     ["All spacing and color tokens are now semantic. Migration table is in the readme.",
      "Frontend migration is about 60% done — the dashboard package is the last big one.",
      "Nice. Let's demo the before/after at Friday's eng sync."]),
    ("ch-security", "Q2 access review findings",
     ["tc-u018", "tc-u008", "tc-u007"],
     ["Seven stale accounts removed, two service accounts had broader scopes than needed — narrowed.",
      "Good. Please add the scope-narrowing to the quarterly checklist so it's not ad hoc.",
      "Also automating the stale-account report — draft cron lands next week."]),
]


def main():
    dry = "--dry-run" in sys.argv
    con = sqlite3.connect(DB_PATH, timeout=60)
    con.row_factory = sqlite3.Row

    # sanity: current state
    existing_min_ts = con.execute(
        f"SELECT MIN(timestamp) FROM {P}messages").fetchone()[0]
    assert existing_min_ts >= "2025-12-08", existing_min_ts
    max_num_id = con.execute(
        f"SELECT MAX(CAST(id AS INTEGER)) FROM {P}messages WHERE id NOT GLOB 'msg-*'"
    ).fetchone()[0]
    next_id = max_num_id + 1
    assert next_id == 2901, next_id

    # --- users ------------------------------------------------------------
    users_new = []
    for uid, root, uname, disp, dept, title, s_emoji, s_text, joined in NEW_USERS:
        last_active = iso(rand_dt(rng, datetime.datetime(2026, 6, 24),
                                  datetime.datetime(2026, 6, 26, 12)))
        users_new.append({
            "id": uid, "root_user_id": root, "username": uname,
            "display_name": disp, "email": f"{uname}@meridiansystems.com",
            "status": rng.choice(["active", "active", "active", "away"]),
            "status_emoji": s_emoji, "status_text": s_text, "title": title,
            "department": dept, "timezone": rng.choice(
                ["America/Los_Angeles", "America/Los_Angeles", "America/New_York", "Europe/Stockholm"]),
            "avatar_url": "/avatars/%s.jpg" % uname.replace(".", "_"),
            "joined_date": joined, "last_active": last_active, "is_admin": 0,
        })

    # --- channels ---------------------------------------------------------
    channels_new = []
    for cid, name, desc, creator, cdate, members, topic, pinned in NEW_CHANNELS:
        channels_new.append({
            "id": cid, "name": name, "description": desc, "is_private": 0,
            "created_by": creator, "created_date": cdate,
            "member_count": members, "topic": topic, "pinned_count": pinned,
        })

    # --- messages ---------------------------------------------------------
    msgs_new = []
    for cid, count in sorted(PLAN_EXISTING.items()):
        start = datetime.datetime(2025, 9, 1)
        end = datetime.datetime(2025, 12, 7, 23, 59)   # strictly before existing min
        stamps = sorted(rand_dt(rng, start, end) for _ in range(count))
        for ts in stamps:
            msgs_new.append({
                "id": str(next_id), "channel_id": cid,
                "user_id": rng.choice(CHANNEL_AUTHORS[cid]),
                "timestamp": iso(ts), "text": fill(rng.choice(T[cid])),
                "edited": 1 if rng.random() < 0.03 else 0,
                "reactions_count": 0, "thread_count": 0,
            })
            next_id += 1
    for cid, count in sorted(PLAN_NEW.items()):
        cdate = dict((c["id"], c["created_date"]) for c in channels_new)[cid]
        start = datetime.datetime.strptime(cdate, "%Y-%m-%d") + datetime.timedelta(days=1)
        end = datetime.datetime(2026, 6, 22, 23, 59)   # before global max & June 23
        stamps = sorted(rand_dt(rng, start, end) for _ in range(count))
        for ts in stamps:
            msgs_new.append({
                "id": str(next_id), "channel_id": cid,
                "user_id": rng.choice(CHANNEL_AUTHORS[cid]),
                "timestamp": iso(ts), "text": fill(rng.choice(T[cid])),
                "edited": 1 if rng.random() < 0.03 else 0,
                "reactions_count": 0, "thread_count": 0,
            })
            next_id += 1

    msg_by_id = {m["id"]: m for m in msgs_new}
    new_channel_msgs = [m for m in msgs_new if m["channel_id"] in PLAN_NEW]

    # --- reactions (on NEW messages only) ---------------------------------
    reactions_new = []
    rxn_id = 31
    targets = rng.sample(msgs_new, 60)
    for m in targets:
        n = rng.choice([1, 1, 1, 2, 2, 3])
        reactors = rng.sample([u for u in ALL_NO_ALEX + ["tc-u001"] if u != m["user_id"]], n)
        base = datetime.datetime.strptime(m["timestamp"], "%Y-%m-%dT%H:%M:%SZ")
        emoji = rng.choice(EMOJI)
        for i, ru in enumerate(reactors):
            if len(reactions_new) >= 80:
                break
            reactions_new.append({
                "id": "rxn-%03d" % rxn_id, "message_id": m["id"], "user_id": ru,
                "emoji": emoji if rng.random() < 0.7 else rng.choice(EMOJI),
                "timestamp": iso(base + datetime.timedelta(minutes=2 + 3 * i)),
            })
            rxn_id += 1
            m["reactions_count"] += 1
        if len(reactions_new) >= 80:
            break

    # --- threads (parents are NEW messages in NEW channels) ---------------
    threads_new = []
    parent_pool = [m for m in new_channel_msgs if m["timestamp"] >= "2026-05-01"]
    used_parents = set()
    for i, (cid, topic, repliers, texts) in enumerate(THREAD_SPECS):
        cands = [m for m in parent_pool if m["channel_id"] == cid
                 and m["id"] not in used_parents]
        parent = rng.choice(cands)
        used_parents.add(parent["id"])
        tid = "thr-%03d" % (8 + i)
        base = datetime.datetime.strptime(parent["timestamp"], "%Y-%m-%dT%H:%M:%SZ")
        replies = []
        for j, (ru, txt) in enumerate(zip(repliers, texts)):
            replies.append({"id": "%s-r%d" % (tid, j + 1), "user_id": ru,
                            "timestamp": iso(base + datetime.timedelta(minutes=15 * (j + 1))),
                            "text": txt})
        parent["thread_count"] = len(replies)
        threads_new.append({"id": tid, "parent_message_id": parent["id"],
                            "channel_id": cid, "topic": topic,
                            "replies": json.dumps(replies)})

    print(f"users: +{len(users_new)}, channels: +{len(channels_new)}, "
          f"messages: +{len(msgs_new)}, reactions: +{len(reactions_new)}, "
          f"threads: +{len(threads_new)}")
    per_ch = {}
    for m in msgs_new:
        per_ch[m["channel_id"]] = per_ch.get(m["channel_id"], 0) + 1
    print("per-channel additions:", per_ch)
    assert not any(m["channel_id"] == "ch-sales" for m in msgs_new)
    assert not any(m["user_id"] == "tc-u001" for m in msgs_new)
    assert all(m["timestamp"] < existing_min_ts for m in msgs_new
               if m["channel_id"] in PLAN_EXISTING)

    if dry:
        for m in msgs_new[:3] + new_channel_msgs[:3]:
            print(" ", m["channel_id"], m["timestamp"], m["user_id"], "|", m["text"][:70])
        con.close()
        return

    bdir = ROOT / "data" / "backups" / "team-chat-workspace-expansion-2026-07-20"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "inserted_ids.json").write_text(json.dumps({
        "users": [u["id"] for u in users_new],
        "channels": [c["id"] for c in channels_new],
        "messages": [m["id"] for m in msgs_new],
        "reactions": [r["id"] for r in reactions_new],
        "threads": [t["id"] for t in threads_new]}, indent=1))

    for table, rows in (("users", users_new), ("channels", channels_new),
                        ("messages", msgs_new), ("reactions", reactions_new),
                        ("threads", threads_new)):
        cols = list(rows[0].keys())
        con.executemany(
            f"INSERT INTO {P}{table} ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' * len(cols))})",
            [[r[c] for c in cols] for r in rows])
    # sync FTS indexes (external-content tables; threads has none)
    for t in ("users", "channels", "messages", "reactions"):
        con.execute(f"INSERT INTO fts_{P}{t}(fts_{P}{t}) VALUES('rebuild')")
    con.commit()
    con.close()
    print(f"inserted; rollback ids at {bdir}/inserted_ids.json")


if __name__ == "__main__":
    main()
