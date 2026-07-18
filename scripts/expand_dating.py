"""Expand dating: realistic population + repair data inconsistencies.

- Backs up the four dating_* tables to data/backups/ before touching anything.
- Adds joined_date/lat/lng columns to dating_users (needed by the Spark
  "Joined From/To" filter, "Newest" sort, and the proximity filter/sort).
- Existing 8 users: fills joined_date (consistent with their first like
  activity), coordinates, fresh last_active, and working avatar paths
  (the seeded /static/profiles/*.jpg files never existed).
- Adds 60 new profiles (ids 9-68) across 7 towns around Lakeport, WA with
  distinct handwritten bios, varied ages/genders/orientations.
- Backfills conversations for matches 4-7 (their notes referenced messages
  that were never seeded) and adds 9 new matches with conversations.
- Adds pending/passed/matched likes so the Likes You page and discover deck
  have depth for every seeded account.
- Generates SVG avatars for all users into sites/dating/static/profiles/.
- Rebuilds the external-content FTS tables (they have no sync triggers).
- Idempotent-ish: refuses to run if dating_users already has >8 rows.
"""
import pathlib
import sqlite3
import json
import random
from datetime import datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "trimmed_miniweb.db"
AVATAR_DIR = ROOT / "sites" / "dating" / "static" / "profiles"

db = sqlite3.connect(DB)
rng = random.Random(20260717)

n_users = db.execute("SELECT COUNT(*) FROM dating_users").fetchone()[0]
if n_users > 8:
    raise SystemExit(f"dating_users already has {n_users} rows — refusing to re-run.")

# ── backup ───────────────────────────────────────────────────────────────────
backup_dir = ROOT / "data" / "backups"
backup_dir.mkdir(parents=True, exist_ok=True)
stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
backup_path = backup_dir / f"dating-pre-expand-{stamp}.sql"
with open(backup_path, "w") as f:
    for line in db.iterdump():
        if "dating_" in line:
            f.write(line + "\n")
print("backup:", backup_path)

# ── new columns ──────────────────────────────────────────────────────────────
existing_cols = {r[1] for r in db.execute("PRAGMA table_info(dating_users)")}
for col, decl in [("joined_date", "TEXT NOT NULL DEFAULT ''"),
                  ("lat", "REAL"), ("lng", "REAL")]:
    if col not in existing_cols:
        db.execute(f"ALTER TABLE dating_users ADD COLUMN {col} {decl}")
        print("added column", col)

# ── geography ────────────────────────────────────────────────────────────────
CITIES = {
    "Lakeport, WA":       (47.98, -122.20),
    "Cedar Falls, WA":    (48.10, -122.35),
    "Harbor Springs, WA": (47.85, -122.40),
    "Eastbrook, WA":      (47.95, -121.95),
    "Millhaven, WA":      (48.25, -122.10),
    "Pinecrest, WA":      (47.70, -122.05),
    "Silverton, WA":      (48.45, -122.55),
}

def coords(city):
    lat, lng = CITIES[city]
    return round(lat + rng.uniform(-0.03, 0.03), 4), round(lng + rng.uniform(-0.04, 0.04), 4)

# ── existing 8: joined_date, coords, fresh last_active, working avatars ──────
EXISTING = {
    1: ("alex_r",    "2025-09-14", "2026-07-16T20:15:00"),
    2: ("mia_t",     "2025-08-30", "2026-07-16T19:40:00"),
    3: ("olivia_j",  "2025-11-19", "2026-07-15T22:10:00"),
    4: ("sophie_l",  "2025-10-05", "2026-07-16T18:30:00"),
    5: ("daniel_o",  "2025-09-21", "2026-07-16T21:00:00"),
    6: ("natalie_k", "2025-11-08", "2026-07-16T23:45:00"),
    7: ("nathan_b",  "2026-01-15", "2026-07-16T07:15:00"),
    8: ("rachel_k",  "2025-12-10", "2026-07-15T16:20:00"),
}
for uid, (username, joined, last_active) in EXISTING.items():
    lat, lng = coords("Lakeport, WA")
    db.execute(
        "UPDATE dating_users SET joined_date=?, last_active=?, lat=?, lng=?, photos=? WHERE id=?",
        (joined + "T12:00:00", last_active, lat, lng,
         json.dumps([f"/sites/dating/static/profiles/{username}.svg"]), uid))

