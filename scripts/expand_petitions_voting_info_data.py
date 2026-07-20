"""Expand petitions-voting-info base data (users, petitions, signatures, elections).

The Lakeport Civic Hub ships with only 60 rows total (9 petitions, 40
signatures, 7 users, 3 elections, 1 voter_info), which makes its
filter/sort/search macros trivial. This adds deterministic (seeded) synthetic
rows: ~160 new registered voters, ~291 new petitions (Lakeport civic topics,
existing category/status vocabulary), ~4.5k signatures attached ONLY to the
new petitions, and 6 historical completed elections.

Task-constraint guarantees (annotation tasks must keep their answers):
  * Elections rows are never touched; the School Board 2026 turnout (25.0%)
    lives in that row's own `turnout` JSON column, so new elections are inert.
  * No new petition mentions "volleyball" or "sand" (a task creates that
    petition and first verifies it does not exist).
  * Existing petitions' signatures_current values are untouched and new
    signature rows attach only to NEW petitions, so "won petitions sorted by
    signatures" keeps existing rows' values (new won petitions are allowed).
  * New petition created_at stays strictly inside the existing range
    (2025-03-01 .. 2026-02-20) so newest/oldest petitions are unchanged.

Page-render sanity: /petitions renders all petitions unpaginated -> total is
kept at 300. Petition detail renders every signature row for that petition ->
5-25 rows per new petition.

Insert-only -- existing rows are never touched. Inserted ids are recorded in
data/backups/petitions-voting-info-expansion-2026-07-20/inserted_ids.json.
After inserting, the signatures FTS index is rebuilt.

Usage: ~/.conda/envs/miniweb/bin/python scripts/expand_petitions_voting_info_data.py [--dry-run]
"""
import datetime
import json
import random
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "trimmed_miniweb.db"
BACKUP_DIR = ROOT / "data" / "backups" / "petitions-voting-info-expansion-2026-07-20"

rng = random.Random(20260720)

TODAY = datetime.date(2026, 7, 20)

# ---------------------------------------------------------------------------
# Vocabulary (reuses Lakeport / Cascadia County branding from existing rows)
# ---------------------------------------------------------------------------

FIRST_NAMES = [
    "James", "Maria", "Wei", "Aisha", "Tom", "Priya", "Grace", "Omar",
    "Hannah", "Luis", "Emily", "Marcus", "Yuki", "Fatima", "Peter", "Nina",
    "David", "Rosa", "Ken", "Amara", "Sarah", "Miguel", "Ingrid", "Jamal",
    "Chloe", "Victor", "Leah", "Andre", "Mei", "Patrick", "Dana", "Hassan",
    "Olivia", "Ray", "Tara", "Felix", "Nadia", "Colin", "Bianca", "Sanjay",
]
LAST_NAMES = [
    "Thompson", "Garcia", "Chen", "Williams", "Nakamura", "Patel", "Olsen",
    "Haddad", "Fischer", "Moreno", "Baker", "Reid", "Tanaka", "Osman",
    "Kowalski", "Petrov", "Sandoval", "Ncube", "Whitfield", "Delgado",
    "Hughes", "Ferreira", "Larsen", "Grant", "Beaumont", "Silva", "Mackey",
    "Novak", "Ibrahim", "Chandler", "Rojas", "Kaplan", "Duffy", "Onyango",
]
STREETS = [
    "Maple Ln", "Birch Ct", "Cedar Blvd", "Walnut Pl", "Main St",
    "Academic Dr", "Liberty Park Rd", "Civic Center Dr", "Oak Ave",
    "Harbor Dr", "Lakeview Ter", "Pine Ridge Rd", "Willow Ct", "Elm St",
    "Shoreline Ave", "Meridian Way",
]
PRECINCTS = ["Lakeport Precinct 1", "Lakeport Precinct 2",
             "Lakeport Precinct 3", "Lakeport Precinct 4"]
PARTIES = ["democrat", "republican", "independent"]
EMAIL_DOMAINS = ["gmail.com", "gmail.com", "outlook.com", "yahoo.com"]
INTEREST_POOL = [
    "parks", "transit", "education", "libraries", "environment", "housing",
    "small business", "public safety", "arts", "youth development",
    "cycling", "gardening", "technology", "history", "recreation",
]
BIOS = [
    "Lakeport resident who cares about {i1} and {i2}.",
    "Longtime {i1} advocate living near {street}.",
    "Parent and volunteer focused on {i1} in our community.",
    "Local {i1} enthusiast; often at the farmers market on weekends.",
    "Retired and active in neighborhood {i1} projects.",
    "New to Lakeport, excited to get involved in {i1} and {i2}.",
]

