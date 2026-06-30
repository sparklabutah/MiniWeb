"""Per-task HTTP verification functions for sports-esports."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/sports-esports"
    r = requests.get(f"{base}/league/2")
    ok = r.status_code == 200 and "National Basketball Association" in r.text
    return {"pass": ok, "detail": f"NBA league page: status={r.status_code}"}


def verify_002(server_url):
    base = f"{server_url}/sites/sports-esports"
    r = requests.get(f"{base}/api/teams/1")
    team = r.json()
    wins = team.get("wins", 0)
    losses = team.get("losses", 0)
    ok = wins > 0 and losses >= 0
    return {"pass": ok, "detail": f"Lakeport Stallions: {wins}W-{losses}L"}


def verify_003(server_url):
    base = f"{server_url}/sites/sports-esports"
    r = requests.get(f"{base}/api/standings/1/rank/1")
    team = r.json()
    name = team.get("name", "")
    ok = name == "Lakeport Stallions"
    return {"pass": ok, "detail": f"NFL #1: {name}"}


def verify_004(server_url):
    base = f"{server_url}/sites/sports-esports"
    r = requests.get(f"{base}/api/players?q=Quarterback")
    players = r.json()
    count = len(players)
    ok = count > 0
    return {"pass": ok, "detail": f"Search 'Quarterback': {count} players"}


def verify_005(server_url):
    base = f"{server_url}/sites/sports-esports"
    r = requests.get(f"{base}/api/search?q=Lakeport")
    data = r.json()
    team_count = len(data.get("teams", []))
    ok = team_count > 0
    return {"pass": ok, "detail": f"Semantic 'Lakeport': {team_count} teams"}


def verify_006(server_url):
    base = f"{server_url}/sites/sports-esports"
    r = requests.get(f"{base}/api/players?league_id=2")
    players = r.json()
    count = len(players)
    ok = count > 0
    return {"pass": ok, "detail": f"NBA players: {count}"}


def verify_007(server_url):
    base = f"{server_url}/sites/sports-esports"
    r = requests.get(f"{base}/api/matches?date_from=2026-06-26&date_to=2026-06-27")
    matches = r.json()
    count = len(matches)
    # Verify all are in range
    ok = all(m["date"] >= "2026-06-26" and m["date"] <= "2026-06-27" for m in matches)
    return {"pass": ok and count > 0, "detail": f"June 26-27: {count} matches, all_in_range={ok}"}


def verify_008(server_url):
    base = f"{server_url}/sites/sports-esports"
    r = requests.get(f"{base}/api/teams?sort=wins")
    teams = r.json()
    if not teams:
        return {"pass": False, "detail": "No teams returned"}
    first = teams[0]["name"]
    ok = teams[0]["wins"] >= teams[-1]["wins"]
    return {"pass": ok, "detail": f"Most wins: {first} ({teams[0]['wins']}W)"}


def verify_009(server_url):
    base = f"{server_url}/sites/sports-esports"
    r = requests.get(f"{base}/api/players?q=Guard")
    players = r.json()
    if not players:
        return {"pass": False, "detail": "No players found for 'Guard'"}
    first_name = players[0]["name"]
    return {"pass": len(first_name) > 0, "detail": f"First 'Guard' player: {first_name}"}


def verify_010(server_url):
    base = f"{server_url}/sites/sports-esports"
    r = requests.get(f"{base}/api/standings/2")
    data = r.json()
    standings = data.get("standings", [])
    if not standings:
        return {"pass": False, "detail": "No NBA standings"}
    top = standings[0]
    win_pct = top.get("win_pct", 0)
    ok = top["standing"] == 1
    return {"pass": ok, "detail": f"NBA #1 win_pct: {win_pct}"}


def verify_011(server_url):
    base = f"{server_url}/sites/sports-esports"
    r = requests.get(f"{base}/api/players/1")
    player = r.json()
    position = player.get("position", "")
    ok = position == "Quarterback"
    return {"pass": ok, "detail": f"Player 1 position: {position}"}


def verify_012(server_url):
    base = f"{server_url}/sites/sports-esports"
    r = requests.get(f"{base}/api/teams/extremum?stat=wins&mode=max")
    data = r.json()
    team = data.get("team", {})
    name = team.get("name", "")
    wins = data.get("value", 0)
    ok = wins > 0 and len(name) > 0
    return {"pass": ok, "detail": f"Max wins: {name} with {wins}"}


def verify_013(server_url):
    base = f"{server_url}/sites/sports-esports"
    r = requests.get(f"{base}/api/teams/filter?stat=wins&min=20")
    data = r.json()
    count = data.get("count", 0)
    ok = count > 0
    # Verify all have >= 20 wins
    all_ok = all(t["wins"] >= 20 for t in data.get("teams", []))
    return {"pass": ok and all_ok, "detail": f"Teams with wins>=20: {count}, all_valid={all_ok}"}


def verify_014(server_url):
    base = f"{server_url}/sites/sports-esports"
    r = requests.get(f"{base}/api/standings/5/stats")
    data = r.json()
    avg_wins = data.get("avg_wins", 0)
    ok = avg_wins > 0
    return {"pass": ok, "detail": f"EPL avg wins: {avg_wins}"}


def verify_015(server_url):
    base = f"{server_url}/sites/sports-esports"
    r = requests.get(f"{base}/api/teams/compare?ids=14,15")
    teams = r.json()
    if len(teams) < 2:
        return {"pass": False, "detail": f"Compare returned {len(teams)} teams, expected 2"}
    pcts = [(t["name"], t["win_pct"]) for t in teams]
    higher = max(pcts, key=lambda x: x[1])
    return {"pass": True, "detail": f"Higher win%: {higher[0]} ({higher[1]})"}


def verify_016(server_url):
    base = f"{server_url}/sites/sports-esports"
    r = requests.get(f"{base}/api/teams/1/verify?stat=win_pct&threshold=0.7&op=gte")
    data = r.json()
    result = data.get("result", False)
    value = data.get("value", 0)
    return {"pass": isinstance(result, bool), "detail": f"Stallions win_pct={value}, >=0.700: {result}"}


def verify_017(server_url):
    base = f"{server_url}/sites/sports-esports"
    r = requests.get(f"{base}/api/matches/4/highlights")
    data = r.json()
    available = data.get("available", False)
    return {"pass": available is True, "detail": f"Match 4 highlights available: {available}"}


def verify_018(server_url):
    base = f"{server_url}/sites/sports-esports"
    r = requests.get(f"{base}/api/matches/4/comments")
    comments = r.json()
    ok = any(c.get("text") == "Great game tonight!" for c in comments)
    return {"pass": ok, "detail": f"Comment 'Great game tonight!': found={ok}, total={len(comments)}"}


def verify_019(server_url):
    base = f"{server_url}/sites/sports-esports"
    r = requests.get(f"{base}/api/matches/4/comments")
    comments = r.json()
    target = next((c for c in comments if c.get("text") == "What a play!"), None)
    if not target:
        return {"pass": False, "detail": "Comment 'What a play!' not found"}
    ok = target.get("likes", 0) >= 1
    return {"pass": ok, "detail": f"Comment likes: {target.get('likes', 0)}"}


def verify_020(server_url):
    base = f"{server_url}/sites/sports-esports"
    # Check favorites for user 2 (sarah_lopez) via user-specific API
    r = requests.get(f"{base}/api/users/2/favorites")
    fav = r.json()
    team_ok = 3 in fav.get("team_ids", [])
    player_ok = 10 in fav.get("player_ids", [])

    # Check subscriptions for user 2 via user-specific API
    r2 = requests.get(f"{base}/api/users/2/subscriptions")
    sub = r2.json()
    sub_ok = 1 in sub.get("league_ids", [])

    ok = team_ok and player_ok and sub_ok
    return {
        "pass": ok,
        "detail": f"team3_fav={team_ok}, player10_fav={player_ok}, nfl_sub={sub_ok}"
    }