# ── 60 new profiles ──────────────────────────────────────────────────────────
# (username, name, age, gender, city, bio, interests, looking_for,
#  gender_pref, min_age, max_age, max_dist, verified, joined, last_active_day)
NEW_USERS = [
 ("jade_m", "Jade Morales", 27, "female", "Lakeport, WA",
  "ER nurse on nights, which means my weekends are Tuesdays. Best gnocchi in three counties, fight me. Looking for someone who doesn't flinch at a 3am breakfast date.",
  ["cooking", "true crime podcasts", "kayaking", "thrifting"], "relationship", "male", 25, 36, 40, 1, "2025-06-11", "2026-07-16"),
 ("tom_h", "Tomás Herrera", 31, "male", "Lakeport, WA",
  "High school chemistry teacher and weekend soccer referee. I make terrible puns and excellent paella. My students say I'm 'mid' which I'm told is almost a compliment.",
  ["soccer", "cooking", "board games", "hiking"], "relationship", "female", 25, 35, 30, 1, "2025-03-22", "2026-07-15"),
 ("priya_s", "Priya Shah", 29, "female", "Eastbrook, WA",
  "Product designer who left Seattle for a house with an actual yard. Learning to keep plants alive, currently 4 for 11. Sunday farmers market is non-negotiable.",
  ["gardening", "design", "yoga", "farmers markets", "reading"], "relationship", "any", 26, 38, 25, 1, "2025-08-02", "2026-07-16"),
 ("marcus_w", "Marcus Webb", 34, "male", "Harbor Springs, WA",
  "Marine mechanic with my own shop. If your boat breaks down, we've probably met. Big on crabbing season, small on drama.",
  ["fishing", "boats", "BBQ", "classic rock"], "relationship", "female", 27, 40, 35, 1, "2024-11-15", "2026-07-14"),
 ("elena_v", "Elena Volkov", 26, "female", "Lakeport, WA",
  "Barista by day, ceramicist by night. My apartment is 60% mugs. Will absolutely judge your coffee order and then buy you a better one.",
  ["pottery", "coffee", "indie music", "film photography"], "casual", "any", 22, 34, 20, 1, "2025-12-05", "2026-07-17"),
 ("derek_c", "Derek Chen", 29, "male", "Lakeport, WA",
  "Data analyst who spends his salary on climbing gear and concert tickets. 5.11 on a good day. Looking for a belay partner in every sense.",
  ["climbing", "live music", "coding side projects", "coffee"], "relationship", "female", 24, 33, 45, 1, "2025-05-19", "2026-07-16"),
 ("amara_o", "Amara Okafor", 32, "female", "Cedar Falls, WA",
  "Pediatric PT and part-time salsa instructor. Yes I will make you dance, no you won't be good at it at first, yes you'll love it anyway.",
  ["dancing", "fitness", "travel", "cooking"], "relationship", "male", 28, 42, 30, 1, "2025-02-14", "2026-07-15"),
 ("sam_t", "Sam Torres", 24, "nonbinary", "Lakeport, WA",
  "Bookseller at the indie shop downtown. I will build you a personalized reading list on the second date. They/them.",
  ["books", "zines", "cats", "vinyl records", "baking"], "casual", "any", 21, 32, 15, 1, "2026-01-30", "2026-07-16"),
 ("kevin_p", "Kevin Park", 36, "male", "Millhaven, WA",
  "Firefighter, dad to a golden retriever named Biscuit, amateur woodworker. My table wobbles but my intentions don't.",
  ["woodworking", "dogs", "hiking", "grilling"], "relationship", "female", 28, 42, 40, 1, "2024-09-08", "2026-07-13"),
 ("lucy_g", "Lucy Grant", 30, "female", "Pinecrest, WA",
  "Environmental consultant who counts salmon for a living (really). I own more rain jackets than dresses and I'm at peace with that.",
  ["birdwatching", "hiking", "craft beer", "camping"], "relationship", "male", 27, 38, 50, 1, "2025-04-27", "2026-07-16"),
 ("andre_b", "André Boucher", 28, "male", "Lakeport, WA",
  "Pastry chef at Harborview Grill. I smell like butter and I'm done apologizing for it. Seeking someone to taste-test at 6am.",
  ["baking", "food trucks", "cycling", "jazz"], "casual", "any", 23, 35, 25, 1, "2025-10-12", "2026-07-17"),
 ("nina_r", "Nina Rossi", 33, "female", "Harbor Springs, WA",
  "Real estate agent who can tell you what your date's house is worth from the driveway. Competitive trivia team captain. We're called the Quizzly Bears.",
  ["trivia", "wine tasting", "running", "podcasts"], "relationship", "male", 30, 45, 30, 1, "2024-12-01", "2026-07-15"),
 ("jamal_e", "Jamal Edwards", 27, "male", "Lakeport, WA",
  "Radio DJ for the local station, so yes, my voice sounds like this in person. Record collection is at 800 and climbing. Send me your top 5 albums.",
  ["vinyl records", "live music", "basketball", "thrifting"], "casual", "female", 22, 32, 20, 1, "2026-02-18", "2026-07-16"),
 ("harper_l", "Harper Lin", 25, "female", "Eastbrook, WA",
  "Vet school survivor, now junior vet at the Eastbrook clinic. I've been peed on by every species you can name. Dark humor required.",
  ["animals", "hiking", "horror movies", "bubble tea"], "relationship", "any", 23, 33, 35, 1, "2025-11-23", "2026-07-17"),
 ("owen_d", "Owen Delacroix", 38, "male", "Silverton, WA",
  "Winemaker at a small Silverton vineyard. Divorced, no kids, one very opinionated cat. I promise not to talk about tannins on the first date. Second date, no promises.",
  ["wine tasting", "cooking", "reading", "gardening"], "relationship", "female", 30, 45, 60, 1, "2024-08-19", "2026-07-12"),
 ("zoe_k", "Zoe Kaminski", 23, "female", "Lakeport, WA",
  "Grad student in marine biology. Ask me about octopuses. No really, ask me. I have slides.",
  ["scuba diving", "octopuses", "gaming", "anime"], "casual", "any", 21, 29, 25, 0, "2026-03-14", "2026-07-17"),
 ("victor_m", "Victor Mendez", 41, "male", "Millhaven, WA",
  "Contractor who builds custom homes and terrible jokes. Two kids, week on week off. Honest about all of it up front.",
  ["woodworking", "fishing", "classic cars", "BBQ"], "relationship", "female", 32, 46, 35, 1, "2025-01-10", "2026-07-14"),
 ("faith_a", "Faith Adeyemi", 29, "female", "Cedar Falls, WA",
  "Pharmacist with a secret: I write romance novels under a pen name you will never guess. Plot ideas welcome.",
  ["writing", "reading", "baking", "true crime podcasts"], "relationship", "male", 27, 38, 30, 1, "2025-07-07", "2026-07-16"),
 ("cole_n", "Cole Novak", 26, "male", "Lakeport, WA",
  "Ski patrol in winter, raft guide in summer, unemployed and thriving in between. My couch is a hammock. Adventure buddy wanted.",
  ["skiing", "rafting", "camping", "slacklining"], "casual", "any", 21, 32, 50, 0, "2025-09-30", "2026-07-16"),
 ("iris_w", "Iris Whitfield", 35, "female", "Lakeport, WA",
  "Architect restoring Lakeport's old cannery building. I notice doorframes on dates. It's a problem. Tell me about your favorite building.",
  ["architecture", "sketching", "cycling", "museums"], "relationship", "male", 30, 44, 25, 1, "2024-10-25", "2026-07-15"),
 ("dmitri_s", "Dmitri Sokolov", 30, "male", "Eastbrook, WA",
  "Physical therapist and former semi-pro volleyball player. My knees are shot but my serve isn't. Beach league every Thursday.",
  ["volleyball", "fitness", "cooking", "travel"], "relationship", "female", 25, 36, 30, 1, "2025-06-28", "2026-07-16"),
 ("penny_h", "Penny Huang", 28, "female", "Lakeport, WA",
  "Food truck owner (Dumpling Cart on 5th, come say hi). I work weekends so Tuesday is my Friday. First date suggestion: I cook, you talk.",
  ["cooking", "food trucks", "hiking", "k-dramas"], "relationship", "male", 23, 36, 20, 1, "2025-05-05", "2026-07-17"),
 ("gus_f", "Gus Fitzgerald", 44, "male", "Harbor Springs, WA",
  "Ferry captain, 20 years on the water. Widower, slowly figuring out chapter two. My daughter set up this profile and she says hi.",
  ["boats", "history", "chess", "cooking"], "relationship", "female", 35, 50, 40, 1, "2025-03-08", "2026-07-13"),
 ("mabel_j", "Mabel Johnson", 39, "female", "Millhaven, WA",
  "Owner of Millhaven's only yarn shop. Yes, knitting is cool now, I checked. Two teenagers, one ex, zero patience for games.",
  ["knitting", "reading", "gardening", "community events"], "relationship", "male", 35, 50, 30, 1, "2024-07-14", "2026-07-15"),
 ("theo_r", "Theo Reyes", 25, "male", "Lakeport, WA",
  "Junior firefighter and volunteer EMT. I can cook exactly three meals but all three are fantastic. Gym at 5am, asleep by 10.",
  ["fitness", "basketball", "meal prep", "dogs"], "relationship", "female", 22, 30, 25, 1, "2026-01-08", "2026-07-16"),
 ("clara_b", "Clara Beaumont", 31, "female", "Silverton, WA",
  "High school art teacher who paints murals in summer. You've probably walked past two of mine. Paint under my nails is permanent, deal with it.",
  ["painting", "murals", "thrifting", "indie music"], "relationship", "any", 26, 40, 45, 1, "2025-02-27", "2026-07-16"),
 ("ray_v", "Ray Valdez", 33, "male", "Pinecrest, WA",
  "Park ranger at Pinecrest State Park. I know where the good views are and I'm willing to share. Leave no trace, except on my heart apparently.",
  ["hiking", "birdwatching", "photography", "camping"], "relationship", "female", 27, 40, 60, 1, "2024-06-20", "2026-07-16"),
 ("suki_t", "Suki Tanaka", 27, "female", "Lakeport, WA",
  "UX researcher, competitive Mario Kart player, aggressive brunch defender. My love language is sending you memes at 2am.",
  ["gaming", "brunch", "cycling", "design"], "casual", "any", 23, 33, 20, 1, "2025-08-25", "2026-07-17"),
 ("bruno_m", "Bruno Marchetti", 37, "male", "Lakeport, WA",
  "Owner of Marchetti's Deli, third generation. I will feed you until you can't move. Nonna approves of this app, somehow.",
  ["cooking", "soccer", "wine tasting", "family"], "relationship", "female", 28, 42, 25, 1, "2024-05-30", "2026-07-15"),
 ("wren_c", "Wren Callahan", 24, "nonbinary", "Cedar Falls, WA",
  "Tattoo apprentice and botanical illustrator. My flash sheets are all native plants. Will trade a sketch for a good hike recommendation. They/them.",
  ["tattoos", "illustration", "plants", "hiking"], "casual", "any", 21, 32, 30, 0, "2026-02-02", "2026-07-16"),
 ("hank_o", "Hank Olsen", 52, "male", "Harbor Springs, WA",
  "Retired Coast Guard, now I fix up old sailboats and sell them for less than they're worth. Looking for a first mate who likes slow mornings.",
  ["sailing", "woodworking", "history", "fishing"], "relationship", "female", 42, 58, 40, 1, "2024-04-12", "2026-07-11"),
 ("dora_e", "Dora Espinoza", 45, "female", "Lakeport, WA",
  "City council member and weekend beekeeper. Yes, politics AND bees — I like things with a sting. Empty nester, full calendar, open heart.",
  ["beekeeping", "community events", "reading", "gardening"], "relationship", "male", 40, 55, 30, 1, "2024-08-03", "2026-07-14"),
 ("felix_g", "Felix Gruber", 29, "male", "Lakeport, WA",
  "Brewery quality engineer. I taste beer for a living and still drink coffee like it's a personality. Bouldering three nights a week.",
  ["craft beer", "climbing", "coffee", "board games"], "casual", "any", 24, 34, 25, 1, "2025-07-21", "2026-07-17"),
 ("june_p", "June Park", 34, "female", "Eastbrook, WA",
  "Physician assistant, marathoner, aunt of the year four years running. Training for Boston. If you bike alongside me handing up snacks, that's a date.",
  ["running", "fitness", "meal prep", "podcasts"], "relationship", "male", 30, 42, 35, 1, "2025-01-25", "2026-07-16"),
 ("oscar_h", "Oscar Hidalgo", 26, "male", "Lakeport, WA",
  "Sound engineer at the Lakeport Amphitheater. I've mixed for bands you like and bands you pretend to like. Tinnitus and good taste included.",
  ["live music", "vinyl records", "synthesizers", "skateboarding"], "casual", "female", 22, 31, 20, 0, "2025-12-19", "2026-07-17"),
 ("greta_s", "Greta Svensson", 30, "female", "Millhaven, WA",
  "Large animal vet. I've got a truck full of mud and a heart full of love for anything with hooves. City people, I will convert you.",
  ["horses", "animals", "camping", "country music"], "relationship", "male", 27, 40, 50, 1, "2025-04-09", "2026-07-15"),
 ("leo_a", "Leo Antonelli", 28, "male", "Lakeport, WA",
  "Librarian at the Lakeport branch (Rachel's colleague, small world). Fluent in Dewey Decimal and dad jokes despite not being a dad.",
  ["books", "board games", "local history", "cycling"], "relationship", "female", 24, 36, 25, 1, "2025-10-01", "2026-07-16"),
 ("tess_d", "Tess Donovan", 26, "female", "Lakeport, WA",
  "Rock climbing gym manager. I will absolutely use 'let's climb sometime' as a first date and I will absolutely spot you.",
  ["climbing", "slacklining", "van life", "coffee"], "casual", "any", 22, 32, 30, 1, "2025-11-11", "2026-07-17"),
 ("raj_k", "Raj Kapoor", 32, "male", "Eastbrook, WA",
  "Software engineer, amateur astrophotographer. My best photo of Saturn took 14 hours and my mom thinks it's a sticker. Stargazing dates are my whole thing.",
  ["astronomy", "photography", "coding side projects", "hiking"], "relationship", "female", 26, 36, 40, 1, "2025-03-17", "2026-07-16"),
 ("ivy_m", "Ivy Moreau", 28, "female", "Harbor Springs, WA",
  "Oyster farmer. My hands are always cold and my stories are always good. The sunrise commute by boat never gets old.",
  ["boats", "cooking", "cold plunges", "documentaries"], "relationship", "any", 25, 38, 35, 1, "2025-06-04", "2026-07-15"),
 ("stan_w", "Stan Wozniak", 48, "male", "Lakeport, WA",
  "High school football coach, 22 seasons. Divorced, two kids in college. I do crosswords in pen because life's short.",
  ["football", "crosswords", "grilling", "history"], "relationship", "female", 38, 52, 30, 1, "2024-09-27", "2026-07-13"),
 ("mira_n", "Mira Nassar", 27, "female", "Lakeport, WA",
  "Dental hygienist with the steadiest hands in town. I do stand-up on open mic nights. Yes, teeth jokes. No, I won't stop.",
  ["stand-up comedy", "yoga", "brunch", "travel"], "relationship", "male", 25, 35, 25, 1, "2025-09-09", "2026-07-17"),
 ("ezra_f", "Ezra Feldman", 31, "male", "Cedar Falls, WA",
  "Documentary filmmaker between projects, which is film-speak for 'I also do weddings.' Currently obsessed with the Cedar Falls logging archives.",
  ["filmmaking", "documentaries", "hiking", "coffee"], "casual", "any", 25, 38, 35, 0, "2025-08-15", "2026-07-16"),
 ("carmen_r", "Carmen Ruiz", 36, "female", "Pinecrest, WA",
  "Small-batch hot sauce maker (Carmen's Inferno — it's in three stores now!). Spice tolerance is not required but is appreciated.",
  ["cooking", "salsa dancing", "farmers markets", "gardening"], "relationship", "male", 30, 45, 40, 1, "2024-12-20", "2026-07-15"),
 ("finn_b", "Finn Byrne", 24, "male", "Lakeport, WA",
  "Bike messenger and bike mechanic — if it has two wheels I've crashed it and fixed it. Training for the Lakeport Gran Fondo.",
  ["cycling", "craft beer", "punk shows", "camping"], "casual", "any", 21, 29, 20, 0, "2026-04-05", "2026-07-17"),
 ("opal_t", "Opal Thompson", 42, "female", "Silverton, WA",
  "Glassblower with a studio in the Silverton arts district. First date idea: watch me make you something at 2000 degrees.",
  ["glassblowing", "art galleries", "wine tasting", "hiking"], "relationship", "any", 35, 50, 50, 1, "2024-11-02", "2026-07-14"),
 ("diego_l", "Diego Luna", 29, "male", "Lakeport, WA",
  "Elementary school music teacher. I own 11 instruments and can genuinely play 6. My kindergarteners' kazoo orchestra took regionals. Ask me anything.",
  ["music", "guitar", "hiking", "board games"], "relationship", "female", 24, 34, 30, 1, "2025-04-22", "2026-07-16"),
 ("billie_h", "Billie Hart", 26, "female", "Lakeport, WA",
  "Bartender at The Anchor, mixology nerd, plant hoarder. I remember everyone's usual. Wednesday is my Saturday and I'm at the lake if it's sunny.",
  ["mixology", "plants", "paddleboarding", "indie music"], "casual", "any", 22, 33, 20, 1, "2025-10-20", "2026-07-17"),
 ("walt_g", "Walt Garrison", 55, "male", "Millhaven, WA",
  "Semi-retired dairy farmer transitioning the farm to my nephew. Learning to travel, cook for one (badly), and use this app (worse).",
  ["farming", "country music", "fishing", "travel"], "relationship", "female", 45, 60, 40, 1, "2025-05-16", "2026-07-12"),
 ("noor_a", "Noor Al-Rashid", 30, "female", "Lakeport, WA",
  "Immigration attorney by day, mediocre-but-enthusiastic rock climber by night. I argue for a living; I promise to leave it at the office. Mostly.",
  ["climbing", "reading", "travel", "cooking"], "relationship", "male", 27, 38, 30, 1, "2025-02-08", "2026-07-16"),
 ("chip_d", "Chip Dawson", 27, "male", "Lakeport, WA",
  "Golf course groundskeeper with a 4 handicap and a sunrise photography habit. The course at 5am is my church.",
  ["golf", "photography", "fishing", "craft beer"], "casual", "female", 23, 32, 25, 0, "2026-03-01", "2026-07-16"),
 ("romy_v", "Romy Vance", 33, "female", "Cedar Falls, WA",
  "Midwife. I've delivered 300+ babies and I still cry every time. Off duty you'll find me on the river with a fly rod.",
  ["fly fishing", "hiking", "baking", "podcasts"], "relationship", "male", 29, 42, 35, 1, "2024-10-08", "2026-07-15"),
 ("axel_j", "Axel Johansson", 35, "male", "Lakeport, WA",
  "Furniture designer, ex-IKEA (the irony is not lost on me). Everything in my house has a story and a splinter risk.",
  ["woodworking", "design", "sauna culture", "cycling"], "relationship", "female", 28, 40, 30, 1, "2025-01-18", "2026-07-16"),
 ("posy_c", "Posy Clarke", 25, "female", "Lakeport, WA",
  "Florist at Bloom & Bramble. I can tell what flowers you'd be and I'm usually right. Hopeless romantic, employed by romance, do the math.",
  ["flowers", "watercolor painting", "farmers markets", "cats"], "relationship", "male", 23, 32, 20, 1, "2026-02-25", "2026-07-17"),
 ("moss_r", "Moss Riley", 29, "nonbinary", "Pinecrest, WA",
  "Trail crew lead for the county parks. I build the switchbacks you complain about. Chainsaw certified, campfire certified, feelings certified. They/them.",
  ["trail building", "camping", "banjo", "foraging"], "casual", "any", 24, 36, 45, 1, "2025-07-03", "2026-07-16"),
 ("vera_d", "Vera Dimitrova", 38, "female", "Lakeport, WA",
  "Piano teacher and church organist with a secret metal playlist. My students think Chopin is my favorite. It's Iron Maiden.",
  ["piano", "metal", "reading", "cats"], "relationship", "male", 33, 48, 25, 1, "2024-06-09", "2026-07-15"),
 ("cy_b", "Cy Bennett", 23, "male", "Lakeport, WA",
  "Line cook grinding toward my own pop-up. I stage at Harborview on my days off. Feed me criticism and I'll feed you everything else.",
  ["cooking", "food trucks", "skateboarding", "gaming"], "casual", "any", 21, 28, 15, 0, "2026-05-12", "2026-07-17"),
 ("hazel_p", "Hazel Price", 31, "female", "Eastbrook, WA",
  "Occupational therapist and weekend beach volleyball fiend. I've got strong opinions about sunscreen and stronger serves.",
  ["volleyball", "beach days", "smoothies", "travel"], "relationship", "male", 27, 38, 30, 1, "2025-03-29", "2026-07-16"),
 ("arlo_m", "Arlo Marsh", 40, "male", "Silverton, WA",
  "Luthier — I build and repair guitars in a barn that smells like spruce and varnish. Quiet life, loud amps, open heart.",
  ["guitar", "woodworking", "vinyl records", "hiking"], "relationship", "any", 32, 48, 55, 1, "2024-07-26", "2026-07-14"),
 ("skye_l", "Skye Lawson", 28, "female", "Lakeport, WA",
  "Flight instructor at the county airfield. Best first date I can offer: sunset loop over the sound, you pick the playlist. (Weather permitting. Always weather permitting.)",
  ["flying", "photography", "running", "travel"], "casual", "any", 24, 36, 40, 1, "2025-06-17", "2026-07-17"),
]