CATEGORIES = [
    "arts_and_culture", "community", "education", "environment",
    "infrastructure", "parks_and_recreation", "transportation",
]

# Per-category petition topic templates. Placeholders: {place} {street}.
# NOTE: deliberately no volleyball / sand-court topics (task constraint).
PETITION_TOPICS = {
    "parks_and_recreation": [
        ("Add Shade Structures to the {place} Playground",
         "Summer temperatures make the {place} playground unusable by midday. This petition asks Lakeport Parks & Recreation to install shade sails over the play equipment and seating areas."),
        ("Resurface the Tennis Courts at {place}",
         "The tennis courts at {place} have wide cracks and pooling water. We ask the city to resurface the courts and repaint the lines before next season."),
        ("Build a Dog Off-Leash Area in {place}",
         "Dog owners in Lakeport lack a fenced off-leash area. This petition proposes a dedicated dog run in {place} with waste stations and a small-dog section."),
        ("Extend Summer Hours at the {hood} Community Pool",
         "The {hood} pool closes at 6 PM even in July. This petition asks Parks & Recreation to extend summer hours to 8 PM on weekdays."),
        ("Install Outdoor Fitness Equipment Along the {place} Loop Trail",
         "Adding simple outdoor fitness stations along the {place} loop trail would give residents of all ages a free way to exercise."),
        ("Restore the Picnic Shelters at {place}",
         "The wooden picnic shelters at {place} are weathered and unsafe. We petition the city to restore or replace them with accessible shelters."),
        ("Add Evening Lighting to the {place} Walking Paths",
         "Poor lighting makes the walking paths at {place} feel unsafe after dusk. This petition requests energy-efficient path lighting."),
        ("Open a Skate Spot Near {street}",
         "Young skaters have nowhere legal to ride. This petition proposes a small concrete skate spot on underused city land near {street}."),
        ("Create a Disc Golf Course at {place}",
         "A nine-hole disc golf course at {place} would be a low-cost recreation amenity enjoyed by all ages."),
        ("Reopen the {place} Wading Pool",
         "The wading pool at {place} has been closed for two summers. We ask the city to fund repairs and reopen it for families."),
    ],
    "transportation": [
        ("Add a Crosswalk with Flashing Beacons at {street}",
         "Pedestrians crossing {street} face fast-moving traffic with no marked crossing. This petition requests a high-visibility crosswalk with rapid flashing beacons."),
        ("Extend Bus Route Service to the {street} Neighborhood",
         "Residents along {street} are more than a mile from the nearest bus stop. We petition Lakeport Transit to extend service to this growing neighborhood."),
        ("Lower the Speed Limit on {street} to 25 MPH",
         "Cut-through traffic on {street} regularly exceeds 35 MPH near homes and a school route. This petition asks the city to lower the limit to 25 MPH and add signage."),
        ("Install Bike Racks Downtown Near {street}",
         "Cyclists visiting downtown Lakeport have nowhere secure to lock up. This petition requests covered bike racks near {street}."),
        ("Add Speed Humps on {street}",
         "Neighbors on {street} have documented repeated speeding. We petition Public Works to install speed humps and evaluate additional traffic calming."),
        ("Improve Snow Clearing on Residential Streets Like {street}",
         "Side streets such as {street} stay icy for days after storms. This petition asks the city to expand its snow-clearing priority map."),
        ("Create a Safe Routes to School Plan for the {street} Corridor",
         "Students walking along {street} lack continuous sidewalks. We petition the city to fund a Safe Routes to School improvement plan."),
        ("Add Accessible Parking Spaces Near the {place} Entrance",
         "Visitors with mobility needs struggle to find accessible parking near {place}. This petition requests additional marked accessible spaces."),
        ("Pilot a Weekend Downtown Shuttle",
         "Parking downtown is scarce on weekends. This petition proposes a free weekend shuttle looping between the Civic Center, Main St, and the waterfront."),
        ("Fix the Potholes Along {street}",
         "The pavement on {street} has deteriorated badly, damaging cars and bikes. We petition Public Works to schedule a full repaving."),
    ],
    "environment": [
        ("Plant 500 Street Trees Along {street}",
         "Tree cover on {street} is far below the city average. This petition asks the Urban Forestry program to plant native street trees over the next two years."),
        ("Ban Single-Use Plastic Bags at Lakeport Retailers",
         "Plastic bags litter Cascadia Lake and its shoreline. This petition asks the City Council to phase out single-use plastic bags at retail checkout."),
        ("Expand Curbside Composting Citywide",
         "Curbside composting is only available in two neighborhoods. We petition the city to expand food-and-yard-waste collection to every household."),
        ("Restore Native Plantings Along the {place} Shoreline",
         "Invasive species are crowding out native plants near {place}. This petition supports a volunteer-led restoration program with city funding."),
        ("Install Water Bottle Refill Stations in Public Buildings",
         "Reducing bottled water waste starts with access. This petition requests refill stations at the Civic Center, library, and community centers."),
        ("Adopt a Dark-Sky Lighting Ordinance",
         "Unshielded lighting washes out the night sky and wastes energy. This petition asks the City Council to adopt dark-sky compliant standards for new fixtures."),
        ("Protect the {place} Wetlands from Runoff",
         "Stormwater runoff is degrading the wetlands near {place}. We petition the city to fund bioswales and runoff controls in the surrounding blocks."),
        ("Start a Community Solar Program for Lakeport Residents",
         "Many residents cannot install rooftop panels. This petition asks Lakeport Utilities to offer a community solar subscription program."),
        ("Hold a Twice-Yearly Hazardous Waste Collection Day",
         "Residents have no easy way to dispose of paint and batteries. This petition requests regular hazardous-waste collection events at the Public Works yard."),
        ("Reduce Pesticide Use at {place}",
         "This petition asks Parks & Recreation to adopt an integrated pest management policy and phase out routine pesticide spraying at {place}."),
    ],
    "education": [
        ("Fund a Full-Time Counselor at {hood} Elementary",
         "Student-to-counselor ratios in the Lakeport School District are far above recommended levels. This petition asks the School Board to fund a full-time counselor at {hood} Elementary."),
        ("Start a Dual-Language Program at {hood} Elementary",
         "Families have asked for Spanish-English dual-language instruction for years. This petition requests a pilot program at {hood} Elementary beginning in kindergarten."),
        ("Extend Weekend Hours at the {hood} Library Branch",
         "The {hood} branch closes at 5 PM on Saturdays and is closed Sundays. This petition asks the Library Board to fund weekend evening hours."),
        ("Provide Free School Meals at {hood} Elementary",
         "This petition asks the Lakeport School Board to adopt universal free breakfast and lunch at {hood} Elementary, removing stigma and paperwork barriers."),
        ("Restore the Music Program at {hood} Middle School",
         "Band and choir were cut in 2023. This petition requests the School Board restore a full-time music position at {hood} Middle School."),
        ("Create a Homework Help Center at the {hood} Library Branch",
         "Many students lack quiet study space and tutoring. This petition proposes a staffed after-school homework help center at the {hood} branch library."),
        ("Upgrade the {hood} Elementary Playground for Accessibility",
         "The playground at {hood} Elementary is not accessible to students using mobility devices. We petition the district for an inclusive redesign."),
        ("Offer Adult Evening Classes at the {hood} Community Center",
         "This petition asks the city to fund evening adult education classes -- ESL, computer skills, and financial literacy -- at the {hood} community center."),
        ("Launch a Summer Reading Bus Stop at {place}",
         "A mobile library visiting {place} each week would keep kids reading all summer. This petition asks the Library Board to add a summer reading bus stop there."),
        ("Cap Class Sizes at 24 at {hood} Elementary",
         "Crowded classrooms shortchange students. This petition asks the School Board to adopt a class-size cap of 24 for grades K-5 at {hood} Elementary."),
    ],
    "infrastructure": [
        ("Repair the Sidewalks Along {street}",
         "Buckled sidewalk panels on {street} are a tripping hazard for seniors and strollers. This petition asks Public Works to prioritize repairs."),
        ("Bring Fiber Internet to the {street} Neighborhood",
         "Households near {street} have only one slow internet option. This petition asks the city to partner on a municipal fiber buildout."),
        ("Upgrade Storm Drains on {street} to Prevent Flooding",
         "Every heavy rain floods the intersection near {street}. We petition the city to upsize the storm drains and add catch basins."),
        ("Add Public Restrooms Downtown Near {street}",
         "Downtown Lakeport has no public restrooms. This petition requests a staffed, accessible restroom facility near {street}."),
        ("Replace the Aging Water Mains Under {street}",
         "The cast-iron water mains under {street} have broken three times in two years. This petition asks Lakeport Utilities to accelerate replacement."),
        ("Bury the Overhead Utility Lines on {street}",
         "Storm-related outages hit {street} every winter. This petition asks the city to underground the utility lines during the planned repaving."),
        ("Install More Street Lighting in the {street} Area",
         "Dark blocks around {street} see more collisions and vandalism. We petition for additional LED streetlights."),
        ("Build a Covered Transit Shelter at the Civic Center Stop",
         "Riders wait in the rain at Lakeport's busiest bus stop. This petition requests a covered, lit shelter with seating at the Civic Center stop."),
        ("Modernize the {place} Community Center HVAC",
         "The community center at {place} has no air conditioning and an unreliable boiler. This petition asks the city to fund an HVAC replacement."),
        ("Add EV Charging at the {street} Public Lot",
         "This petition requests level-2 EV chargers in the public parking lot near {street}, complementing the existing solar charging proposal."),
    ],
    "community": [
        ("Start a Monthly Night Market on Main St",
         "A monthly evening market would support local vendors and bring foot traffic downtown. This petition asks the city to permit and promote a night market."),
        ("Create a Tool Lending Library at the Community Center",
         "Many residents cannot afford rarely-used tools. This petition proposes a tool lending library run from the community center."),
        ("Establish a Sister City Partnership for Lakeport",
         "This petition asks the City Council to establish a sister city partnership to promote cultural exchange and student programs."),
        ("Fund a Community Mural Series in the {street} Underpass",
         "The underpass at {street} attracts graffiti. This petition proposes commissioning local artists for a rotating mural series."),
        ("Open a Weekly Senior Social Hour at {place}",
         "Isolated seniors need low-cost social programming. This petition asks the city to host a weekly senior social hour with transportation support."),
        ("Support a Youth Jobs Program with Local Businesses",
         "This petition asks the city to match funds with local businesses for a summer youth employment program for Lakeport teens."),
        ("Allow Backyard Chickens in Residential Zones",
         "Many Cascadia County cities already allow small backyard flocks. This petition asks Lakeport to permit up to four hens per household."),
        ("Launch a Neighborhood Emergency Preparedness Network",
         "This petition asks the city to fund block-level emergency preparedness training and supply caches across all four precincts."),
        ("Keep the {place} Warming Shelter Open Year-Round",
         "The seasonal warming shelter at {place} closes in March. This petition asks the city and county to fund year-round operation."),
        ("Host a Lakeport Multicultural Festival at {place}",
         "This petition proposes an annual multicultural festival at {place} celebrating the food, music, and traditions of Lakeport's communities."),
    ],
    "arts_and_culture": [
        ("Restore the Historic {place} Bandstand",
         "The century-old bandstand at {place} is structurally unsound. This petition asks the city to restore it for summer concerts."),
        ("Fund Free Summer Concerts at {place}",
         "This petition asks the Arts Commission to fund a free Friday-evening summer concert series at {place}."),
        ("Convert the Vacant {street} Storefront into an Arts Space",
         "A city-owned storefront near {street} has sat empty for years. This petition proposes converting it into a community arts and maker space."),
        ("Add a Poet Laureate Program for Lakeport",
         "This petition asks the City Council to establish a Lakeport poet laureate to lead readings and school workshops."),
        ("Protect the Murals on the Old {street} Granary",
         "The landmark granary murals near {street} are fading. This petition requests preservation funding before the artwork is lost."),
        ("Start a Free Outdoor Movie Night Series at {place}",
         "Family movie nights at {place} would be an affordable summer tradition. This petition asks Parks & Recreation to fund a projector and licensing."),
        ("Expand the Lakeport History Museum's Open Days",
         "The history museum is open only two days a week. This petition asks the county to fund additional open days and school tours."),
        ("Commission Public Sculpture for the New Civic Plaza",
         "This petition asks the Arts Commission to dedicate one percent of the plaza budget to commissioned public sculpture by regional artists."),
        ("Create an Annual Lakeport Studio Tour Weekend",
         "This petition proposes a self-guided open-studio weekend showcasing Lakeport artists, coordinated by the Arts Commission."),
        ("Bring Back the Lakeport Winter Lights Parade",
         "The beloved winter lights parade ended in 2019. This petition asks the city and chamber of commerce to revive it."),
    ],
}

