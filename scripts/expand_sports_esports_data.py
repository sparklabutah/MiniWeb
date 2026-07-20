"""Expand sports-esports (Lakeport Sports Hub) base data.

The hub ships with 6 leagues / 20 teams / 25 players / 30 matches, which makes
the standings, players, and league schedule pages nearly empty. Adds 10 new
leagues (hockey, WNBA-style basketball, regional soccer, volleyball, college
football, regional baseball, a second esports circuit, rugby, lacrosse, and a
basketball development league) with 16 teams each, sport-appropriate rosters,
and a full season of matches per league, plus extra hub users and their
favorites. All data is deterministic (seeded RNG) and Lakeport/Meridian/
Cascadia branded.

Constraint safety (annotation tasks must keep their answers):
- No rows in existing leagues are touched. NFL (id 1) and MLB (id 3) get no
  new teams, so "top 2 NFL teams" stays Stallions/Wolves and the MLB leader
  stays Lakeport Mariners 52-34 (.605).
- Standings/wins/losses are stored on the teams table and never derived from
  matches; new matches also only reference NEW teams in NEW leagues.
- New final matches are dated before 2026-06-24 and new scheduled matches
  after 2026-07-01 so the homepage "recent" / "upcoming" top-6 are unchanged.
- Only 4 new "live" matches (homepage renders all live matches).
- Players total kept < 500 because /players renders the full list.

Insert-only; inserted ids recorded under data/backups/ for rollback.

Usage: ~/.conda/envs/miniweb/bin/python scripts/expand_sports_esports_data.py [--dry-run]
"""
import json
import random
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "trimmed_miniweb.db"
rng = random.Random(2026)

# --------------------------------------------------------------------------
# New leagues (ids assigned after existing max). Existing leagues 1-6 are
# never touched.
# --------------------------------------------------------------------------
NEW_LEAGUES = [
    # name, sport, season, status, abbreviation, country
    ("National Hockey League", "Hockey", "2025-2026", "active", "NHL", "USA"),
    ("Women's National Basketball Association", "Basketball", "2026", "active", "WNBA", "USA"),
    ("Cascadia Premier Soccer League", "Soccer", "2026", "active", "CPSL", "USA"),
    ("Meridian Volleyball League", "Volleyball", "2026", "active", "MVL", "USA"),
    ("National Collegiate Football Conference", "Football", "2025-2026", "active", "NCFC", "USA"),
    ("Lakeport Regional Baseball League", "Baseball", "2026", "active", "LRBL", "USA"),
    ("Meridian Esports Circuit", "Esports", "Summer 2026", "active", "MEC", "USA"),
    ("Cascadia Rugby Union", "Rugby", "2026", "active", "CRU", "USA"),
    ("National Lacrosse Association", "Lacrosse", "2026", "active", "NLA", "USA"),
    ("Meridian Basketball Development League", "Basketball", "2026", "active", "MBDL", "USA"),
]

TEAMS_PER_LEAGUE = 16
MATCHES_PER_LEAGUE = 440       # league page renders teams + all matches (< ~500 rows)
PLAYER_BUDGET = 455            # /players renders everything; 25 existing + 455 = 480

CITIES = [
    "Lakeport", "Clearwater", "Ridgewood", "Bayview", "Oakdale", "Summit City",
    "Pinecrest", "Bridgewater", "Harbor City", "Riverside", "Meridian",
    "Cascadia Falls", "Cedar Grove", "Maplewood", "Stonebridge", "Fairhaven",
    "Brookfield", "Ashford", "Westport", "Elmwood", "Northgate", "Silverlake",
    "Granite Bay", "Willow Creek", "Eastvale", "Kingsford", "Port Meridian",
    "Highwater", "Redcliff", "Thornton",
]

