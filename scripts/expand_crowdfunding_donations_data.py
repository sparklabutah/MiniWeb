"""Expand crowdfunding-donations (FundSpark) base data.

The site ships with only 10 campaigns, 30 pledges and 8 users (48 rows total),
which makes its filter/sort macros trivial. This adds deterministic (seeded)
synthetic rows: ~32 new campaigns, ~600 new backer users and ~4400 pledges,
bringing the site total to >= 5000 rows.

Consistency rules honoured:
- INSERT-ONLY: existing rows (incl. existing users' backed_campaigns JSON and
  existing campaigns' raised/backer aggregates) are never touched. All new
  pledges attach ONLY to NEW campaigns, and all new pledges belong to NEW
  users, whose backed_campaigns JSON mirrors their pledge rows exactly.
- New campaigns' raised_amount == sum of their pledge amounts, backer_count ==
  number of their pledges (one pledge per user per campaign), and each reward
  tier's quantity_claimed == number of pledges on that tier. Every tier JSON
  follows the existing shape incl. the checkout flow's "fulfillment" field
  ("physical"/"digital").
- status semantics match routes.py: funded => raised >= goal; active =>
  raised < goal and end_date in the future; expired/cancelled => flexible
  campaigns that ended short of goal.
- Vocabulary reuses Lakeport / Meridian / Cascadia branding, existing
  categories, funding models, date style (YYYY-MM-DD) and pledge status
  ("completed").

Inserted ids are recorded in
data/backups/crowdfunding-donations-expansion-2026-07-20/inserted_ids.json.

Usage: python scripts/expand_crowdfunding_donations_data.py [--dry-run]
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

TODAY = datetime.date(2026, 7, 20)

FIRST = ["Maya", "Liam", "Ava", "Noah", "Isla", "Ethan", "Chloe", "Mason",
         "Zoe", "Lucas", "Nora", "Owen", "Ruby", "Caleb", "Hazel", "Jonah",
         "Priya", "Diego", "Amara", "Felix", "Ingrid", "Omar", "Lena", "Theo",
         "Rosa", "Victor", "June", "Andre", "Talia", "Grant", "Mei", "Silas",
         "Freya", "Dmitri", "Carmen", "Hugo", "Anika", "Ravi", "Paloma", "Cole"]
LAST = ["Hartley", "Nguyen", "Alvarez", "Kowalski", "Bennett", "Osei",
        "Lindqvist", "Marsh", "Delgado", "Fitzgerald", "Ito", "Bauer",
        "Castellanos", "Whitfield", "Novak", "Ramirez", "Ferreira", "Boyd",
        "Ashford", "Petrov", "Slater", "Moreau", "Kim", "Donnelly", "Vance",
        "Okafor", "Sandoval", "Hale", "Bishop", "Tanaka", "Reyes", "Crane"]
PW_WORDS = ["maker", "backer", "indie", "pledge", "spark", "studio", "trail",
            "lake", "craft", "mural", "reader", "coder", "banjo", "roast"]
MAIL = ["gmail.com", "gmail.com", "outlook.com", "yahoo.com", "fundspark.com"]

# category -> list of (title, description-seed) campaign concepts
CONCEPTS = {
    "technology": [
        ("PulseBoard: Open-Source Home Energy Monitor",
         "An open-source smart panel that shows every circuit's energy use in real time, built by a Meridian hardware collective."),
        ("Cascadia Mesh: Neighborhood Emergency Network",
         "Solar-powered mesh radio nodes so Lakeport neighborhoods stay connected when storms take the grid down."),
        ("BrightKey: A Keyboard for Low-Vision Typists",
         "A high-contrast, backlit mechanical keyboard designed with the Lakeport Center for Independent Living."),
        ("LoopLogger: Bike Commute Data Tracker",
         "A tiny handlebar sensor that maps pavement quality across the Meridian bike network and shares it openly."),
        ("EchoFrame: DIY Smart Picture Frame Kit",
         "A solder-free kit that turns any thrifted frame into an e-ink photo display, with a classroom curriculum included."),
    ],
    "art": [
        ("Cascadia Ceramics: Community Kiln Rebuild",
         "Rebuilding the shared gas kiln at the Cascadia Clay Collective so forty local potters can fire their work again."),
        ("Harbor Lights: Winter Lantern Walk Installation",
         "Two hundred hand-folded lanterns along the Lakeport harbor boardwalk for the winter solstice festival."),
        ("Meridian Print Shop: Letterpress Restoration",
         "Restoring a 1923 Chandler & Price letterpress and opening free printing hours for local artists."),
        ("Wild Ink: Botanical Illustration Field Guide",
         "A hand-illustrated field guide to the wildflowers of the Cascadia foothills, drawn over four seasons."),
        ("Open Walls: Rotating Gallery in the Old Depot",
         "Converting the disused Meridian rail depot ticket hall into a rotating gallery for emerging artists."),
    ],
    "games": [
        ("Trailhead: A Cooperative Hiking Board Game",
         "A co-op board game about planning summit routes in the Cascadia range, playtested at Lakeport game nights."),
        ("Lantern & Ledger: A Cozy Shopkeeping RPG",
         "A tabletop RPG where players run a village general store, with a solo mode and a gorgeous cloth map."),
        ("Meridian Arcade Co-op: Cabinet Restoration Drive",
         "Restoring six classic arcade cabinets for the member-run Meridian Arcade Co-op's free play nights."),
        ("Riverdelta: Print-and-Play Strategy Game",
         "An engine-building strategy game about restoring a river delta ecosystem, offered print-and-play first."),
    ],
    "film": [
        ("The Last Ferry: A Lakeport Documentary",
         "A feature documentary about the final season of the Lakeport passenger ferry and the crew who ran it."),
        ("Night Shift at the Diner: Short Film",
         "A 20-minute short filmed at the Meridian all-night diner, told across one snowy shift."),
        ("Cascadia Stories: Oral History Film Series",
         "Ten short films preserving elders' stories from towns across the Cascadia valley, screened free in libraries."),
        ("Paper Mountains: Stop-Motion Passion Project",
         "A hand-built stop-motion short about a papercraft world, three years in the making."),
    ],
    "music": [
        ("Lakeport Symphony: Instruments for Students",
         "Buying forty refurbished instruments so Lakeport middle schoolers can join orchestra without rental fees."),
        ("Meridian Sessions: Live Album at the Grain Hall",
         "Recording a live album with twelve local bands in the historic Meridian grain hall's natural reverb."),
        ("Porchfest Cascadia 2026",
         "A neighborhood porch music festival across Cascadia Heights: stages, sound gear, and street permits."),
        ("The Banjo Archive: Digitizing Old-Time Tapes",
         "Digitizing 300 reel-to-reel tapes of old-time string band music recorded around Lakeport since 1962."),
    ],
    "community": [
        ("Lakeport Tool Library Expansion",
         "Doubling the Lakeport Tool Library's inventory and adding a repair workbench open to all members."),
        ("Meridian Community Fridge Network",
         "Installing four outdoor community fridges across Meridian with weekly restocking by volunteers."),
        ("Cascadia Youth Sailing Scholarship Fund",
         "Scholarships and two refitted dinghies so any Lakeport kid can learn to sail on the lake."),
        ("Warm Winters: Coat Closet & Boot Drive",
         "Stocking the Lakeport community closet with 500 coats and waterproof boots before the cold sets in."),
        ("Greenway Pollinator Corridor",
         "Planting a mile of native pollinator gardens along the Meridian greenway with neighborhood work parties."),
    ],
    "design": [
        ("Wayfind Lakeport: Open Signage System",
         "A clear, open-licensed wayfinding signage system for downtown Lakeport, designed with local input."),
        ("The Everyday Carry Notebook, Reimagined",
         "A pocket notebook with stone paper, a lay-flat spine, and a cover pressed from recycled lake plastic."),
        ("Modular Balcony Garden Kit",
         "Flat-pack cedar planters designed in Meridian that click together to fit any apartment balcony."),
    ],
    "food": [
        ("Cascadia Grain Project: Community Mill",
         "A stone mill for the Cascadia Grain Project so local farms can sell fresh-milled flour year-round."),
        ("Lakeport Night Market: Vendor Starter Fund",
         "Stalls, lighting, and permits to launch a monthly night market for twenty local food vendors."),
        ("Second Harvest Cider: Orchard Rescue",
         "Pressing cider from unpicked backyard fruit across Meridian, with proceeds funding the gleaning crew."),
        ("The Soup Bike: Pedal-Powered Winter Meals",
         "A cargo bike soup kitchen serving hot meals on Lakeport's coldest nights, run entirely by volunteers."),
    ],
    "education": [
        ("Meridian STEM Van: Lab on Wheels",
         "A mobile science lab bringing hands-on experiments to rural schools across the Cascadia valley."),
        ("Lakeport Coding Club: Laptop Lending Library",
         "Twenty refurbished laptops so every kid in the Lakeport Coding Club can practice at home."),
    ],
}

# tier archetypes: (name, base amount, fulfillment)
TIER_SETS = [
    [("Supporter", 10, "digital"), ("Friend", 40, "physical"), ("Champion", 120, "physical")],
    [("Backer", 15, "digital"), ("Insider", 50, "digital"), ("Founder", 150, "physical")],
    [("Fan", 20, "physical"), ("Patron", 75, "physical"), ("Benefactor", 200, "physical")],
    [("Neighbor", 10, "digital"), ("Builder", 60, "physical"), ("MVP", 250, "digital")],
    [("Early Bird", 25, "digital"), ("Collector", 80, "physical"), ("Visionary", 300, "digital")],
]
TIER_DESC = {
    "digital": ["Digital thank-you pack + backer-only updates",
                "Your name on the supporters page + digital wallpaper set",
                "Behind-the-scenes digital diary + early access",
                "Backer badge + digital download of the final release"],
    "physical": ["Sticker pack + hand-written thank-you card",
                 "Signed print + your name on the thank-you wall",
                 "Limited-run tote bag + supporters page mention",
                 "Enamel pin + early access + printed postcard set"],
}

UPDATE_SNIPPETS = [
    ("First milestone reached!", "We just crossed {pct}% of our goal. Thank you, Lakeport — telling everyone at the studio tonight!"),
    ("Production update", "Quick update from the workshop: prototypes are coming along and we're on schedule. More photos next week."),
    ("Halfway there", "We're at {pct}% funded with time to spare. If you can share the campaign with one friend, it makes a real difference."),
    ("Community spotlight", "Huge thanks to the Meridian volunteers who showed up this weekend. This project belongs to all of you."),
    ("New stretch ideas", "We've been sketching what happens if we pass the goal — more on that soon. Keep the feedback coming!"),
    ("Funded — thank you!", "We made it! Every backer will get a full timeline update this week. We could not have done this without you."),
    ("Wrapping up", "The campaign has closed. Thank you to everyone who pledged and shared — updates on next steps soon."),
]


def iso(day):
    return day.isoformat()


def rand_date(rng, start, end):
    span = max((end - start).days, 1)
    return start + datetime.timedelta(days=rng.randrange(span))


def round_to(x, step):
    return int(round(x / step) * step)


def main():
    dry = "--dry-run" in sys.argv
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.row_factory = sqlite3.Row

    next_campaign = db.execute(
        "SELECT COALESCE(MAX(id),0)+1 FROM crowdfunding_donations_campaigns").fetchone()[0]
    next_user = db.execute(
        "SELECT COALESCE(MAX(id),0)+1 FROM crowdfunding_donations_users").fetchone()[0]
    next_pledge = db.execute(
        "SELECT COALESCE(MAX(id),0)+1 FROM crowdfunding_donations_pledges").fetchone()[0]
    # tier ids are globally unique across campaigns' reward_tiers JSON
    max_tier = 0
    for (tiers_json,) in db.execute(
            "SELECT reward_tiers FROM crowdfunding_donations_campaigns"):
        for t in json.loads(tiers_json or "[]"):
            max_tier = max(max_tier, int(t["id"]))
    next_tier = max_tier + 1

    existing_usernames = {r[0] for r in db.execute(
        "SELECT username FROM crowdfunding_donations_users")}

    # ---- users ----------------------------------------------------------
    n_users = 600
    combos = [(f, l) for f in FIRST for l in LAST]
    rng.shuffle(combos)
    new_users = []
    for (f, l) in combos:
        if len(new_users) >= n_users:
            break
        username = f"{f.lower()}_{l.lower()}"
        if username in existing_usernames:
            continue
        existing_usernames.add(username)
        uid = next_user
        next_user += 1
        new_users.append({
            "id": uid, "root_user_id": uid,
            "username": username,
            "password": f"{rng.choice(PW_WORDS)}{rng.choice([2024, 2025, 2025, 2026])}",
            "name": f"{f} {l}",
            "email": f"{f.lower()}.{l.lower()}@{rng.choice(MAIL)}",
            "backed": [],   # filled from pledges below
            "created": [],  # filled from campaigns below
        })

    # ---- campaigns ------------------------------------------------------
    concept_pool = [(cat, title, desc)
                    for cat, items in CONCEPTS.items()
                    for (title, desc) in items]
    rng.shuffle(concept_pool)
    n_campaigns = 32
    # status plan: 12 funded, 12 active, 5 expired, 3 cancelled
    status_plan = (["funded"] * 12 + ["active"] * 12 +
                   ["expired"] * 5 + ["cancelled"] * 3)
    rng.shuffle(status_plan)

    new_campaigns = []
    new_pledges = []
    creators = rng.sample(new_users, n_campaigns)

    for i in range(n_campaigns):
        cat, title, desc_seed = concept_pool[i]
        status = status_plan[i]
        creator = creators[i]
        cid = next_campaign
        next_campaign += 1

        duration = rng.choice([45, 60, 60, 75, 90])
        if status == "active":
            end = TODAY + datetime.timedelta(days=rng.randint(10, 70))
            start = end - datetime.timedelta(days=duration)
        else:
            # ended campaigns, dated older than / around the existing ones
            end = TODAY - datetime.timedelta(days=rng.randint(30, 700))
            start = end - datetime.timedelta(days=duration)
        pledge_end = min(end, TODAY)

        # reward tiers (fulfillment field required by the checkout flow)
        tier_set = rng.choice(TIER_SETS)
        tiers = []
        for (tname, tamount, fulfil) in tier_set:
            tiers.append({
                "id": next_tier, "name": tname,
                "amount": tamount + rng.choice([0, 0, 5]),
                "description": rng.choice(TIER_DESC[fulfil]),
                "quantity_available": 0,  # set after pledges are drawn
                "quantity_claimed": 0,
                "fulfillment": fulfil,
            })
            next_tier += 1

        # pledges: one per distinct new user; aggregates derive from these
        n_backers = rng.randint(50, 110) if status in ("expired", "cancelled") \
            else rng.randint(105, 235)
        backers = rng.sample(new_users, n_backers)
        raised = 0
        for u in backers:
            tier = rng.choices(tiers, weights=[8, 4, 1])[0]
            amount = tier["amount"]
            if rng.random() < 0.15:
                amount += rng.choice([5, 10, 15, 25])
            tier["quantity_claimed"] += 1
            raised += amount
            pid = next_pledge
            next_pledge += 1
            pdate = rand_date(rng, start, pledge_end)
            new_pledges.append({
                "id": pid, "user_id": u["id"], "campaign_id": cid,
                "amount": amount, "tier_id": tier["id"],
                "date": iso(pdate), "status": "completed",
            })
            u["backed"].append({"campaign_id": cid, "amount": amount,
                                "tier_id": tier["id"]})

        for t in tiers:
            base = max(t["quantity_claimed"] + 5, 20)
            t["quantity_available"] = rng.choice(
                [round_to(base * m, 5) for m in (1.5, 2, 3)])

        # goal consistent with status (funded <=> raised >= goal)
        if status == "funded":
            goal = round_to(raised * rng.uniform(0.72, 0.95), 500)
            goal = max(min(goal, raised), 500)
        else:
            goal = round_to(raised / rng.uniform(0.35, 0.85), 500)
            goal = max(goal, raised + 500)
        funding_model = ("flexible" if status in ("expired", "cancelled")
                         else rng.choice(["flexible", "all-or-nothing"]))

        # updates within the campaign window
        updates = []
        n_upd = rng.randint(0, 3)
        pool = UPDATE_SNIPPETS[:5] if status == "active" else list(UPDATE_SNIPPETS)
        for (utitle, ucontent) in rng.sample(pool, n_upd):
            udate = rand_date(rng, start + datetime.timedelta(days=7), pledge_end)
            updates.append({
                "date": iso(udate), "title": utitle,
                "content": ucontent.format(pct=rng.choice([30, 40, 50, 60, 75])),
            })
        updates.sort(key=lambda u: u["date"])

        description = (
            f"{desc_seed} Backed by the local community, this campaign covers "
            f"materials, permits, and the volunteer hours to make it real. "
            f"Every pledge, at any level, moves us closer — and all backers "
            f"get regular updates from the team.")

        new_campaigns.append({
            "id": cid, "title": title, "creator_id": creator["id"],
            "description": description, "category": cat,
            "goal_amount": int(goal), "raised_amount": int(raised),
            "backer_count": n_backers, "funding_model": funding_model,
            "status": status, "start_date": iso(start), "end_date": iso(end),
            "reward_tiers": json.dumps(tiers), "updates": json.dumps(updates),
        })
        creator["created"].append(cid)

    # ---- finalize user rows ---------------------------------------------
    user_rows = []
    for u in new_users:
        user_rows.append({
            "id": u["id"], "root_user_id": u["root_user_id"],
            "username": u["username"], "password": u["password"],
            "name": u["name"], "email": u["email"],
            "backed_campaigns": json.dumps(u["backed"]),
            "created_campaigns": json.dumps(u["created"]),
        })

    print(f"campaigns: +{len(new_campaigns)}")
    print(f"users:     +{len(user_rows)}")
    print(f"pledges:   +{len(new_pledges)}")
    per_campaign = {}
    for p in new_pledges:
        per_campaign[p["campaign_id"]] = per_campaign.get(p["campaign_id"], 0) + 1
    print(f"max pledges on one campaign: {max(per_campaign.values())}")
    per_user = {}
    for p in new_pledges:
        per_user[p["user_id"]] = per_user.get(p["user_id"], 0) + 1
    print(f"max pledges by one user: {max(per_user.values())}")

    if dry:
        for rows in (new_campaigns[:2], user_rows[:2], new_pledges[:3]):
            for r in rows:
                print(" ", json.dumps(r, default=str)[:200])
        return

    bdir = ROOT / "data" / "backups" / f"crowdfunding-donations-expansion-{TODAY}"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "inserted_ids.json").write_text(json.dumps({
        "campaigns": [c["id"] for c in new_campaigns],
        "users": [u["id"] for u in user_rows],
        "pledges": [p["id"] for p in new_pledges],
    }, indent=1))

    for table, rows in (("campaigns", new_campaigns),
                        ("users", user_rows),
                        ("pledges", new_pledges)):
        cols = list(rows[0].keys())
        sql = (f"INSERT INTO crowdfunding_donations_{table} "
               f"({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})")
        db.executemany(sql, [[r[c] for c in cols] for r in rows])

    # keep FTS content tables in sync
    for fts in ("fts_crowdfunding_donations_campaigns",
                "fts_crowdfunding_donations_pledges"):
        db.execute(f"INSERT INTO {fts}({fts}) VALUES('rebuild')")

    db.commit()
    print(f"inserted; rollback ids at {bdir}/inserted_ids.json")


if __name__ == "__main__":
    main()