def password_for(username, interests, joined):
    word = interests[0].split()[0].lower().replace("-", "")[:8]
    year = joined[:4]
    return f"{word}{year}!"

user_rows = []
for i, (username, name, age, gender, city, bio, interests, looking_for,
        gpref, min_age, max_age, max_dist, verified, joined, last_day) in enumerate(NEW_USERS):
    uid = 9 + i
    lat, lng = coords(city)
    prefs = {"min_age": min_age, "max_age": max_age,
             "gender_pref": gpref, "max_distance_miles": max_dist}
    hour = rng.randint(7, 23)
    user_rows.append((
        uid, 0, username, password_for(username, interests, joined), name, age, gender,
        bio, city, json.dumps(interests), looking_for, json.dumps(prefs),
        json.dumps([f"/sites/dating/static/profiles/{username}.svg"]),
        verified, f"{last_day}T{hour:02d}:{rng.randint(0,59):02d}:00",
        f"{joined}T{rng.randint(8,20):02d}:00:00", lat, lng,
    ))

db.executemany(
    "INSERT INTO dating_users (id, root_user_id, username, password, name, age, gender,"
    " bio, location, interests, looking_for, preferences, photos, verified,"
    " last_active, joined_date, lat, lng) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
    user_rows)
print("new users:", len(user_rows))