MASCOTS = [
    "Ice Wolves", "Glaciers", "Frostbite", "Polar Kings", "Avalanche", "Yetis",
    "Blizzards", "Sabres", "Storm", "Falcons", "Comets", "Chargers", "Titans",
    "Raptors", "Pioneers", "Voyagers", "Sentinels", "Guardians", "Monarchs",
    "Admirals", "Mustangs", "Broncos", "Grizzlies", "Wolverines", "Badgers",
    "Otters", "Herons", "Ospreys", "Kestrels", "Condors", "Vikings",
    "Highlanders", "Rangers", "Rovers", "Athletic", "City FC", "Wanderers",
    "Spikers", "Aces", "Setters", "Smash", "Blockers", "Miners", "Lumberjacks",
    "Steelheads", "Anchors", "Mariners United", "Cutters", "Sawyers", "Foxes",
    "Lynx", "Cobras", "Pythons", "Scorpions", "Hornets", "Wasps", "Firebirds",
    "Dragons", "Griffins", "Krakens", "Leviathans", "Tempest", "Cyclones",
    "Twisters", "Quakes", "Rapids", "Cascades", "Summit", "Peaks", "Ridge Runners",
    "Trailblazers", "Prospectors", "Stampede", "Bison", "Elk", "Moose",
    "Timberwolves", "Night Owls", "Ravens", "Crows", "Magpies", "Jays",
    "Pixels", "Glitchers", "Overclockers", "Mainframes", "Circuits", "Renderers",
    "Spartans", "Gladiators", "Centurions", "Legion", "Warhawks", "Jets",
    "Rockets", "Astros United", "Novas", "Pulsars", "Quasars", "Meteors",
    "Scrummers", "Mauls", "Lions", "Tigers", "Panthers", "Jaguars", "Cheetahs",
    "Laxers", "Sticks", "Netminders", "Riptide", "Surge", "Breakers",
]

VENUE_TYPES = {
    "Hockey": ["Ice Center", "Arena", "Coliseum"],
    "Basketball": ["Arena", "Center", "Fieldhouse"],
    "Soccer": ["Soccer Park", "Stadium", "Pitch"],
    "Volleyball": ["Pavilion", "Gymnasium", "Center"],
    "Football": ["Stadium", "Field", "Bowl"],
    "Baseball": ["Ballpark", "Diamond", "Field"],
    "Esports": ["Esports Center", "Gaming Hall", "Arena"],
    "Rugby": ["Rugby Ground", "Stadium", "Park"],
    "Lacrosse": ["Lacrosse Complex", "Stadium", "Field"],
}

LOGO_COLORS = [
    "#1a3c6e", "#5c2d91", "#c0392b", "#f39c12", "#2ecc71", "#e67e22",
    "#e74c3c", "#0e6655", "#2c3e50", "#27ae60", "#3498db", "#8e44ad",
    "#9b59b6", "#1abc9c", "#34495e", "#d35400", "#16a085", "#7f8c8d",
    "#2980b9", "#8d6e63", "#00695c", "#4527a0", "#ad1457", "#f1c40f",
]

# games played per new league (mid/late season snapshots)
LEAGUE_GAMES = {
    "NHL": 62, "WNBA": 28, "CPSL": 20, "MVL": 24, "NCFC": 11,
    "LRBL": 78, "MEC": 18, "CRU": 14, "NLA": 16, "MBDL": 30,
}

POSITIONS = {
    "Hockey": ["Goaltender", "Defenseman", "Center", "Left Wing", "Right Wing"],
    "Basketball": ["Point Guard", "Shooting Guard", "Small Forward",
                   "Power Forward", "Center"],
    "Soccer": ["Goalkeeper", "Defender", "Midfielder", "Winger", "Striker"],
    "Volleyball": ["Setter", "Outside Hitter", "Middle Blocker", "Opposite",
                   "Libero"],
    "Football": ["Quarterback", "Running Back", "Wide Receiver", "Tight End",
                 "Linebacker", "Cornerback", "Safety", "Kicker"],
    "Baseball": ["Pitcher", "Catcher", "First Base", "Shortstop", "Third Base",
                 "Outfielder", "Designated Hitter"],
    "Esports": ["Duelist", "In-Game Leader", "Support", "Flex", "Sniper"],
    "Rugby": ["Fly-half", "Scrum-half", "Prop", "Hooker", "Lock", "Wing",
              "Fullback"],
    "Lacrosse": ["Attack", "Midfielder", "Defenseman", "Goalie", "Faceoff Specialist"],
}

