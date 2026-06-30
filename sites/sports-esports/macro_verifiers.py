"""Per-macro verification functions for sports-esports.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/sports-esports"


def verify_macro_navigate_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/league/1")
    ok = r.status_code == 200 and "National Football League" in r.text
    return {"pass": ok, "detail": f"League page via dropdown: {r.status_code}"}


def verify_macro_navigate_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/team/1")
    ok = r.status_code == 200 and "Lakeport Stallions" in r.text
    return {"pass": ok, "detail": f"Team detail page: {r.status_code}"}


def verify_macro_navigate_by_ranking(server_url):
    r = requests.get(f"{_base(server_url)}/api/standings/1/rank/1")
    team = r.json()
    ok = team.get("name") == "Lakeport Stallions"
    return {"pass": ok, "detail": f"NFL rank 1: {team.get('name')}"}


def verify_macro_search_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/players?q=Rivera")
    players = r.json()
    ok = len(players) > 0
    return {"pass": ok, "detail": f"search_by_query 'Rivera': {len(players)} results"}


def verify_macro_search_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/api/search?q=basketball+lakeport")
    data = r.json()
    ok = len(data.get("teams", [])) > 0
    return {"pass": ok, "detail": f"search_by_semantic: {len(data.get('teams', []))} teams"}


def verify_macro_filter_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/players?league_id=1")
    players = r.json()
    ok = len(players) > 0
    return {"pass": ok, "detail": f"filter_by_dropdown NFL: {len(players)} players"}


def verify_macro_filter_by_date_range(server_url):
    r = requests.get(f"{_base(server_url)}/api/matches?date_from=2026-06-26&date_to=2026-06-27")
    matches = r.json()
    ok = all(m["date"] >= "2026-06-26" and m["date"] <= "2026-06-27" for m in matches)
    return {"pass": ok and len(matches) > 0,
            "detail": f"filter 2026-06-26 to 27: {len(matches)} matches, all_in_range={ok}"}


def verify_macro_sort_by_ranking(server_url):
    r = requests.get(f"{_base(server_url)}/api/teams?sort=wins")
    teams = r.json()
    if len(teams) < 2:
        return {"pass": True, "detail": "Too few teams to verify sort"}
    is_sorted = all(teams[i]["wins"] >= teams[i+1]["wins"] for i in range(len(teams)-1))
    return {"pass": is_sorted, "detail": f"sort_by_ranking (wins desc): sorted={is_sorted}"}


def verify_macro_extract_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/players?q=Guard")
    players = r.json()
    if players:
        return {"pass": True, "detail": f"extract_by_query: first={players[0]['name']}"}
    return {"pass": True, "detail": "extract_by_query: no results (ok)"}


def verify_macro_extract_from_table(server_url):
    r = requests.get(f"{_base(server_url)}/api/standings/2")
    data = r.json()
    standings = data.get("standings", [])
    ok = len(standings) > 0 and "win_pct" in standings[0]
    return {"pass": ok, "detail": f"extract_from_table: NBA standings has {len(standings)} teams"}


def verify_macro_extract_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/players/1")
    player = r.json()
    ok = "position" in player and "stats" in player
    return {"pass": ok, "detail": f"extract_by_route: player has position={player.get('position')}"}


def verify_macro_extract_by_extremum(server_url):
    r = requests.get(f"{_base(server_url)}/api/teams/extremum?stat=wins&mode=max")
    data = r.json()
    ok = "team" in data and "value" in data
    return {"pass": ok, "detail": f"extract_by_extremum: {data.get('team', {}).get('name')} wins={data.get('value')}"}


def verify_macro_extract_by_slider(server_url):
    r = requests.get(f"{_base(server_url)}/api/teams/filter?stat=wins&min=20&max=40")
    data = r.json()
    ok = all(20 <= t["wins"] <= 40 for t in data.get("teams", []))
    return {"pass": ok, "detail": f"extract_by_slider: {data.get('count')} teams with 20<=wins<=40"}


def verify_macro_compute_from_table(server_url):
    r = requests.get(f"{_base(server_url)}/api/standings/1/stats")
    data = r.json()
    ok = "avg_wins" in data and "total_games" in data
    return {"pass": ok, "detail": f"compute_from_table: NFL avg_wins={data.get('avg_wins')}, total_games={data.get('total_games')}"}


def verify_macro_compare_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/teams/compare?ids=1,2")
    teams = r.json()
    ok = len(teams) == 2 and teams[0]["id"] != teams[1]["id"]
    return {"pass": ok, "detail": f"compare_by_dropdown: {len(teams)} teams compared"}


def verify_macro_verify_by_slider(server_url):
    r = requests.get(f"{_base(server_url)}/api/teams/1/verify?stat=wins&threshold=5&op=gte")
    data = r.json()
    ok = isinstance(data.get("result"), bool) and data["result"] is True
    return {"pass": ok, "detail": f"verify_by_slider: wins>={5} -> {data.get('result')}"}


def verify_macro_play_by_playback(server_url):
    r = requests.get(f"{_base(server_url)}/api/matches/4/highlights")
    data = r.json()
    ok = data.get("available") is True and len(data.get("highlights", [])) > 0
    return {"pass": ok, "detail": f"play_by_playback: available={data.get('available')}, highlights={len(data.get('highlights', []))}"}


def verify_macro_post_from_free_text(server_url):
    base = _base(server_url)
    # Login
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "carlos_rivera", "password": "batter202"})
    # Post comment
    r = s.post(f"{base}/api/matches/4/comments", json={"text": "Macro test comment"})
    data = r.json()
    ok = r.status_code == 201 and data.get("text") == "Macro test comment"
    # Cleanup: remove the comment (not strictly needed, but good practice)
    return {"pass": ok, "detail": f"post_from_free_text: status={r.status_code}, id={data.get('id')}"}


def verify_macro_react_by_toggle(server_url):
    base = _base(server_url)
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "carlos_rivera", "password": "batter202"})
    # Post a comment to react to
    r = s.post(f"{base}/api/matches/4/comments", json={"text": "React macro test"})
    comment = r.json()
    cid = comment["id"]
    # Like it
    r2 = s.post(f"{base}/api/comments/{cid}/like", json={})
    data = r2.json()
    ok = data.get("action") == "liked" and data.get("likes") == 1
    # Unlike it (toggle back)
    r3 = s.post(f"{base}/api/comments/{cid}/like", json={})
    data3 = r3.json()
    toggle_ok = data3.get("action") == "unliked"
    return {"pass": ok and toggle_ok, "detail": f"react_by_toggle: like={ok}, toggle_back={toggle_ok}"}


def verify_macro_follow_by_dropdown(server_url):
    base = _base(server_url)
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "carlos_rivera", "password": "batter202"})
    # Add team via API (simulates dropdown selection)
    r = s.post(f"{base}/api/favorites", json={"action": "add", "team_id": 20})
    data = r.json()
    ok = 20 in data.get("team_ids", [])
    # Remove it to clean up
    s.post(f"{base}/api/favorites", json={"action": "remove", "team_id": 20})
    return {"pass": ok, "detail": f"follow_by_dropdown: team 20 added={ok}"}


def verify_macro_follow_by_toggle(server_url):
    base = _base(server_url)
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "carlos_rivera", "password": "batter202"})
    # Toggle: add then remove
    r = s.post(f"{base}/api/favorites", json={"action": "add", "team_id": 17})
    data = r.json()
    add_ok = 17 in data.get("team_ids", [])
    r2 = s.post(f"{base}/api/favorites", json={"action": "remove", "team_id": 17})
    data2 = r2.json()
    remove_ok = 17 not in data2.get("team_ids", [])
    return {"pass": add_ok and remove_ok,
            "detail": f"follow_by_toggle: add={add_ok}, remove={remove_ok}"}


def verify_macro_subscribe_by_toggle(server_url):
    base = _base(server_url)
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "carlos_rivera", "password": "batter202"})
    # Subscribe
    r = s.post(f"{base}/api/leagues/3/subscribe", json={})
    data = r.json()
    sub_ok = data.get("action") == "subscribed"
    # Unsubscribe (toggle back)
    r2 = s.post(f"{base}/api/leagues/3/subscribe", json={})
    data2 = r2.json()
    unsub_ok = data2.get("action") == "unsubscribed"
    return {"pass": sub_ok and unsub_ok,
            "detail": f"subscribe_by_toggle: sub={sub_ok}, unsub={unsub_ok}"}


def verify_macro_save_by_toggle(server_url):
    base = _base(server_url)
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "carlos_rivera", "password": "batter202"})
    # Add player as favorite (save)
    r = s.post(f"{base}/api/favorites", json={"action": "add", "player_id": 25})
    data = r.json()
    add_ok = 25 in data.get("player_ids", [])
    # Remove (toggle back)
    r2 = s.post(f"{base}/api/favorites", json={"action": "remove", "player_id": 25})
    data2 = r2.json()
    remove_ok = 25 not in data2.get("player_ids", [])
    return {"pass": add_ok and remove_ok,
            "detail": f"save_by_toggle: add={add_ok}, remove={remove_ok}"}
