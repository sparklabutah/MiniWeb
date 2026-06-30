"""Per-task reference solutions via Flask test client for sports-esports."""
import json


def solve_001(client, base="/sites/sports-esports"):
    r = client.get(f"{base}/league/2")
    # The page contains "National Basketball Association"
    return "National Basketball Association"


def solve_002(client, base="/sites/sports-esports"):
    r = client.get(f"{base}/api/teams/1")
    team = json.loads(r.data)
    return f"{team['wins']}W-{team['losses']}L"


def solve_003(client, base="/sites/sports-esports"):
    r = client.get(f"{base}/api/standings/1/rank/1")
    team = json.loads(r.data)
    return team["name"]


def solve_004(client, base="/sites/sports-esports"):
    r = client.get(f"{base}/api/players?q=Quarterback")
    return str(len(json.loads(r.data)))


def solve_005(client, base="/sites/sports-esports"):
    r = client.get(f"{base}/api/search?q=Lakeport")
    data = json.loads(r.data)
    return str(len(data["teams"]))


def solve_006(client, base="/sites/sports-esports"):
    r = client.get(f"{base}/api/players?league_id=2")
    return str(len(json.loads(r.data)))


def solve_007(client, base="/sites/sports-esports"):
    r = client.get(f"{base}/api/matches?date_from=2026-06-26&date_to=2026-06-27")
    return str(len(json.loads(r.data)))


def solve_008(client, base="/sites/sports-esports"):
    r = client.get(f"{base}/api/teams?sort=wins")
    teams = json.loads(r.data)
    return teams[0]["name"] if teams else ""


def solve_009(client, base="/sites/sports-esports"):
    r = client.get(f"{base}/api/players?q=Guard")
    players = json.loads(r.data)
    return players[0]["name"] if players else "No results"


def solve_010(client, base="/sites/sports-esports"):
    r = client.get(f"{base}/api/standings/2")
    data = json.loads(r.data)
    standings = data["standings"]
    top = standings[0]
    return str(top["win_pct"])


def solve_011(client, base="/sites/sports-esports"):
    r = client.get(f"{base}/api/players/1")
    player = json.loads(r.data)
    return player["position"]


def solve_012(client, base="/sites/sports-esports"):
    r = client.get(f"{base}/api/teams/extremum?stat=wins&mode=max")
    data = json.loads(r.data)
    return f"{data['team']['name']}, {data['value']}"


def solve_013(client, base="/sites/sports-esports"):
    r = client.get(f"{base}/api/teams/filter?stat=wins&min=20")
    data = json.loads(r.data)
    return str(data["count"])


def solve_014(client, base="/sites/sports-esports"):
    r = client.get(f"{base}/api/standings/5/stats")
    data = json.loads(r.data)
    return str(data["avg_wins"])


def solve_015(client, base="/sites/sports-esports"):
    r = client.get(f"{base}/api/teams/compare?ids=14,15")
    teams = json.loads(r.data)
    higher = max(teams, key=lambda t: t["win_pct"])
    return higher["name"]


def solve_016(client, base="/sites/sports-esports"):
    r = client.get(f"{base}/api/teams/1/verify?stat=win_pct&threshold=0.7&op=gte")
    data = json.loads(r.data)
    return str(data["result"])


def solve_017(client, base="/sites/sports-esports"):
    r = client.get(f"{base}/api/matches/4/highlights")
    data = json.loads(r.data)
    return str(data["available"])


def solve_018(client, base="/sites/sports-esports"):
    client.post(f"{base}/api/login",
                json={"username": "mike_chen", "password": "sports123"})
    r = client.post(f"{base}/api/matches/4/comments",
                    json={"text": "Great game tonight!"})
    data = json.loads(r.data)
    return "posted" if data.get("id") else "failed"


def solve_019(client, base="/sites/sports-esports"):
    client.post(f"{base}/api/login",
                json={"username": "mike_chen", "password": "sports123"})
    r = client.post(f"{base}/api/matches/4/comments",
                    json={"text": "What a play!"})
    comment = json.loads(r.data)
    comment_id = comment["id"]
    r2 = client.post(f"{base}/api/comments/{comment_id}/like",
                     json={})
    like_data = json.loads(r2.data)
    return str(like_data["likes"])


def solve_020(client, base="/sites/sports-esports"):
    # Login as sarah_lopez (user 2)
    client.post(f"{base}/api/login",
                json={"username": "sarah_lopez", "password": "goals456"})
    # Add team 3 to favorites
    client.post(f"{base}/api/favorites",
                json={"action": "add", "team_id": 3})
    # Add player 10 to favorites
    client.post(f"{base}/api/favorites",
                json={"action": "add", "player_id": 10})
    # Subscribe to NFL (league 1)
    client.post(f"{base}/api/leagues/1/subscribe",
                json={})
    # Verify
    r = client.get(f"{base}/api/favorites")
    fav = json.loads(r.data)
    r2 = client.get(f"{base}/api/subscriptions")
    sub = json.loads(r2.data)
    team_ok = 3 in fav.get("team_ids", [])
    player_ok = 10 in fav.get("player_ids", [])
    sub_ok = 1 in sub.get("league_ids", [])
    return "done" if (team_ok and player_ok and sub_ok) else "failed"