PLACES = [
    "Liberty Park", "Cascadia Lake Park", "Meridian Commons", "Riverside Green",
    "Pioneer Square Park", "Cedar Grove Park", "Northgate Park", "Heron Point",
    "Willow Bend Park", "Harborview Park",
]
NEIGHBORHOODS = [
    "Cedar Grove", "Northgate", "Willow Bend", "Harborview", "Meridian",
    "Riverside", "Pioneer", "Lakeview", "Eastshore", "Maplewood",
]

SIG_COMMENTS = [
    "Signed! This is long overdue.",
    "Happy to support this.",
    "Our neighborhood really needs this.",
    "I walk past this every day -- please fix it.",
    "Great idea, hope the council listens.",
    "Supporting for my kids' sake.",
    "This would make Lakeport so much better.",
    "About time someone organized this.",
    "Count me in. Shared with my neighbors too.",
    "As a longtime resident, I fully agree.",
    "This affects my daily commute. Signed.",
    "Small investment, big community payoff.",
    "My whole family supports this.",
    "I brought this up at a council meeting last year. Glad to see a petition.",
    "Lakeport deserves this.",
    "Signing on behalf of everyone on my block.",
    "Yes please. Let's get this done.",
    "Exactly what this part of town needs.",
    "Thank you for organizing this!",
    "Strongly support -- hope we hit the goal.",
]