FIRST_NAMES = [
    "Marcus", "Jalen", "Tyler", "Andre", "Devon", "Caleb", "Owen", "Liam",
    "Noah", "Ethan", "Mason", "Logan", "Lucas", "Aiden", "Elijah", "Carter",
    "Dylan", "Hunter", "Austin", "Blake", "Cole", "Chase", "Grant", "Reid",
    "Sofia", "Maya", "Ava", "Isla", "Zoe", "Nora", "Elena", "Camila",
    "Aaliyah", "Brianna", "Destiny", "Jasmine", "Kayla", "Alexis", "Morgan",
    "Taylor", "Jordan", "Casey", "Riley", "Quinn", "Avery", "Peyton",
    "Diego", "Mateo", "Santiago", "Rafael", "Luis", "Javier", "Emilio",
    "Kenji", "Hiro", "Daiki", "Minho", "Jisung", "Wei", "Ling", "Ravi",
    "Arjun", "Nikolai", "Dmitri", "Stefan", "Luka", "Mateus", "Thiago",
]
LAST_NAMES = [
    "Rivera", "Carter", "Morrison", "Nguyen", "Thomas", "Williams", "Johnson",
    "Brooks", "Hayes", "Coleman", "Sanders", "Bennett", "Fisher", "Sullivan",
    "Reyes", "Mendoza", "Castillo", "Vargas", "Romero", "Delgado", "Ortiz",
    "Kim", "Park", "Choi", "Tanaka", "Sato", "Yamamoto", "Chen", "Wang",
    "Patel", "Singh", "Petrov", "Ivanov", "Novak", "Kovac", "Silva", "Santos",
    "Okafor", "Adeyemi", "Mensah", "Diallo", "Keita", "Toure", "Osei",
    "Lindqvist", "Johansson", "Virtanen", "Nieminen", "Laine", "Kucera",
    "Dubois", "Moreau", "Fontaine", "Girard", "Lambert", "Rousseau",
]

GAMER_TAGS = [
    "Vortex", "Spectre", "Nova", "Havoc", "Zenith", "Cipher", "Rogue", "Blitz",
    "Phantom", "Onyx", "Static", "Echo", "Raze", "Drift", "Fuse", "Glitch",
    "Pulse", "Shade", "Frost", "Ember", "Talon", "Viper", "Wraith", "Apex",
]


