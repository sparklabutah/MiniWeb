#!/usr/bin/env python3
"""
Fetch real sports data from TheSportsDB (free tier, api_key=3) and generate
data files for the MiniWeb sports-esports site.

Produces:
  - leagues.json   (~8-10 leagues across soccer, basketball, hockey, MMA, tennis, esports)
  - teams.json     (~24+ teams)
  - players.json   (~50 players — synthesized names with real team associations)
  - matches.json   (~200 records — the primary entity, sourced from past events)
  - users.json     (~5 users — synthesized)
  - comments.json  (~25 comments — synthesized)

All IDs are integers to match the existing routes.py (uses <int:...> converters).
"""

import json
import pathlib
import random
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta

BASE_URL = "https://www.thesportsdb.com/api/v1/json/3"
DATA_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "sites" / "sports-esports" / "data"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def api_get(endpoint: str, retries: int = 3) -> dict | None:
    """GET a TheSportsDB endpoint with retry logic."""
    url = f"{BASE_URL}/{endpoint}"
    for attempt in range(retries):
        try:
            print(f"  GET {url}")
            req = urllib.request.Request(url, headers={"User-Agent": "MiniWeb-DataPrep/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            return data
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            print(f"    Attempt {attempt+1} failed: {e}")
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
    return None


def save(name: str, data):
    path = DATA_DIR / name
    path.write_text(json.dumps(data, indent=4, ensure_ascii=False))
    print(f"Wrote {path}  ({len(data)} records)")


# ---------------------------------------------------------------------------
# Target leagues — a mix of real sports + esports placeholders
# ---------------------------------------------------------------------------

# We'll fetch real league info for these known league IDs from TheSportsDB
TARGET_LEAGUES = [
    # (thesportsdb_id, sport_label, type, region)
    (4328, "Soccer", "traditional", "Europe"),         # English Premier League
    (4335, "Soccer", "traditional", "Europe"),         # La Liga
    (4331, "Soccer", "traditional", "Europe"),         # Bundesliga
    (4380, "Soccer", "traditional", "Europe"),         # Serie A
    (4387, "Basketball", "traditional", "North America"),  # NBA
    (4380, "Soccer", "traditional", "Europe"),         # duplicate, skip — use MLS instead
    (4346, "Ice Hockey", "traditional", "North America"),  # NHL
    (4344, "Baseball", "traditional", "North America"),    # MLB (if available)
]

# We'll also manually add esports leagues (not in TheSportsDB)
ESPORTS_LEAGUES = [
    {"name": "League of Legends World Championship", "sport": "League of Legends", "type": "esports",
     "region": "Global", "season": "2024", "team_count": 3, "start_date": "2024-09-25",
     "end_date": "2024-11-02", "is_active": False},
    {"name": "Valorant Champions Tour", "sport": "Valorant", "type": "esports",
     "region": "Global", "season": "2025", "team_count": 3, "start_date": "2025-03-01",
     "end_date": "2025-08-30", "is_active": True},
]

# ---------------------------------------------------------------------------
# Fetch leagues
# ---------------------------------------------------------------------------

def fetch_leagues():
    """Fetch league details from TheSportsDB for our target league IDs."""
    leagues = []
    league_id_counter = 1
    seen_db_ids = set()

    # Real sports leagues
    real_league_ids = [4328, 4335, 4331, 4387, 4346, 4344]
    for db_id in real_league_ids:
        if db_id in seen_db_ids:
            continue
        seen_db_ids.add(db_id)

        data = api_get(f"lookupleague.php?id={db_id}")
        if not data or not data.get("leagues"):
            print(f"    Skipping league {db_id} — no data")
            continue

        lg = data["leagues"][0]
        sport_map = {
            "Soccer": "Soccer",
            "Basketball": "Basketball",
            "Ice Hockey": "Ice Hockey",
            "Baseball": "Baseball",
            "American Football": "American Football",
        }
        sport = lg.get("strSport", "Unknown")
        sport_label = sport_map.get(sport, sport)

        region = "Europe"
        if lg.get("strCountry") in ("United States", "USA", "Canada", "United States,Canada"):
            region = "North America"
        elif lg.get("strCountry") in ("Japan", "South Korea", "China"):
            region = "Asia"

        leagues.append({
            "id": league_id_counter,
            "name": lg.get("strLeague", f"League {db_id}"),
            "sport": sport_label,
            "type": "traditional",
            "region": region,
            "season": "2024-2025",
            "team_count": 0,  # filled later
            "start_date": "2024-08-15",
            "end_date": "2025-05-30",
            "is_active": True,
            "_db_id": db_id,  # internal, stripped later
        })
        league_id_counter += 1
        time.sleep(0.5)

    # Esports leagues (manually defined)
    for elg in ESPORTS_LEAGUES:
        lg_entry = dict(elg)
        lg_entry["id"] = league_id_counter
        lg_entry["_db_id"] = None
        leagues.append(lg_entry)
        league_id_counter += 1

    return leagues


# ---------------------------------------------------------------------------
# Fetch teams for each league
# ---------------------------------------------------------------------------

def fetch_teams(leagues):
    """Fetch teams from TheSportsDB for real leagues, synthesize for esports."""
    teams = []
    team_id_counter = 1

    # Map from league _db_id -> our league id
    db_to_local = {lg["_db_id"]: lg["id"] for lg in leagues if lg["_db_id"]}

    for lg in leagues:
        db_id = lg["_db_id"]
        if db_id:
            # Fetch teams by league name
            league_name = lg["name"].replace(" ", "%20")
            data = api_get(f"search_all_teams.php?l={league_name}")
            if not data or not data.get("teams"):
                print(f"    No teams for {lg['name']}")
                continue

            # Take up to 4 teams per league to keep manageable
            api_teams = data["teams"][:4]
            for t in api_teams:
                founded = 0
                try:
                    founded = int(t.get("intFormedYear", 0) or 0)
                except (ValueError, TypeError):
                    founded = 1900

                teams.append({
                    "id": team_id_counter,
                    "name": t.get("strTeam", f"Team {team_id_counter}"),
                    "league_id": lg["id"],
                    "sport": lg["sport"],
                    "region": lg["region"],
                    "founded": founded,
                    "wins": random.randint(8, 28),
                    "losses": random.randint(2, 15),
                    "draws": random.randint(0, 10) if lg["sport"] == "Soccer" else 0,
                    "points": 0,  # computed below
                    "ranking": 0,  # computed below
                    "logo_url": t.get("strBadge", "") or f"/static/logos/team{team_id_counter}.png",
                    "coach": t.get("strManager", "") or "Head Coach",
                    "roster_size": random.randint(15, 30),
                    "_db_team_id": t.get("idTeam"),
                })
                team_id_counter += 1
            time.sleep(0.5)
        else:
            # Esports — synthesize teams
            esports_teams_data = {
                "League of Legends": [
                    ("T1", "Asia", "Bengi", 2012),
                    ("Gen.G", "Asia", "Score", 2017),
                    ("Cloud9", "North America", "Rapidstar", 2013),
                ],
                "Valorant": [
                    ("Sentinels", "North America", "kaplan", 2016),
                    ("Fnatic", "Europe", "mini", 2004),
                    ("DRX", "Asia", "termi", 2012),
                ],
            }
            for tname, tregion, tcoach, tfounded in esports_teams_data.get(lg["sport"], []):
                teams.append({
                    "id": team_id_counter,
                    "name": tname,
                    "league_id": lg["id"],
                    "sport": lg["sport"],
                    "region": tregion,
                    "founded": tfounded,
                    "wins": random.randint(8, 18),
                    "losses": random.randint(1, 8),
                    "draws": 0,
                    "points": 0,
                    "ranking": 0,
                    "logo_url": f"/static/logos/team{team_id_counter}.png",
                    "coach": tcoach,
                    "roster_size": random.randint(6, 12),
                    "_db_team_id": None,
                })
                team_id_counter += 1

    # Compute points and rankings per league
    for lg in leagues:
        lg_teams = [t for t in teams if t["league_id"] == lg["id"]]
        for t in lg_teams:
            if lg["sport"] == "Soccer":
                t["points"] = t["wins"] * 3 + t["draws"]
            else:
                t["points"] = t["wins"]
        lg_teams.sort(key=lambda x: x["points"], reverse=True)
        for rank, t in enumerate(lg_teams, 1):
            t["ranking"] = rank
        lg["team_count"] = len(lg_teams)

    return teams


# ---------------------------------------------------------------------------
# Fetch matches (past events) — aim for ~200 records
# ---------------------------------------------------------------------------

def fetch_matches(leagues, teams):
    """Fetch past events from TheSportsDB; synthesize extras to reach ~200."""
    matches = []
    match_id_counter = 1

    # Build lookup: league_id -> list of team ids
    league_teams = {}
    for t in teams:
        league_teams.setdefault(t["league_id"], []).append(t["id"])

    # Build team id lookup by name for matching API events
    team_by_name = {}
    for t in teams:
        team_by_name[t["name"].lower()] = t["id"]
        # Also store short forms
        for word in t["name"].split():
            if len(word) > 3:
                team_by_name[word.lower()] = t["id"]

    # Fetch real past events for leagues that have TheSportsDB IDs
    for lg in leagues:
        db_id = lg["_db_id"]
        if not db_id:
            continue

        data = api_get(f"eventspastleague.php?id={db_id}")
        if not data or not data.get("events"):
            print(f"    No past events for {lg['name']}")
            continue

        events = data["events"]
        lg_team_ids = league_teams.get(lg["id"], [])
        if not lg_team_ids:
            continue

        for ev in events[:35]:  # up to 35 per league
            # Try to match home/away teams
            home_name = (ev.get("strHomeTeam") or "").lower()
            away_name = (ev.get("strAwayTeam") or "").lower()

            home_id = team_by_name.get(home_name)
            away_id = team_by_name.get(away_name)

            # If we can't match, assign randomly from this league's teams
            if not home_id or home_id not in lg_team_ids:
                home_id = random.choice(lg_team_ids)
            if not away_id or away_id not in lg_team_ids or away_id == home_id:
                candidates = [tid for tid in lg_team_ids if tid != home_id]
                away_id = random.choice(candidates) if candidates else home_id

            # Parse scores
            home_score = 0
            away_score = 0
            try:
                home_score = int(ev.get("intHomeScore") or 0)
                away_score = int(ev.get("intAwayScore") or 0)
            except (ValueError, TypeError):
                home_score = random.randint(0, 4)
                away_score = random.randint(0, 4)

            event_date = ev.get("dateEvent", "2025-01-01")
            venue = ev.get("strVenue", "") or "Stadium"

            # Pick a random player from the home team as MVP
            home_players_later = []  # filled after players are generated

            matches.append({
                "id": match_id_counter,
                "league_id": lg["id"],
                "home_team_id": home_id,
                "away_team_id": away_id,
                "date": event_date,
                "status": "completed",
                "home_score": home_score,
                "away_score": away_score,
                "venue": venue[:60] if venue else "Stadium",
                "highlights_url": f"/highlights/match{match_id_counter}.mp4",
                "video_duration_sec": random.randint(300, 3600),
                "attendance": random.randint(5000, 80000),
                "mvp_player_id": None,  # filled after players exist
                "_source": "api",
            })
            match_id_counter += 1
        time.sleep(0.5)

    # Synthesize matches for esports leagues and to pad to ~200
    for lg in leagues:
        if lg["_db_id"] is not None:
            continue  # already fetched
        lg_team_ids = league_teams.get(lg["id"], [])
        if len(lg_team_ids) < 2:
            continue
        # Generate 15 matches per esports league
        for _ in range(15):
            home_id = random.choice(lg_team_ids)
            away_id = random.choice([t for t in lg_team_ids if t != home_id])
            base_date = datetime(2025, random.randint(1, 6), random.randint(1, 28))
            is_esports = lg["type"] == "esports"
            matches.append({
                "id": match_id_counter,
                "league_id": lg["id"],
                "home_team_id": home_id,
                "away_team_id": away_id,
                "date": base_date.strftime("%Y-%m-%d"),
                "status": random.choice(["completed", "completed", "completed", "scheduled"]),
                "home_score": random.randint(0, 16) if is_esports else random.randint(0, 5),
                "away_score": random.randint(0, 16) if is_esports else random.randint(0, 5),
                "venue": f"{lg['sport']} Arena" if is_esports else "Stadium",
                "highlights_url": f"/highlights/match{match_id_counter}.mp4",
                "video_duration_sec": random.randint(1200, 3600) if is_esports else random.randint(300, 700),
                "attendance": random.randint(200, 15000) if is_esports else random.randint(20000, 80000),
                "mvp_player_id": None,
                "_source": "synth",
            })
            match_id_counter += 1

    # If we still have fewer than 200, pad with more synthesized matches from real leagues
    while len(matches) < 200:
        lg = random.choice(leagues)
        lg_team_ids = league_teams.get(lg["id"], [])
        if len(lg_team_ids) < 2:
            continue
        home_id = random.choice(lg_team_ids)
        away_id = random.choice([t for t in lg_team_ids if t != home_id])
        base_date = datetime(2025, random.randint(1, 6), random.randint(1, 28))
        is_soccer = lg["sport"] == "Soccer"
        is_esports = lg["type"] == "esports"

        if is_soccer:
            hs, aws = random.randint(0, 5), random.randint(0, 4)
        elif is_esports:
            hs, aws = random.randint(0, 16), random.randint(0, 16)
        elif lg["sport"] == "Basketball":
            hs, aws = random.randint(85, 135), random.randint(85, 130)
        elif lg["sport"] == "Ice Hockey":
            hs, aws = random.randint(0, 7), random.randint(0, 6)
        elif lg["sport"] == "Baseball":
            hs, aws = random.randint(0, 12), random.randint(0, 10)
        else:
            hs, aws = random.randint(0, 5), random.randint(0, 5)

        status = random.choices(["completed", "scheduled"], weights=[85, 15])[0]
        if status == "scheduled":
            hs, aws = None, None

        matches.append({
            "id": match_id_counter,
            "league_id": lg["id"],
            "home_team_id": home_id,
            "away_team_id": away_id,
            "date": base_date.strftime("%Y-%m-%d"),
            "status": status,
            "home_score": hs,
            "away_score": aws,
            "venue": "Arena" if is_esports else "Stadium",
            "highlights_url": f"/highlights/match{match_id_counter}.mp4" if status == "completed" else None,
            "video_duration_sec": random.randint(300, 3600) if status == "completed" else None,
            "attendance": random.randint(1000, 80000) if status == "completed" else None,
            "mvp_player_id": None,
            "_source": "pad",
        })
        match_id_counter += 1

    # Null out scores for scheduled matches
    for m in matches:
        if m["status"] == "scheduled":
            m["home_score"] = None
            m["away_score"] = None
            m["highlights_url"] = None
            m["video_duration_sec"] = None
            m["attendance"] = None
            m["mvp_player_id"] = None

    return matches


# ---------------------------------------------------------------------------
# Generate players (synthesized but with real team associations)
# ---------------------------------------------------------------------------

PLAYER_NAMES_BY_SPORT = {
    "Soccer": [
        ("Erling Haaland", "Forward", 24, "Norwegian", 9),
        ("Kevin De Bruyne", "Midfielder", 33, "Belgian", 17),
        ("Bukayo Saka", "Forward", 23, "English", 7),
        ("Mohamed Salah", "Forward", 32, "Egyptian", 11),
        ("Kylian Mbappe", "Forward", 26, "French", 9),
        ("Jude Bellingham", "Midfielder", 21, "English", 5),
        ("Vinicius Junior", "Forward", 24, "Brazilian", 7),
        ("Lamine Yamal", "Forward", 17, "Spanish", 19),
        ("Robert Lewandowski", "Forward", 36, "Polish", 9),
        ("Pedri", "Midfielder", 22, "Spanish", 8),
        ("Phil Foden", "Midfielder", 24, "English", 47),
        ("Florian Wirtz", "Midfielder", 21, "German", 10),
        ("Jamal Musiala", "Forward", 21, "German", 42),
        ("Harry Kane", "Forward", 31, "English", 9),
        ("Leroy Sane", "Forward", 29, "German", 10),
        ("Rodri", "Midfielder", 28, "Spanish", 16),
        ("Virgil van Dijk", "Defender", 33, "Dutch", 4),
        ("William Saliba", "Defender", 23, "French", 2),
        ("Martin Odegaard", "Midfielder", 26, "Norwegian", 8),
        ("Cole Palmer", "Forward", 22, "English", 20),
        ("Lautaro Martinez", "Forward", 27, "Argentine", 10),
        ("Hakan Calhanoglu", "Midfielder", 30, "Turkish", 20),
        ("Rafael Leao", "Forward", 25, "Portuguese", 10),
        ("Federico Dimarco", "Defender", 26, "Italian", 32),
    ],
    "Basketball": [
        ("LeBron James", "Forward", 40, "American", 23),
        ("Stephen Curry", "Guard", 36, "American", 30),
        ("Jayson Tatum", "Forward", 26, "American", 0),
        ("Luka Doncic", "Guard", 25, "Slovenian", 77),
        ("Nikola Jokic", "Center", 29, "Serbian", 15),
        ("Anthony Davis", "Center", 31, "American", 3),
        ("Giannis Antetokounmpo", "Forward", 30, "Greek", 34),
        ("Kevin Durant", "Forward", 36, "American", 35),
    ],
    "Ice Hockey": [
        ("Connor McDavid", "Center", 27, "Canadian", 97),
        ("Auston Matthews", "Center", 27, "American", 34),
        ("Nathan MacKinnon", "Center", 29, "Canadian", 29),
        ("Leon Draisaitl", "Center", 29, "German", 29),
        ("Cale Makar", "Defenseman", 26, "Canadian", 8),
        ("Sidney Crosby", "Center", 37, "Canadian", 87),
    ],
    "Baseball": [
        ("Shohei Ohtani", "Pitcher/DH", 30, "Japanese", 17),
        ("Mookie Betts", "Outfielder", 32, "American", 50),
        ("Aaron Judge", "Outfielder", 32, "American", 99),
        ("Ronald Acuna Jr", "Outfielder", 27, "Venezuelan", 13),
        ("Freddie Freeman", "First Base", 35, "American", 5),
        ("Mike Trout", "Outfielder", 33, "American", 27),
    ],
    "League of Legends": [
        ("Faker", "Mid", 29, "South Korean", 0),
        ("Gumayusi", "Bot", 22, "South Korean", 0),
        ("Keria", "Support", 22, "South Korean", 0),
        ("Chovy", "Mid", 24, "South Korean", 0),
        ("Peyz", "Bot", 19, "South Korean", 0),
        ("Berserker", "Bot", 21, "South Korean", 0),
    ],
    "Valorant": [
        ("TenZ", "Duelist", 23, "Canadian", 0),
        ("zekken", "Flex", 20, "American", 0),
        ("Boaster", "IGL", 28, "British", 0),
        ("Alfajer", "Duelist", 19, "Turkish", 0),
        ("BuZz", "Sentinel", 24, "South Korean", 0),
        ("MaKo", "Controller", 24, "South Korean", 0),
    ],
}


def generate_players(teams):
    """Generate ~50 players distributed across teams."""
    players = []
    player_id = 1

    # Group teams by sport
    sport_teams = {}
    for t in teams:
        sport_teams.setdefault(t["sport"], []).append(t)

    for sport, sport_team_list in sport_teams.items():
        pool = list(PLAYER_NAMES_BY_SPORT.get(sport, []))
        random.shuffle(pool)

        # Distribute players across teams
        for i, (pname, position, age, nationality, jersey) in enumerate(pool):
            team = sport_team_list[i % len(sport_team_list)]
            is_esports = sport in ("League of Legends", "Valorant")

            if sport == "Basketball":
                goals = random.randint(800, 2000)
                assists = random.randint(150, 600)
                games = random.randint(50, 75)
                salary = random.randint(5_000_000, 55_000_000)
            elif is_esports:
                goals = random.randint(30, 450)
                assists = random.randint(20, 130)
                games = random.randint(8, 20)
                salary = random.randint(300_000, 7_000_000)
            elif sport == "Baseball":
                goals = random.randint(10, 55)  # home runs
                assists = random.randint(20, 100)  # RBIs
                games = random.randint(100, 162)
                salary = random.randint(5_000_000, 70_000_000)
            elif sport == "Ice Hockey":
                goals = random.randint(15, 65)
                assists = random.randint(20, 80)
                games = random.randint(50, 82)
                salary = random.randint(3_000_000, 15_000_000)
            else:  # Soccer
                goals = random.randint(1, 30)
                assists = random.randint(1, 18)
                games = random.randint(15, 35)
                salary = random.randint(100_000, 500_000)

            players.append({
                "id": player_id,
                "name": pname,
                "team_id": team["id"],
                "position": position,
                "age": age,
                "nationality": nationality,
                "jersey_number": jersey,
                "games_played": games,
                "goals_or_kills": goals,
                "assists": assists,
                "rating": round(random.uniform(7.0, 9.5), 1),
                "salary": salary,
                "is_active": random.choices([True, False], weights=[90, 10])[0],
                "joined": f"{random.randint(2015, 2024)}-{random.randint(1,12):02d}-01",
            })
            player_id += 1

    return players


# ---------------------------------------------------------------------------
# Assign MVP player IDs to completed matches
# ---------------------------------------------------------------------------

def assign_mvps(matches, players):
    """Assign MVP to completed matches from players on participating teams."""
    team_players = {}
    for p in players:
        team_players.setdefault(p["team_id"], []).append(p["id"])

    for m in matches:
        if m["status"] != "completed":
            continue
        candidates = team_players.get(m["home_team_id"], []) + team_players.get(m["away_team_id"], [])
        if candidates:
            m["mvp_player_id"] = random.choice(candidates)


# ---------------------------------------------------------------------------
# Synthesize users
# ---------------------------------------------------------------------------

def generate_users(teams, players, leagues, matches):
    """Generate 5 synthetic users with reasonable following/saved data."""
    user_data = [
        ("sports_fanatic", "Alex Rodriguez", "alex.r@example.com"),
        ("esports_guru", "Min-ji Kim", "minji.k@example.com"),
        ("footy_lover", "James Wilson", "james.w@example.com"),
        ("val_watcher", "Sofia Chen", "sofia.c@example.com"),
        ("all_sports", "David Okafor", "david.o@example.com"),
    ]

    team_ids = [t["id"] for t in teams]
    player_ids = [p["id"] for p in players]
    league_ids = [lg["id"] for lg in leagues]
    match_ids = [m["id"] for m in matches if m["status"] == "completed"]

    users = []
    for i, (uname, name, email) in enumerate(user_data, 1):
        users.append({
            "id": i,
            "username": uname,
            "name": name,
            "email": email,
            "following_teams": random.sample(team_ids, min(random.randint(1, 3), len(team_ids))),
            "following_players": random.sample(player_ids, min(random.randint(1, 3), len(player_ids))),
            "subscribed_leagues": random.sample(league_ids, min(random.randint(1, 2), len(league_ids))),
            "saved_matches": random.sample(match_ids, min(random.randint(1, 3), len(match_ids))),
            "predictions": {},
        })

    return users


# ---------------------------------------------------------------------------
# Synthesize comments
# ---------------------------------------------------------------------------

def generate_comments(matches, users):
    """Generate ~25 comments on completed matches."""
    completed = [m for m in matches if m["status"] == "completed"]
    if not completed:
        return []

    comment_templates = [
        "What an incredible match! The performance was outstanding.",
        "Disappointing result, expected much better from the team.",
        "MVP absolutely deserved it tonight. Dominant display!",
        "Best match of the season so far, edge-of-the-seat stuff.",
        "Defense was rock solid today, well deserved clean sheet.",
        "That second-half comeback was unbelievable!",
        "Can't believe we lost that, we had so many chances.",
        "Brilliant teamwork on display. Loved every minute.",
        "The crowd atmosphere was electric, wish I was there!",
        "Tactical masterclass from the coach today.",
        "Controversial refereeing decisions ruined the match.",
        "Young players stepping up when it matters most.",
        "What a rivalry! These two teams always deliver.",
        "Heartbreaking loss, but we'll come back stronger.",
        "Absolutely clinical finishing in front of goal.",
        "The stats don't lie — total domination.",
        "Great to see the veterans still performing at this level.",
        "This league is so competitive this season!",
        "Underdog story of the year right there.",
        "Peak entertainment! Sports at its finest.",
        "That last-minute winner sent me through the roof!",
        "Both teams played their hearts out today.",
        "Record-breaking performance, one for the history books.",
        "The atmosphere in that stadium must have been insane.",
        "Looking forward to the rematch already!",
    ]

    user_ids = [u["id"] for u in users]
    comments = []
    selected_matches = random.sample(completed, min(15, len(completed)))

    for i in range(25):
        match = random.choice(selected_matches)
        parent = None
        if i > 5 and random.random() < 0.2 and comments:
            # Reply to an existing comment on the same match
            same_match_comments = [c for c in comments if c["match_id"] == match["id"]]
            if same_match_comments:
                parent = random.choice(same_match_comments)["id"]

        match_date = datetime.strptime(match["date"], "%Y-%m-%d")
        comment_time = match_date + timedelta(hours=random.randint(1, 5), minutes=random.randint(0, 59))

        comments.append({
            "id": i + 1,
            "match_id": match["id"],
            "user_id": random.choice(user_ids),
            "text": comment_templates[i % len(comment_templates)],
            "created": comment_time.strftime("%Y-%m-%dT%H:%M:%S"),
            "likes": random.randint(0, 35),
            "parent_id": parent,
        })

    return comments


# ---------------------------------------------------------------------------
# Clean internal fields before saving
# ---------------------------------------------------------------------------

def clean(records):
    """Remove internal fields (prefixed with _) before saving."""
    for r in records:
        for key in list(r.keys()):
            if key.startswith("_"):
                del r[key]
    return records


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    random.seed(42)
    print("=" * 60)
    print("Sports & Esports Data Preparation")
    print("=" * 60)

    print("\n[1/6] Fetching leagues...")
    leagues = fetch_leagues()
    print(f"  -> {len(leagues)} leagues")

    print("\n[2/6] Fetching teams...")
    teams = fetch_teams(leagues)
    print(f"  -> {len(teams)} teams")

    print("\n[3/6] Fetching matches (target ~200)...")
    matches = fetch_matches(leagues, teams)
    print(f"  -> {len(matches)} matches")

    print("\n[4/6] Generating players...")
    players = generate_players(teams)
    print(f"  -> {len(players)} players")

    print("\n[5/6] Assigning MVPs and generating users/comments...")
    assign_mvps(matches, players)
    users = generate_users(teams, players, leagues, matches)
    comments = generate_comments(matches, users)

    print("\n[6/6] Writing data files...")
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    save("leagues.json", clean(leagues))
    save("teams.json", clean(teams))
    save("players.json", clean(players))
    save("matches.json", clean(matches))
    save("users.json", users)
    save("comments.json", comments)

    # Summary
    print("\n" + "=" * 60)
    print("Summary:")
    print(f"  Leagues:  {len(leagues)}")
    print(f"  Teams:    {len(teams)}")
    print(f"  Players:  {len(players)}")
    print(f"  Matches:  {len(matches)}")
    print(f"  Users:    {len(users)}")
    print(f"  Comments: {len(comments)}")
    print(f"\nAll files written to: {DATA_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