# ── backfill conversations for matches 4-7 (notes referenced missing msgs) ───
# (match_id, sender_id, timestamp, content)  — read flags set below
BACKFILL = [
 # Match 4: Sophie (4) & Nathan (7), matched 2026-03-05, active.
 (4, 7, "2026-03-05T10:20:00", "Sophie! Your gallery photos stopped my scroll. That mural shot with the ladder shadow — where was that?"),
 (4, 4, "2026-03-05T12:05:00", "Ha, thank you! That's the old cannery wall on Dockside. I shot it at 7am before the light went flat. You're the gym owner, right?"),
 (4, 7, "2026-03-05T12:40:00", "Guilty. Though 'guy who reorganizes dumbbells for a living' is more accurate. I've been wanting decent photos of the gym for the website, fate maybe?"),
 (4, 4, "2026-03-06T09:15:00", "Smooth way to get a free shoot. It'll cost you a smoothie at least."),
 (4, 7, "2026-03-08T18:30:00", "Deal. Saturday morning? Golden hour hits the front windows around 8."),
 (4, 4, "2026-03-08T19:02:00", "Look at you knowing what golden hour is. Saturday works."),
 (4, 4, "2026-03-14T17:45:00", "Those turned out really well btw. The rope wall one especially. Sending the album tonight."),
 (4, 7, "2026-03-14T18:20:00", "You made my gym look like a movie set. Dinner's on me — Harborview Friday?"),
 (4, 4, "2026-03-14T18:31:00", "It's a date. An actual one this time."),
 (4, 7, "2026-05-02T20:10:00", "Still thinking about that trail you took me up today. My calves are writing you an angry letter."),
 (4, 4, "2026-05-02T20:44:00", "Tell them it was worth it for the view. Next time we do the sunrise version."),
 (4, 7, "2026-07-11T21:05:00", "Booked the Silverton cabin for the 25th. Bring the film camera, the meadow should be blooming."),
 # Match 5: Mia (2) & Daniel (5), matched 2025-10-22, unmatched amicably.
 (5, 5, "2025-10-22T14:30:00", "Mia! Fellow outdoors person. What's your go-to trail when you only have a half day?"),
 (5, 2, "2025-10-22T15:10:00", "Easy — Cedar Ridge north loop. You can be up and back before the clinic calls me in. You?"),
 (5, 5, "2025-10-23T09:05:00", "Same loop honestly. Weird we haven't crossed paths. Block party circuit keeps me busy most weekends though."),
 (5, 2, "2025-10-25T19:40:00", "Ha, I've seen the flyers for those. You know we have like four mutual friends? Tiny town."),
 (5, 5, "2025-10-27T20:15:00", "Just realized we're both going to Priya's Halloween thing. This might be more 'friends' energy than app energy, isn't it."),
 (5, 2, "2025-10-28T08:50:00", "Yeah I was feeling that too 😅 See you Friday as friends? I'm going as a very tired vet tech. It's not a costume."),
 # Match 6: Natalie (6) & Nathan (7), matched 2026-04-10, fizzled.
 (6, 6, "2026-04-10T21:00:00", "ok gym owner. rate my deadlift form, I'll send a video, be brutal"),
 (6, 7, "2026-04-10T21:25:00", "Send it. Brutal is my love language."),
 (6, 6, "2026-04-10T21:40:00", "[video] go"),
 (6, 7, "2026-04-11T07:30:00", "Bar's drifting off your mid-foot and you're rushing the lockout. Honestly not bad though. Come by the gym, first session's free."),
 (6, 6, "2026-04-11T23:55:00", "maybe!! whats your gym's music situation, this matters more than the equipment"),
 (6, 7, "2026-04-12T06:10:00", "Whatever's on the classic rock station. It builds character."),
 (6, 6, "2026-04-14T22:30:00", "dad rock at 6am is a red flag but I respect the commitment lol"),
 # Match 7: Olivia (3) & Daniel (5), matched 2025-12-15, unmatched after a week.
 (7, 3, "2025-12-15T17:00:00", "So a PT who organizes block parties — do you ever actually sit still?"),
 (7, 5, "2025-12-15T18:20:00", "Sitting still is how injuries happen. What about you, the travel photos are unreal. Lisbon looked amazing."),
 (7, 3, "2025-12-16T10:05:00", "Lisbon was a work trip that accidentally became a life plan. I'm back there in March for a client."),
 (7, 5, "2025-12-18T19:30:00", "That's a lot of time zones. I'm more of a 'everything I love is within ten miles' guy honestly."),
 (7, 3, "2025-12-20T22:15:00", "Ha, and that's the whole thing in a nutshell isn't it. You're great but I think we want opposite maps."),
]