def _stats_for(sport, position, r):
    if sport == "Hockey":
        if position == "Goaltender":
            return {"save_pct": round(r.uniform(0.890, 0.935), 3),
                    "goals_against_avg": round(r.uniform(2.1, 3.4), 2),
                    "shutouts": r.randint(0, 6), "wins": r.randint(8, 34)}
        return {"goals": r.randint(2, 44), "assists": r.randint(5, 58),
                "plus_minus": r.randint(-18, 32),
                "penalty_minutes": r.randint(6, 90)}
    if sport == "Basketball":
        return {"points_per_game": round(r.uniform(4.5, 29.5), 1),
                "rebounds_per_game": round(r.uniform(1.5, 12.8), 1),
                "assists_per_game": round(r.uniform(0.8, 9.6), 1),
                "field_goal_pct": round(r.uniform(0.398, 0.612), 3)}
    if sport == "Soccer":
        if position == "Goalkeeper":
            return {"clean_sheets": r.randint(2, 12), "saves": r.randint(28, 96),
                    "goals_conceded": r.randint(8, 34),
                    "save_pct": round(r.uniform(0.62, 0.82), 2)}
        return {"goals": r.randint(0, 19), "assists": r.randint(0, 13),
                "appearances": r.randint(8, 20),
                "pass_accuracy": round(r.uniform(0.71, 0.92), 2)}
    if sport == "Volleyball":
        if position == "Setter":
            return {"assists": r.randint(280, 720), "aces": r.randint(8, 40),
                    "digs": r.randint(90, 260), "sets_played": r.randint(50, 90)}
        if position == "Libero":
            return {"digs": r.randint(220, 480), "receptions": r.randint(180, 420),
                    "aces": r.randint(4, 22), "sets_played": r.randint(50, 90)}
        return {"kills": r.randint(120, 420), "blocks": r.randint(18, 110),
                "aces": r.randint(6, 38), "hitting_pct": round(r.uniform(0.180, 0.360), 3)}
    if sport == "Football":
        if position == "Quarterback":
            return {"passing_yards": r.randint(1400, 4100), "touchdowns": r.randint(9, 32),
                    "interceptions": r.randint(2, 14),
                    "passer_rating": round(r.uniform(72.0, 112.0), 1)}
        if position == "Running Back":
            return {"rushing_yards": r.randint(320, 1350), "touchdowns": r.randint(2, 14),
                    "fumbles": r.randint(0, 4), "yards_per_carry": round(r.uniform(3.4, 5.6), 1)}
        if position in ("Wide Receiver", "Tight End"):
            return {"receptions": r.randint(18, 88), "receiving_yards": r.randint(210, 1240),
                    "touchdowns": r.randint(1, 12), "yards_per_catch": round(r.uniform(8.5, 17.8), 1)}
        if position == "Kicker":
            return {"field_goals_made": r.randint(9, 28), "field_goals_att": r.randint(12, 32),
                    "long": r.randint(44, 58), "points": r.randint(40, 130)}
        return {"tackles": r.randint(28, 110), "sacks": round(r.uniform(0, 12.5), 1),
                "forced_fumbles": r.randint(0, 4), "interceptions": r.randint(0, 5)}
    if sport == "Baseball":
        if position == "Pitcher":
            return {"era": round(r.uniform(2.40, 5.30), 2), "wins": r.randint(2, 15),
                    "strikeouts": r.randint(40, 190), "whip": round(r.uniform(1.02, 1.48), 2)}
        return {"batting_avg": round(r.uniform(0.218, 0.327), 3),
                "home_runs": r.randint(2, 34), "rbi": r.randint(14, 96),
                "stolen_bases": r.randint(0, 28)}
    if sport == "Esports":
        return {"kda": round(r.uniform(0.82, 1.95), 2),
                "avg_combat_score": r.randint(160, 295),
                "headshot_pct": round(r.uniform(0.14, 0.34), 2),
                "maps_played": r.randint(24, 60)}
    if sport == "Rugby":
        return {"tries": r.randint(0, 14), "tackles": r.randint(40, 180),
                "meters_carried": r.randint(120, 980), "turnovers_won": r.randint(1, 18)}
    # Lacrosse
    if position == "Goalie":
        return {"saves": r.randint(80, 220), "save_pct": round(r.uniform(0.46, 0.60), 2),
                "goals_against_avg": round(r.uniform(8.5, 13.5), 1), "wins": r.randint(3, 12)}
    return {"goals": r.randint(4, 48), "assists": r.randint(2, 34),
            "ground_balls": r.randint(10, 90), "shooting_pct": round(r.uniform(0.22, 0.42), 2)}


