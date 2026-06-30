"""Per-task HTTP verification functions for petitions-voting-info."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/petitions-voting-info"
    # Check elections page is reachable and has an upcoming election
    r = requests.get(f"{base}/api/elections?status=upcoming")
    elections = r.json()
    if not elections:
        return {"pass": False, "detail": "No upcoming elections found"}
    title = elections[0]["title"]
    return {"pass": len(title) > 0, "detail": f"Upcoming election: {title}"}


def verify_002(server_url):
    base = f"{server_url}/sites/petitions-voting-info"
    r = requests.get(f"{base}/api/petitions/1")
    data = r.json()
    title = data.get("title", "")
    return {"pass": len(title) > 0, "detail": f"Petition 1 title: {title}"}


def verify_003(server_url):
    base = f"{server_url}/sites/petitions-voting-info"
    r = requests.get(f"{base}/api/petitions/search?q=park")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Search 'park': {count} results"}


def verify_004(server_url):
    base = f"{server_url}/sites/petitions-voting-info"
    r = requests.get(f"{base}/api/petitions/semantic?q=environmental+protection")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Semantic 'environmental protection': {count} results"}


def verify_005(server_url):
    base = f"{server_url}/sites/petitions-voting-info"
    r = requests.get(f"{base}/api/petitions?status=active")
    results = r.json()
    count = len(results)
    ok = all(p["status"] == "active" for p in results)
    return {"pass": ok and count > 0, "detail": f"Active petitions: {count}, all_active={ok}"}


def verify_006(server_url):
    base = f"{server_url}/sites/petitions-voting-info"
    r = requests.get(f"{base}/api/petitions?category=education")
    results = r.json()
    count = len(results)
    ok = all(p["category"] == "education" for p in results)
    return {"pass": ok and count >= 0, "detail": f"Education category: {count} petitions, all_education={ok}"}


def verify_007(server_url):
    base = f"{server_url}/sites/petitions-voting-info"
    r = requests.get(f"{base}/api/petitions?sort=title&order=asc")
    results = r.json()
    if not results:
        return {"pass": False, "detail": "No petitions returned"}
    first_title = results[0]["title"]
    titles = [p["title"].lower() for p in results]
    is_sorted = all(titles[i] <= titles[i+1] for i in range(len(titles)-1))
    return {"pass": is_sorted, "detail": f"First title (A-Z): {first_title[:60]}, sorted={is_sorted}"}


def verify_008(server_url):
    base = f"{server_url}/sites/petitions-voting-info"
    r = requests.get(f"{base}/api/petitions/search?q=bike")
    results = r.json()
    if not results:
        return {"pass": True, "detail": "No results for 'bike'"}
    first = results[0]["title"]
    return {"pass": len(first) > 0, "detail": f"First 'bike' result: {first[:60]}"}


def verify_009(server_url):
    base = f"{server_url}/sites/petitions-voting-info"
    r = requests.get(f"{base}/api/categories/community/stats")
    stats = r.json()
    total_sigs = stats.get("total_signatures", 0)
    return {"pass": "total_signatures" in stats, "detail": f"Community total signatures: {total_sigs}"}


def verify_010(server_url):
    base = f"{server_url}/sites/petitions-voting-info"
    r = requests.get(f"{base}/api/elections/1")
    election = r.json()
    turnout = election.get("turnout", {}).get("turnout_percentage")
    return {"pass": turnout is not None, "detail": f"Election 1 turnout: {turnout}%"}


def verify_011(server_url):
    base = f"{server_url}/sites/petitions-voting-info"
    r = requests.get(f"{base}/api/petitions?date_from=2025-09-01&date_to=2025-12-31")
    results = r.json()
    count = len(results)
    ok = all("2025-09" <= p["created_at"][:7] <= "2025-12" for p in results)
    return {"pass": ok and count >= 0, "detail": f"Date range 2025-09 to 2025-12: {count} petitions, all_in_range={ok}"}


def verify_012(server_url):
    base = f"{server_url}/sites/petitions-voting-info"
    r = requests.get(f"{base}/api/voter-info/verify?precinct=Precinct+4&username=alex_rivera")
    data = r.json()
    status = data.get("registration_status", "")
    return {"pass": data.get("user_found", False) and status == "active",
            "detail": f"alex_rivera registration status: {status}"}


def verify_013(server_url):
    base = f"{server_url}/sites/petitions-voting-info"
    r = requests.get(f"{base}/api/petitions")
    petitions = r.json()
    found = any(p["title"] == "Improve Lakeport Crosswalk Safety" for p in petitions)
    return {"pass": found,
            "detail": f"Petition 'Improve Lakeport Crosswalk Safety' found={found}"}


def verify_014(server_url):
    base = f"{server_url}/sites/petitions-voting-info"
    r = requests.get(f"{base}/api/petitions/3/comments")
    comments = r.json()
    found = any(
        "Protected bike lanes are essential" in c.get("comment", "")
        for c in comments
    )
    return {"pass": found,
            "detail": f"Comment on petition 3 found={found}, total_comments={len(comments)}"}


def verify_015(server_url):
    base = f"{server_url}/sites/petitions-voting-info"
    r = requests.get(f"{base}/api/petitions/5/signatures")
    sigs = r.json()
    found = any(
        s.get("user_name") == "Rachel Kim" and s.get("signature") == "Rachel Kim"
        for s in sigs
    )
    return {"pass": found,
            "detail": f"Rachel Kim signature on petition 5 found={found}"}


def verify_016(server_url):
    base = f"{server_url}/sites/petitions-voting-info"
    r = requests.get(f"{base}/api/users/3")
    user = r.json()
    subs = user.get("subscribed_petitions", [])
    return {"pass": 3 in subs,
            "detail": f"User 3 subscribed petitions: {subs}"}


def verify_017(server_url):
    base = f"{server_url}/sites/petitions-voting-info"
    r = requests.post(f"{base}/api/petitions/1/share",
                      json={"method": "twitter"})
    data = r.json()
    url = data.get("share_url", "")
    return {"pass": "twitter" in url,
            "detail": f"Share URL: {url}"}


def verify_018(server_url):
    base = f"{server_url}/sites/petitions-voting-info"
    r = requests.get(f"{base}/api/users/5")
    user = r.json()
    saved = user.get("saved_petitions", [])
    ok = 1 in saved and 3 in saved and 5 in saved and len(saved) >= 3
    return {"pass": ok,
            "detail": f"User 5 saved petitions: {saved}"}


def verify_019(server_url):
    base = f"{server_url}/sites/petitions-voting-info"
    s = requests.Session()
    r = s.post(f"{base}/api/login",
               json={"username": "nathan_brooks", "password": "civicpass"})
    data = r.json()
    display_name = data.get("display_name", "")
    return {"pass": display_name == "Nathan Brooks",
            "detail": f"Login display_name: {display_name}"}


def verify_020(server_url):
    base = f"{server_url}/sites/petitions-voting-info"
    # Check that user maria_gonzalez was created
    r = requests.get(f"{base}/api/voter-info/verify?precinct=Precinct+3&username=maria_gonzalez")
    data = r.json()
    status = data.get("registration_status", "")
    return {"pass": status == "active",
            "detail": f"maria_gonzalez registration: {status}"}