REQUIRED_CHOICES = [100, 150, 200, 250, 300, 350, 400, 500, 600, 750, 1000]

# Six historical completed elections (all older than existing rows; the
# School Board 2026 turnout task reads its own row, which is untouched).
CANDIDATE_POOL = [
    "Harold Jenkins", "Beatrice Lawson", "Raymond Ortiz", "Cynthia Park",
    "Walter Higgins", "Dolores Fontaine", "Stanley Kubiak", "Irene Castillo",
    "Gordon Ashby", "Lucille Warner", "Edwin Marsh", "Paulette Nguyen",
    "Vernon Slater", "Harriet Boone", "Clifford Danner", "Rosalind Meyer",
    "Arthur Pemberton", "Gwendolyn Frost", "Leon Vargas", "Mabel Thorne",
    "Oscar Whitley", "Fern Caldwell", "Rudolph Eng", "Estelle Branch",
]

ELECTION_SPECS = [
    # (title, type, date, jurisdiction, offices, n_measures, reg_voters, turnout_pct)
    ("Lakeport City Council General Election 2023", "general_election", "2023-11-07",
     "City of Lakeport", ["City Council, District 2", "City Council, District 4", "Mayor"], 1, 31200, 54.1),
    ("Lakeport School Board General Election 2023", "general_election", "2023-11-07",
     "Lakeport School District", ["School Board, Position 1", "School Board, Position 3"], 1, 31450, 48.7),
    ("Cascadia County General Election 2024", "general_election", "2024-11-05",
     "Cascadia County", ["County Commissioner, District 1", "County Assessor", "Sheriff"], 2, 31900, 71.3),
    ("Lakeport City Council Primary Election 2024", "primary_election", "2024-08-06",
     "City of Lakeport", ["City Council, District 2", "City Council, District 4"], 0, 31700, 32.4),
    ("Lakeport Special Election - Fire District Levy 2024", "special_election", "2024-02-13",
     "Lakeport Fire Protection District", [], 1, 31500, 28.9),
    ("Lakeport City Council General Election 2021", "general_election", "2021-11-02",
     "City of Lakeport", ["City Council, District 1", "City Council, District 3", "City Council, District 5"], 1, 29800, 51.8),
]