def _score_for(sport, r):
    return {
        "Hockey": lambda: (r.randint(0, 6), r.randint(0, 6)),
        "Basketball": lambda: (r.randint(74, 126), r.randint(74, 126)),
        "Soccer": lambda: (r.randint(0, 4), r.randint(0, 4)),
        "Volleyball": lambda: r.choice([(3, 0), (3, 1), (3, 2), (0, 3), (1, 3), (2, 3)]),
        "Football": lambda: (r.choice([3, 7, 10, 13, 14, 17, 20, 21, 24, 27, 28, 31, 35, 38, 42]),
                             r.choice([0, 3, 6, 7, 10, 13, 14, 16, 17, 20, 21, 24, 27, 31, 35])),
        "Baseball": lambda: (r.randint(0, 11), r.randint(0, 11)),
        "Esports": lambda: r.choice([(2, 0), (2, 1), (0, 2), (1, 2), (3, 1), (3, 2), (1, 3), (2, 3)]),
        "Rugby": lambda: (r.randint(7, 45), r.randint(3, 38)),
        "Lacrosse": lambda: (r.randint(5, 18), r.randint(4, 17)),
    }[sport]()


LIVE_STATE = {
    "Hockey": ("P2", "12:35"), "Rugby": ("H2", "23:10"),
    "Esports": ("Map 2", ""), "Volleyball": ("Set 3", ""),
}