# ── new matches & conversations among new users ──────────────────────────────
# Pairs are keyed by username so gender/age-pref compatibility is auditable.
uname_to_id = {u[2]: u[0] for u in user_rows}
PAIRS = [
 ("jade_m", "theo_r",   "2026-04-18T20:30:00", "active", [
    ("theo_r", "2026-04-18T20:45:00", "A nurse and an EMT. Between us we're basically a small hospital."),
    ("jade_m", "2026-04-18T21:02:00", "Ha! Which means neither of us has a normal weekend. When's your next day off, Tuesday?"),
    ("theo_r", "2026-04-18T21:15:00", "Wednesday. You?"),
    ("jade_m", "2026-04-18T21:20:00", "Wednesday!! Ok that never happens. Breakfast at 3pm? I know a place that doesn't judge."),
    ("theo_r", "2026-04-19T06:05:00", "It's a plan. I'm the guy who orders pancakes AND eggs, fair warning."),
    ("jade_m", "2026-04-22T23:40:00", "Today confirmed you're one of the good ones. Even if you salted the pancakes. Next Wednesday, my gnocchi?"),
    ("theo_r", "2026-04-23T05:55:00", "The famous gnocchi?? I'll bring the appetite and a defibrillator."),
    ("jade_m", "2026-07-15T22:30:00", "Swapped my Saturday shift. Lake day??"),
    ("theo_r", "2026-07-16T05:50:00", "Lake day. I'll get the kayaks from my brother."),
 ]),
 ("priya_s", "raj_k",   "2026-03-02T19:00:00", "active", [
    ("raj_k",  "2026-03-02T19:20:00", "A designer with a garden. My telescope and I would like to formally request a viewing of this yard."),
    ("priya_s","2026-03-02T20:01:00", "The yard is 70% ambition and 30% dead tomatoes but the sky above it is excellent. You really photograph planets?"),
    ("raj_k",  "2026-03-02T20:15:00", "14 hours for one photo of Saturn. My mom thinks it's a sticker."),
    ("priya_s","2026-03-02T20:22:00", "I need to see the sticker. New moon is the 29th, I checked. See, I did research too."),
    ("raj_k",  "2026-03-02T20:30:00", "A person who checks lunar phases unprompted. Marrying you. I mean — coffee first, then marriage."),
    ("priya_s","2026-03-29T23:50:00", "Ok that was genuinely magical. Jupiter has STRIPES. Why did nobody tell me Jupiter has stripes."),
    ("raj_k",  "2026-03-30T07:40:00", "I've been telling everyone for years! They stopped inviting me to parties. Dinner Friday? I'll leave the telescope home. Maybe."),
    ("priya_s","2026-06-20T21:15:00", "Solstice bonfire at mine Saturday. Bring the telescope, my sister doesn't believe the Jupiter thing either."),
 ]),
 ("amara_o", "dmitri_s","2026-05-20T21:10:00", "active", [
    ("amara_o","2026-05-20T21:30:00", "A volleyball player. Tell me — can you dance, or are you all jump and no rhythm?"),
    ("dmitri_s","2026-05-20T21:48:00", "There is footwork in volleyball! It's just... aggressively unromantic footwork."),
    ("amara_o","2026-05-20T21:55:00", "Thursday, 7pm, my salsa studio. Beginners class. We'll see about that footwork."),
    ("dmitri_s","2026-05-22T22:40:00", "My ego may never recover but my hips have learned things. Same time next week?"),
    ("amara_o","2026-05-22T22:51:00", "You were the best in class and it annoyed me. Yes, next week. Then you teach me to serve."),
    ("dmitri_s","2026-06-19T20:05:00", "Beach league Thursday needs a sub. You in? Fair warning, my team takes it too seriously."),
    ("amara_o","2026-06-19T20:20:00", "Taking it too seriously is my entire personality. In."),
 ]),
 ("kevin_p", "romy_v",  "2026-06-01T18:45:00", "active", [
    ("kevin_p","2026-06-01T19:00:00", "A midwife who fly fishes. My golden retriever Biscuit and I are both very impressed."),
    ("romy_v", "2026-06-01T19:30:00", "Biscuit is doing a lot of work in that profile, I hope you know. Does he wade?"),
    ("kevin_p","2026-06-01T19:42:00", "He believes every fish is his personal friend. Ruins the fishing, improves the day."),
    ("romy_v", "2026-06-01T20:05:00", "That's the correct tradeoff. There's a stretch on the Cedar I like Sunday mornings — bring the fish-greeter?"),
    ("kevin_p","2026-06-08T14:20:00", "Today was the most peaceful I've been in months. Even with the zero fish caught."),
    ("romy_v", "2026-06-08T15:01:00", "Zero fish, one very happy dog, decent company. I'd call that a catch. Dinner next time, I'll bake."),
 ]),
 ("dora_e",  "stan_w",  "2026-05-09T20:00:00", "active", [
    ("stan_w", "2026-05-09T20:15:00", "A councilwoman with bees. I coached your nephew, I think. Tyler? Good kid, terrible route runner."),
    ("dora_e", "2026-05-09T20:40:00", "THAT'S where I know your face from! Small town strikes again. He still talks about that championship season."),
    ("stan_w", "2026-05-09T20:52:00", "We peaked together, that team and me. So — the bees. Do they know you're on the council or do you keep work separate?"),
    ("dora_e", "2026-05-09T21:10:00", "The bees are apolitical, thank goodness. Coffee after Saturday's market? I'll bring you a jar of honey and my best zoning-board story."),
    ("stan_w", "2026-05-16T18:30:00", "That zoning story was better than most game film. Next Saturday, same table?"),
    ("dora_e", "2026-05-16T19:02:00", "Same table. My turn to hear about the '19 season comeback. Tyler says you cried. He also says hello."),
    ("stan_w", "2026-07-13T21:20:00", "Fair week starts Friday. Come judge the pie contest with me — I have influence."),
 ]),
 ("faith_a", "leo_a",   "2026-06-12T19:30:00", "active", [
    ("leo_a",  "2026-06-12T19:45:00", "A pharmacist who writes novels. As a librarian I'm professionally obligated to ask: pen name?"),
    ("faith_a","2026-06-12T20:10:00", "Absolutely not. People WEEP over these books, Leo. My coworkers cannot know."),
    ("leo_a",  "2026-06-12T20:18:00", "Understood. But know that I have interlibrary loan powers and unlimited spite time."),
    ("faith_a","2026-06-12T20:25:00", "Is that a threat or a first date? Because either way, the used bookstore in Cedar Falls, Saturday."),
    ("leo_a",  "2026-06-14T17:40:00", "You bought nine books and hid one from me at the register. It's yours, isn't it. I saw the cover."),
    ("faith_a","2026-06-14T17:52:00", "I will neither confirm nor deny. Dinner first. Truths are earned, chapter by chapter."),
 ]),
 ("penny_h", "cy_b",    "2026-06-25T21:00:00", "active", [
    ("cy_b",   "2026-06-25T21:20:00", "Ok cards on the table: I've eaten at the Dumpling Cart eleven times and I only just recognized you from the app."),
    ("penny_h","2026-06-25T21:35:00", "ELEVEN? Wait. Are you extra-chili-oil guy?? Tuesdays and Fridays??"),
    ("cy_b",   "2026-06-25T21:38:00", "...I'm extra-chili-oil guy."),
    ("penny_h","2026-06-25T21:44:00", "I literally started stocking more chili oil because of you. This is the weirdest meet-cute. Fine — you cook for ME. One dish. Impress me."),
    ("cy_b",   "2026-06-25T21:50:00", "Pressure accepted. Sunday. Bring your professional-grade criticism, I want the real review."),
    ("penny_h","2026-06-29T23:10:00", "Fine. FINE. The scallion pancakes were better than mine. Tell no one. Second dinner Thursday?"),
 ]),
 ("clara_b", "ezra_f",  "2026-02-14T20:20:00", "unmatched", [
    ("ezra_f", "2026-02-14T20:35:00", "A muralist! I've filmed two of your walls without knowing they were yours. The heron one on the coop building — that's you, right?"),
    ("clara_b","2026-02-14T21:00:00", "That's me! Frozen fingers, three lifts of scaffolding, worth it. A doc filmmaker — what are you working on?"),
    ("ezra_f", "2026-02-14T21:12:00", "Logging archive project. And weddings, because rent. Coffee sometime? I'd love to talk shop."),
    ("clara_b","2026-02-20T18:40:00", "Sorry for the slow reply — mural season prep hit like a truck. Coffee, yes. March maybe?"),
    ("ezra_f", "2026-03-03T12:10:00", "March is here! Still up for it?"),
    ("clara_b","2026-03-10T22:05:00", "I'm the worst — commissions in three towns right now. Honestly my calendar isn't being fair to you. Rain check indefinitely? You seem lovely."),
 ]),
 ("billie_h","oscar_h", "2026-07-05T19:15:00", "active", [
    ("oscar_h","2026-07-05T19:30:00", "The Anchor's bartender. I mixed the Vandals show last month and your espresso martini kept the whole crew alive."),
    ("billie_h","2026-07-05T19:50:00", "The sound guy!! You all tipped like saints. How are your ears after that show, be honest."),
    ("oscar_h","2026-07-05T19:58:00", "Ringing in E flat. Come to Saturday's show — I'll put you on the list, side of stage where it's safe-ish."),
    ("billie_h","2026-07-06T00:20:00", "Just got off shift and yes. List me. I'll bring earplugs for you, top shelf ones, bartender's honor."),
    ("oscar_h","2026-07-12T01:15:00", "Tonight was fun. You know every word to every song and I know every flaw in every mix. We're insufferable together."),
    ("billie_h","2026-07-12T01:22:00", "Perfectly insufferable. Lake day Wednesday? I have paddleboards and opinions about playlists."),
 ]),
]