MEASURE_TOPICS = [
    ("Street Maintenance Levy", "Authorizes a six-year property tax levy of $0.20 per $1,000 of assessed value dedicated to residential street repaving and sidewalk repair.", "$2.1 million"),
    ("Library Operations Levy", "Renews the existing levy supporting Lakeport Public Library operating hours, collections, and youth programs.", "$1.4 million"),
    ("Fire and EMS Levy Lid Lift", "Restores the fire district levy rate to $1.50 per $1,000 of assessed value to maintain staffing and replace aging apparatus.", "$3.6 million"),
    ("Affordable Housing Sales Tax", "Enacts a 0.1% sales tax to fund construction and preservation of affordable housing units in Lakeport.", "$2.8 million"),
    ("Public Safety Technology Bond", "Authorizes $12 million in bonds to modernize emergency dispatch and radio infrastructure countywide.", "$1.1 million"),
]


def iso_dt(day, hour, minute):
    return "%sT%02d:%02d:00Z" % (day.isoformat(), hour, minute)


def rand_day(rng, start, end):
    span = (end - start).days
    return start + datetime.timedelta(days=rng.randrange(max(span, 1)))


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def build_users(existing_usernames, start_id, n=160):
    users = []
    seen = set(existing_usernames)
    combos = [(f, l) for f in FIRST_NAMES for l in LAST_NAMES]
    rng.shuffle(combos)
    uid = start_id
    for f, l in combos:
        if len(users) >= n:
            break
        username = ("%s_%s" % (f, l)).lower()
        if username in seen:
            continue
        seen.add(username)
        display = "%s %s" % (f, l)
        street = rng.choice(STREETS)
        i1, i2 = rng.sample(INTEREST_POOL, 2)
        bio = rng.choice(BIOS).format(i1=i1, i2=i2, street=street)
        reg_year = rng.randint(1996, 2025)
        reg_date = datetime.date(reg_year, rng.randint(1, 12), rng.randint(1, 28))
        users.append({
            "id": uid,
            "root_user_id": 0,
            "username": username,
            "display_name": display,
            "email": "%s.%s@%s" % (f.lower(), l.lower(), rng.choice(EMAIL_DOMAINS)),
            "voter_registration_status": "active" if rng.random() < 0.92 else "inactive",
            "registered_address": "%d %s, Lakeport, WA 98401" % (rng.randint(100, 4999), street),
            "precinct": rng.choice(PRECINCTS),
            "party_affiliation": rng.choice(PARTIES),
            "registration_date": reg_date.isoformat(),
            "profile": json.dumps({"bio": bio, "interests": [i1, i2]}),
        })
        uid += 1
    return users