def main():
    dry = "--dry-run" in sys.argv
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.row_factory = sqlite3.Row

    next_league = db.execute("SELECT MAX(id)+1 FROM sports_esports_leagues").fetchone()[0]
    next_team = db.execute("SELECT MAX(id)+1 FROM sports_esports_teams").fetchone()[0]
    next_player = db.execute("SELECT MAX(id)+1 FROM sports_esports_players").fetchone()[0]
    next_match = db.execute("SELECT MAX(id)+1 FROM sports_esports_matches").fetchone()[0]
    next_user = db.execute("SELECT MAX(id)+1 FROM sports_esports_users").fetchone()[0]
    next_fav = db.execute("SELECT MAX(id)+1 FROM sports_esports_favorites").fetchone()[0]

    used_team_names = {r[0] for r in db.execute("SELECT name FROM sports_esports_teams")}
    used_abbrs = {r[0] for r in db.execute("SELECT abbreviation FROM sports_esports_teams")}
    used_player_names = {r[0] for r in db.execute("SELECT name FROM sports_esports_players")}
    used_usernames = {r[0] for r in db.execute("SELECT username FROM sports_esports_users")}

    leagues_new, teams_new, players_new, matches_new = [], [], [], []
    users_new, favs_new = [], []

    mascot_pool = list(MASCOTS)
    rng.shuffle(mascot_pool)
    mi = 0

    def _abbr(city, mascot):
        base = (city[0] + mascot.replace(" ", "")[:2]).upper()
        cands = [base,
                 (city[:2] + mascot[0]).upper().replace(" ", "")[:3],
                 (city[0] + mascot[0] + mascot[-1]).upper()]
        for c in cands:
            if len(c) == 3 and c not in used_abbrs:
                return c
        while True:
            c = (city[0] + mascot[0] + rng.choice("ABCDEFGHJKLMNPRSTUVWXYZ")).upper()
            if c not in used_abbrs:
                return c

    for li, (lname, sport, season, status, labbr, country) in enumerate(NEW_LEAGUES):
        league_id = next_league + li
        leagues_new.append({"id": league_id, "name": lname, "sport": sport,
                            "season": season, "status": status,
                            "abbreviation": labbr, "country": country})

        games = LEAGUE_GAMES[labbr]
        # win totals descending, consistent with standing
        win_list = sorted({min(games - 1, max(1, round(games * (0.78 - 0.052 * k) + rng.randint(-1, 1))))
                           for k in range(TEAMS_PER_LEAGUE * 2)}, reverse=True)
        while len(win_list) < TEAMS_PER_LEAGUE:
            win_list.append(max(1, win_list[-1] - 1))
        win_list = win_list[:TEAMS_PER_LEAGUE]

        league_teams = []
        for st in range(1, TEAMS_PER_LEAGUE + 1):
            city = rng.choice(CITIES)
            for _ in range(200):
                mascot = mascot_pool[mi % len(mascot_pool)]
                mi += 1
                name = f"{city} {mascot}"
                if name not in used_team_names:
                    break
                city = rng.choice(CITIES)
            used_team_names.add(name)
            abbr = _abbr(city, mascot)
            used_abbrs.add(abbr)
            wins = win_list[st - 1]
            team = {"id": next_team, "league_id": league_id, "name": name,
                    "city": city, "abbreviation": abbr, "wins": wins,
                    "losses": games - wins, "standing": st,
                    "logo_color": rng.choice(LOGO_COLORS)}
            next_team += 1
            teams_new.append(team)
            league_teams.append(team)

        # venues: one home venue per team
        venues = {t["id"]: f"{t['city']} {rng.choice(VENUE_TYPES[sport])}"
                  for t in league_teams}

        # matches: mostly finals in the past, some scheduled in the future,
        # at most one live per selected league
        n_live = 1 if labbr in ("NHL", "MVL", "MEC", "CRU") else 0
        n_sched = 39 if n_live else 40
        n_final = MATCHES_PER_LEAGUE - n_sched - n_live

        def _pair():
            home, away = rng.sample(league_teams, 2)
            return home, away

        # final dates: 2025-08-01 .. 2026-06-23 (older than existing finals)
        import datetime
        f_start = datetime.date(2025, 8, 1)
        f_days = (datetime.date(2026, 6, 23) - f_start).days
        for _ in range(n_final):
            home, away = _pair()
            d = f_start + datetime.timedelta(days=rng.randint(0, f_days))
            hs, as_ = _score_for(sport, rng)
            matches_new.append({
                "id": next_match, "league_id": league_id,
                "home_team_id": home["id"], "away_team_id": away["id"],
                "date": d.isoformat(),
                "time": rng.choice(["12:00", "13:00", "15:00", "17:00", "18:00",
                                    "19:00", "19:30", "20:00", "21:00"]),
                "venue": venues[home["id"]], "status": "final",
                "home_score": hs, "away_score": as_, "quarter": "", "clock": ""})
            next_match += 1

        # scheduled: 2026-07-02 .. 2026-08-20 (after existing upcoming window)
        s_start = datetime.date(2026, 7, 2)
        for _ in range(n_sched):
            home, away = _pair()
            d = s_start + datetime.timedelta(days=rng.randint(0, 49))
            matches_new.append({
                "id": next_match, "league_id": league_id,
                "home_team_id": home["id"], "away_team_id": away["id"],
                "date": d.isoformat(),
                "time": rng.choice(["13:00", "15:00", "17:00", "18:00", "19:00",
                                    "19:30", "20:00"]),
                "venue": venues[home["id"]], "status": "scheduled",
                "home_score": 0, "away_score": 0, "quarter": "", "clock": ""})
            next_match += 1

        if n_live:
            home, away = _pair()
            hs, as_ = _score_for(sport, rng)
            quarter, clock = LIVE_STATE[sport]
            matches_new.append({
                "id": next_match, "league_id": league_id,
                "home_team_id": home["id"], "away_team_id": away["id"],
                "date": "2026-06-27", "time": rng.choice(["18:30", "19:00", "20:30"]),
                "venue": venues[home["id"]], "status": "live",
                "home_score": min(hs, as_ + rng.randint(0, 2)), "away_score": as_,
                "quarter": quarter, "clock": clock})
            next_match += 1

    # players: 2-4 per new team until the budget is exhausted
    all_new_team_ids = []
    for team in teams_new:
        if len(players_new) >= PLAYER_BUDGET:
            break
        sport = next(l["sport"] for l in leagues_new if l["id"] == team["league_id"])
        roster = min(rng.randint(2, 4), PLAYER_BUDGET - len(players_new))
        used_numbers = set()
        for _ in range(roster):
            for _ in range(300):
                if sport == "Esports":
                    name = f"{rng.choice(FIRST_NAMES)} '{rng.choice(GAMER_TAGS)}' {rng.choice(LAST_NAMES)}"
                else:
                    name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
                if name not in used_player_names:
                    break
            used_player_names.add(name)
            pos = rng.choice(POSITIONS[sport])
            while True:
                num = rng.randint(0, 99)
                if num not in used_numbers:
                    used_numbers.add(num)
                    break
            players_new.append({
                "id": next_player, "team_id": team["id"], "name": name,
                "position": pos, "jersey_number": num,
                "stats": json.dumps(_stats_for(sport, pos, rng))})
            next_player += 1
        all_new_team_ids.append(team["id"])

    # users + favorites (never touching user 1 / mike_chen)
    sports_cycle = [l["sport"] for l in leagues_new]
    for i in range(30):
        for _ in range(300):
            fn, ln = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
            username = f"{fn.lower()}_{ln.lower()}"
            if username not in used_usernames:
                break
        used_usernames.add(username)
        word = rng.choice(["slapshot", "fastbreak", "corner", "spike", "blitz",
                           "homer", "clutch", "ruck", "faceoff", "crossover"])
        users_new.append({
            "id": next_user, "username": username,
            "password": f"{word}{rng.randint(100, 999)}",
            "name": f"{fn} {ln}",
            "email": f"{fn.lower()}.{ln.lower()}@email.com",
            "favorite_sport": sports_cycle[i % len(sports_cycle)]})
        fav_teams = rng.sample([t["id"] for t in teams_new], rng.randint(1, 3))
        fav_players = [p["id"] for p in rng.sample(players_new, rng.randint(1, 4))]
        favs_new.append({"id": next_fav, "user_id": next_user,
                         "team_ids": json.dumps(sorted(fav_teams)),
                         "player_ids": json.dumps(sorted(fav_players))})
        next_user += 1
        next_fav += 1

    print(f"leagues: +{len(leagues_new)}, teams: +{len(teams_new)}, "
          f"players: +{len(players_new)}, matches: +{len(matches_new)}, "
          f"users: +{len(users_new)}, favorites: +{len(favs_new)}")
    if dry:
        for l in leagues_new:
            n_m = sum(1 for m in matches_new if m["league_id"] == l["id"])
            print(f"  {l['abbreviation']}: {TEAMS_PER_LEAGUE} teams, {n_m} matches")
        for t in teams_new[:4]:
            print("  team:", t)
        for m in matches_new[:3]:
            print("  match:", m)
        for p in players_new[:3]:
            print("  player:", p)
        print("  user:", users_new[0])
        print("  fav:", favs_new[0])
        return

    bdir = ROOT / "data" / "backups" / "sports-esports-expansion-2026-07-20"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "inserted_ids.json").write_text(json.dumps({
        "leagues": [l["id"] for l in leagues_new],
        "teams": [t["id"] for t in teams_new],
        "players": [p["id"] for p in players_new],
        "matches": [m["id"] for m in matches_new],
        "users": [u["id"] for u in users_new],
        "favorites": [f["id"] for f in favs_new]}, indent=1))

    for table, rows in (("leagues", leagues_new), ("teams", teams_new),
                        ("players", players_new), ("matches", matches_new),
                        ("users", users_new), ("favorites", favs_new)):
        if not rows:
            continue
        cols = list(rows[0].keys())
        db.executemany(
            f"INSERT INTO sports_esports_{table} ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' * len(cols))})",
            [[r[c] for c in cols] for r in rows])

    # rebuild FTS indexes for the content tables we touched
    for fts in ("fts_sports_esports_matches", "fts_sports_esports_players",
                "fts_sports_esports_teams"):
        db.execute(f"INSERT INTO {fts}({fts}) VALUES('rebuild')")
    db.commit()
    print(f"inserted; rollback ids at {bdir}/inserted_ids.json")


if __name__ == "__main__":
    main()