match_rows = []
msg_rows = []
next_match_id = 8
next_msg_id = 41  # 40 seeded messages
for u1, u2, mdate, status, msgs in PAIRS:
    match_rows.append((next_match_id, uname_to_id[u1], uname_to_id[u2], mdate, status, ""))
    for sender_uname, ts, content in msgs:
        # unread only for the newest active-thread messages
        msg_rows.append((next_msg_id, next_match_id, uname_to_id[sender_uname], content, ts, 1))
        next_msg_id += 1
    next_match_id += 1

for match_id, sender_id, ts, content in BACKFILL:
    msg_rows.append((next_msg_id, match_id, sender_id, content, ts, 1))
    next_msg_id += 1

# Leave the most recent message of matches 4, 8 and 12 unread for the recipient
unread_targets = {"Booked the Silverton cabin", "Lake day. I'll get the kayaks",
                  "Fair week starts Friday"}
msg_rows = [
    (mid, match, sender, content, ts, 0 if any(content.startswith(t) for t in unread_targets) else read)
    for (mid, match, sender, content, ts, read) in msg_rows
]

db.executemany(
    "INSERT INTO dating_matches (id, user1_id, user2_id, matched_date, status, notes)"
    " VALUES (?,?,?,?,?,?)", match_rows)
db.executemany(
    "INSERT INTO dating_messages (id, match_id, sender_id, content, timestamp, read)"
    " VALUES (?,?,?,?,?,?)", msg_rows)