def build_petitions(all_users, start_id, n=291):
    """New petitions dated strictly inside 2025-03-02 .. 2026-02-19 so the
    oldest (2025-03-01) and newest (2026-02-20) existing petitions keep their
    extremum positions."""
    lo = datetime.date(2025, 3, 2)
    hi = datetime.date(2026, 2, 19)

    # Enumerate every unique (template x place/street/neighborhood) title
    # variant per category, then shuffle -- deterministic, no retry loops.
    variants = {}
    for cat in CATEGORIES:
        cat_variants = []
        for title_tpl, desc_tpl in PETITION_TOPICS[cat]:
            if "{place}" in title_tpl:
                opts = [{"place": p} for p in PLACES]
            elif "{street}" in title_tpl:
                opts = [{"street": s} for s in STREETS]
            elif "{hood}" in title_tpl:
                opts = [{"hood": h} for h in NEIGHBORHOODS]
            else:
                opts = [{}]
            for kw in opts:
                kw = dict(kw)
                kw.setdefault("place", rng.choice(PLACES))
                kw.setdefault("street", rng.choice(STREETS))
                kw.setdefault("hood", rng.choice(NEIGHBORHOODS))
                cat_variants.append((title_tpl.format(**kw), desc_tpl.format(**kw)))
        rng.shuffle(cat_variants)
        variants[cat] = cat_variants

    petitions = []
    titles_seen = set()
    pid = start_id
    i = 0
    while len(petitions) < n:
        if not any(variants.values()):
            raise RuntimeError("ran out of unique petition titles at %d" % len(petitions))
        cat = CATEGORIES[i % len(CATEGORIES)]
        i += 1
        if not variants[cat]:
            continue
        title, desc = variants[cat].pop()
        if title in titles_seen:
            continue
        titles_seen.add(title)
        assert "volleyball" not in title.lower() and "volleyball" not in desc.lower()
        assert "sand" not in title.lower() and "sand " not in desc.lower()

        creator = rng.choice(all_users)
        created = rand_day(rng, lo, hi)
        created_at = iso_dt(created, rng.randint(7, 20), rng.choice([0, 15, 30, 45]))
        required = rng.choice(REQUIRED_CHOICES)
        # ~40% won, ~60% active
        won = rng.random() < 0.40
        if won:
            status = "won"
            current = required + rng.randint(0, max(5, required // 8))
            deadline_day = min(created + datetime.timedelta(days=rng.choice([120, 150, 180])),
                               TODAY + datetime.timedelta(days=rng.randint(10, 200)))
        else:
            status = "active"
            current = rng.randint(max(3, required // 20), required - rng.randint(1, max(2, required // 10)))
            deadline_day = TODAY + datetime.timedelta(days=rng.randint(15, 400))
        tag_words = [w.strip(",.").lower().replace("'s", "") for w in title.split()
                     if len(w) > 4 and w[0].isupper() and w.lower() not in ("lakeport",)]
        tags = list(dict.fromkeys([cat.split("_")[0]] + tag_words[:3]))
        petitions.append({
            "id": pid,
            "title": title,
            "creator_id": creator["id"],
            "creator_name": creator["display_name"],
            "description": desc,
            "category": cat,
            "signatures_required": required,
            "signatures_current": current,
            "status": status,
            "created_at": created_at,
            "deadline": "%sT23:59:59Z" % deadline_day.isoformat(),
            "tags": json.dumps(tags),
            "related_links": json.dumps({}),
        })
        pid += 1
    return petitions


def build_signatures(new_petitions, all_users, start_id, target=4540):
    """Signatures attach ONLY to new petitions (task constraint: existing
    petitions' signature data must not change)."""
    sigs = []
    sid = start_id
    per = max(3, target // len(new_petitions))
    for p in new_petitions:
        created = datetime.date.fromisoformat(p["created_at"][:10])
        deadline = datetime.date.fromisoformat(p["deadline"][:10])
        end = min(deadline, TODAY - datetime.timedelta(days=1))
        if end <= created:
            end = created + datetime.timedelta(days=1)
        n = rng.randint(max(3, per - 8), per + 9)
        signers = rng.sample(all_users, min(n, len(all_users)))
        days = sorted(rng.randint(0, max((end - created).days, 1)) for _ in signers)
        for signer, day_off in zip(signers, days):
            day = created + datetime.timedelta(days=day_off)
            comment = rng.choice(SIG_COMMENTS) if rng.random() < 0.35 else ""
            sigs.append({
                "id": sid,
                "petition_id": p["id"],
                "user_id": signer["id"],
                "user_name": signer["display_name"],
                "signed_at": iso_dt(day, rng.randint(6, 22), rng.choice([0, 5, 10, 20, 30, 40, 50, 55])),
                "comment": comment,
            })
            sid += 1
    return sigs


def build_elections(start_id):
    elections = []
    eid = start_id
    pool = list(CANDIDATE_POOL)
    rng.shuffle(pool)
    ci = 0

    def next_candidate():
        nonlocal ci
        name = pool[ci % len(pool)]
        ci += 1
        return name

    mi = 0
    for title, etype, date_s, jur, offices, n_measures, reg, pct in ELECTION_SPECS:
        votes_cast = int(round(reg * pct / 100.0))
        races = []
        for ri, office in enumerate(offices, start=1):
            n_cand = rng.choice([2, 2, 3])
            total = int(votes_cast * rng.uniform(0.82, 0.97))
            shares = sorted([rng.uniform(0.35, 0.6)] + [rng.uniform(0.1, 0.4) for _ in range(n_cand - 1)], reverse=True)
            norm = sum(shares)
            cands = []
            for j in range(n_cand):
                cands.append({
                    "name": next_candidate(),
                    "party": "nonpartisan",
                    "incumbent": (j == 0 and rng.random() < 0.5),
                    "votes": int(total * shares[j] / norm),
                    "result": "won" if j == 0 else "lost",
                })
            races.append({"id": "race_%d%02d" % (eid, ri), "office": office, "candidates": cands})
        measures = []
        for k in range(n_measures):
            mname, mdesc, mrev = MEASURE_TOPICS[mi % len(MEASURE_TOPICS)]
            mi += 1
            yes = int(votes_cast * rng.uniform(0.42, 0.62))
            no = int(votes_cast * rng.uniform(0.30, 0.50))
            measures.append({
                "id": "measure_%d%02d" % (eid, k + 1),
                "title": "Measure %s: %s" % (chr(ord("A") + k), mname),
                "description": mdesc,
                "estimated_annual_revenue": mrev,
                "votes_yes": yes,
                "votes_no": no,
                "result": "passed" if yes > no else "failed",
                "effective_date": "%d-01-01" % (int(date_s[:4]) + 1),
            })
        elections.append({
            "id": eid,
            "title": title,
            "type": etype,
            "date": date_s,
            "status": "completed",
            "jurisdiction": jur,
            "description": "%s held in %s for %s." % (
                etype.replace("_", " ").capitalize(), date_s[:4], jur),
            "races": json.dumps(races),
            "ballot_measures": json.dumps(measures),
            "turnout": json.dumps({"registered_voters": reg, "votes_cast": votes_cast,
                                   "turnout_percentage": pct}),
        })
        eid += 1
    return elections


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    dry = "--dry-run" in sys.argv
    con = sqlite3.connect(DB_PATH, timeout=60)
    con.row_factory = sqlite3.Row

    existing_users = [dict(r) for r in con.execute(
        "SELECT * FROM petitions_voting_info_users ORDER BY id")]
    next_uid = con.execute("SELECT COALESCE(MAX(id),0)+1 FROM petitions_voting_info_users").fetchone()[0]
    next_pid = con.execute("SELECT COALESCE(MAX(id),0)+1 FROM petitions_voting_info_petitions").fetchone()[0]
    next_sid = con.execute("SELECT COALESCE(MAX(id),0)+1 FROM petitions_voting_info_signatures").fetchone()[0]
    next_eid = con.execute("SELECT COALESCE(MAX(id),0)+1 FROM petitions_voting_info_elections").fetchone()[0]

    users = build_users({u["username"] for u in existing_users}, next_uid)
    all_users = existing_users + [
        {"id": u["id"], "display_name": u["display_name"]} for u in users]
    petitions = build_petitions(all_users, next_pid)
    signatures = build_signatures(petitions, all_users, next_sid)
    elections = build_elections(next_eid)

    # Safety: no volleyball/sand anywhere, no touching existing ids
    blob = json.dumps(petitions).lower()
    assert "volleyball" not in blob and "sand court" not in blob and '"sand' not in blob
    assert all(s["petition_id"] >= next_pid for s in signatures)

    print("Would insert" if dry else "Inserting")
    print("  users:      %d (ids %d..%d)" % (len(users), users[0]["id"], users[-1]["id"]))
    print("  petitions:  %d (ids %d..%d)" % (len(petitions), petitions[0]["id"], petitions[-1]["id"]))
    print("  signatures: %d (ids %d..%d)" % (len(signatures), signatures[0]["id"], signatures[-1]["id"]))
    print("  elections:  %d (ids %d..%d)" % (len(elections), elections[0]["id"], elections[-1]["id"]))
    won = sum(1 for p in petitions if p["status"] == "won")
    print("  petition statuses: %d won / %d active" % (won, len(petitions) - won))
    max_sigs = max(sum(1 for s in signatures if s["petition_id"] == p["id"]) for p in petitions)
    print("  max signature rows per petition: %d" % max_sigs)

    if dry:
        print("\n-- dry run, sample petition --")
        print(json.dumps(petitions[0], indent=2))
        print("-- sample user --")
        print(json.dumps(users[0], indent=2))
        print("-- sample signature --")
        print(json.dumps(signatures[0], indent=2))
        print("-- sample election (truncated) --")
        e = dict(elections[0]); e["races"] = e["races"][:120] + "..."
        print(json.dumps(e, indent=2)[:1200])
        con.close()
        return

    def insert(table, rows):
        cols = list(rows[0].keys())
        sql = "INSERT INTO petitions_voting_info_%s (%s) VALUES (%s)" % (
            table, ",".join("[%s]" % c for c in cols), ",".join("?" * len(cols)))
        con.executemany(sql, [tuple(r[c] for c in cols) for r in rows])

    with con:
        insert("users", users)
        insert("petitions", petitions)
        insert("signatures", signatures)
        insert("elections", elections)
        con.execute("INSERT INTO fts_petitions_voting_info_signatures"
                    "(fts_petitions_voting_info_signatures) VALUES('rebuild')")

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup = {
        "site": "petitions-voting-info",
        "date": "2026-07-20",
        "inserted": {
            "users": [u["id"] for u in users],
            "petitions": [p["id"] for p in petitions],
            "signatures": [signatures[0]["id"], signatures[-1]["id"], "range-inclusive"],
            "elections": [e["id"] for e in elections],
        },
    }
    (BACKUP_DIR / "inserted_ids.json").write_text(json.dumps(backup, indent=2))
    print("Backup written to %s" % (BACKUP_DIR / "inserted_ids.json"))

    for t in ("users", "petitions", "signatures", "elections", "voter_info"):
        print("  %-12s %d" % (t, con.execute(
            "SELECT COUNT(*) FROM petitions_voting_info_%s" % t).fetchone()[0]))
    con.close()


if __name__ == "__main__":
    main()