print("new matches:", len(match_rows), "| new messages:", len(msg_rows))

# ── likes ────────────────────────────────────────────────────────────────────
like_rows = []
next_like_id = 23  # 22 seeded likes

def add_like(from_u, to_u, date, status, comment=""):
    global next_like_id
    fid = uname_to_id.get(from_u, EXISTING_IDS.get(from_u))
    tid = uname_to_id.get(to_u, EXISTING_IDS.get(to_u))
    like_rows.append((next_like_id, fid, tid, date, status, comment))
    next_like_id += 1

EXISTING_IDS = {"alex_r": 1, "mia_t": 2, "olivia_j": 3, "sophie_l": 4,
                "daniel_o": 5, "natalie_k": 6, "nathan_b": 7, "rachel_k": 8}

# Mutual likes behind every new match
for u1, u2, mdate, status, msgs in PAIRS:
    day = mdate[:10]
    add_like(u2, u1, f"{day}T{int(mdate[11:13])-2:02d}:00:00", "matched")
    add_like(u1, u2, mdate, "matched")

# Pending likes into the seeded accounts (gives every login a Likes You queue)
add_like("penny_h", "alex_r", "2026-06-28T20:30:00", "pending",
         "Penny liked Alex. Another cook who hikes — obviously.")
add_like("noor_a", "alex_r", "2026-07-08T21:15:00", "pending",
         "Noor liked Alex. The camera and the trail photos did it.")
add_like("derek_c", "mia_t", "2026-07-02T19:00:00", "pending",
         "Derek liked Mia. Animals and the outdoors, easy call.")
add_like("axel_j", "olivia_j", "2026-06-30T22:10:00", "pending")
add_like("jamal_e", "natalie_k", "2026-07-06T23:40:00", "pending",
         "Jamal liked Natalie. Skateboarding and indie music overlap.")
add_like("leo_a", "rachel_k", "2026-05-28T17:20:00", "pending",
         "Leo liked Rachel. Fellow librarian; he's nervous about it.")
add_like("tess_d", "cole_n", "2026-07-10T21:30:00", "pending")
add_like("mira_n", "diego_l", "2026-07-09T20:45:00", "pending")
add_like("hazel_p", "dmitri_s", "2026-07-01T19:10:00", "pending")
add_like("ivy_m", "marcus_w", "2026-06-22T18:00:00", "pending")
add_like("greta_s", "victor_m", "2026-07-04T20:20:00", "pending")
add_like("suki_t", "felix_g", "2026-07-13T22:50:00", "pending")
add_like("posy_c", "theo_r", "2026-07-11T16:30:00", "pending")
add_like("opal_t", "arlo_m", "2026-06-18T19:40:00", "pending")
add_like("walt_g", "mabel_j", "2026-07-03T13:15:00", "pending")
add_like("carmen_r", "bruno_m", "2026-06-26T21:00:00", "pending")
add_like("finn_b", "billie_h", "2026-07-14T23:20:00", "pending")
add_like("zoe_k", "sam_t", "2026-07-12T21:10:00", "pending")
add_like("wren_c", "moss_r", "2026-07-07T20:00:00", "pending")
add_like("skye_l", "chip_d", "2026-07-15T19:25:00", "pending")

# Some passes so the graph isn't all positive
add_like("june_p", "cole_n", "2026-05-14T20:00:00", "passed")
add_like("nina_r", "gus_f", "2026-04-20T18:30:00", "passed")
add_like("vera_d", "hank_o", "2026-03-11T21:00:00", "passed")
add_like("harper_l", "finn_b", "2026-06-15T22:40:00", "passed")
add_like("iris_w", "kevin_p", "2026-05-25T19:50:00", "passed")
add_like("elena_v", "oscar_h", "2026-06-10T23:30:00", "passed")

db.executemany(
    "INSERT INTO dating_likes (id, from_user_id, to_user_id, date, status, comment)"
    " VALUES (?,?,?,?,?,?)", like_rows)
print("new likes:", len(like_rows))

# ── SVG avatars ──────────────────────────────────────────────────────────────
AVATAR_DIR.mkdir(parents=True, exist_ok=True)
PALETTES = [("#e8475f", "#f4845f"), ("#667eea", "#f093fb"), ("#0ea5e9", "#22d3ee"),
            ("#16a34a", "#84cc16"), ("#f59e0b", "#ef4444"), ("#8b5cf6", "#ec4899"),
            ("#0f766e", "#2dd4bf"), ("#b45309", "#fbbf24")]

all_people = [(u[2], u[4]) for u in user_rows] + [
    (uname, name) for uname, name in [
        ("alex_r", "Alex Rivera"), ("mia_t", "Mia Torres"), ("olivia_j", "Olivia Johansson"),
        ("sophie_l", "Sophie Lin"), ("daniel_o", "Daniel Okonkwo"), ("natalie_k", "Natalie Kim"),
        ("nathan_b", "Nathan Brooks"), ("rachel_k", "Rachel Kim")]]

for username, name in all_people:
    parts = name.split()
    initials = (parts[0][0] + parts[-1][0]).upper()
    c1, c2 = PALETTES[sum(ord(ch) for ch in username) % len(PALETTES)]
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400" viewBox="0 0 400 400">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
<stop offset="0" stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/></linearGradient></defs>
<rect width="400" height="400" fill="url(#g)"/>
<circle cx="200" cy="150" r="70" fill="rgba(255,255,255,0.25)"/>
<ellipse cx="200" cy="330" rx="120" ry="90" fill="rgba(255,255,255,0.25)"/>
<text x="200" y="222" font-family="-apple-system,Segoe UI,Roboto,sans-serif" font-size="96"
 font-weight="700" fill="#ffffff" text-anchor="middle">{initials}</text>
</svg>
"""
    (AVATAR_DIR / f"{username}.svg").write_text(svg)
print("avatars:", len(all_people))

# ── rebuild external-content FTS (no sync triggers exist) ────────────────────
db.execute("INSERT INTO fts_dating_messages(fts_dating_messages) VALUES('rebuild')")
db.execute("INSERT INTO fts_dating_likes(fts_dating_likes) VALUES('rebuild')")

db.commit()

for t in ("dating_users", "dating_likes", "dating_matches", "dating_messages"):
    print(t, "->", db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0], "rows")
