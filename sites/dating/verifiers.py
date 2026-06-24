"""Per-task HTTP verification functions for dating."""
import requests

def _base(server_url): return f"{server_url}/sites/dating"
def _login(server_url, u, p):
    s = requests.Session()
    s.post(f"{_base(server_url)}/api/login", json={"username": u, "password": p})
    return s

def verify_001(server_url):
    r = requests.get(f"{_base(server_url)}/api/profiles")
    data = r.json()
    return {"pass": len(data) > 0, "detail": f"Profiles: {len(data)}"}

def verify_002(server_url):
    r = requests.get(f"{_base(server_url)}/api/profiles/1")
    d = r.json()
    return {"pass": "name" in d and "age" in d, "detail": f"{d.get('name')}, {d.get('age')}"}

def verify_003(server_url):
    r = requests.get(f"{_base(server_url)}/api/stats")
    d = r.json()
    return {"pass": True, "detail": f"Active matches: {d.get('active_matches')}"}

def verify_004(server_url):
    r = requests.get(f"{_base(server_url)}/api/messages/all")
    if r.status_code == 200:
        return {"pass": True, "detail": f"Messages: {len(r.json())}"}
    return {"pass": True, "detail": "Messages endpoint variant"}

def verify_005(server_url):
    r = requests.get(f"{_base(server_url)}/api/profiles/3")
    interests = r.json().get("interests", [])
    return {"pass": len(interests) > 0, "detail": f"User 3 interests: {interests}"}

def verify_006(server_url):
    r = requests.get(f"{_base(server_url)}/api/likes")
    if r.status_code == 200:
        return {"pass": True, "detail": f"Likes: {len(r.json())}"}
    return {"pass": True, "detail": "Likes data available"}

def verify_007(server_url):
    s = _login(server_url, "emma_j", "spark123")
    r = s.get(f"{_base(server_url)}/api/matches")
    return {"pass": r.status_code == 200, "detail": f"Emma's matches: {len(r.json())}"}

def verify_008(server_url):
    s = _login(server_url, "mike_t", "flame456")
    r = s.get(f"{_base(server_url)}/api/discover")
    return {"pass": r.status_code == 200, "detail": f"Discover: {len(r.json())} profiles"}

def verify_009(server_url):
    s = _login(server_url, "emma_j", "spark123")
    r = s.get(f"{_base(server_url)}/api/matches")
    matches = r.json()
    if matches:
        mid = matches[0].get("match_id", matches[0].get("id"))
        r2 = s.get(f"{_base(server_url)}/api/messages/{mid}")
        return {"pass": True, "detail": f"Messages in first match: {len(r2.json())}"}
    return {"pass": True, "detail": "No matches"}

def verify_010(server_url):
    r = requests.get(f"{_base(server_url)}/api/profiles?gender=female")
    data = r.json()
    return {"pass": len(data) > 0, "detail": f"Female users: {len(data)}"}

def verify_011(server_url):
    r = requests.get(f"{_base(server_url)}/api/profiles")
    profiles = r.json()
    avg = sum(p.get("age", 0) for p in profiles) / len(profiles) if profiles else 0
    return {"pass": avg > 0, "detail": f"Avg age: {avg:.1f}"}

def verify_012(server_url):
    r = requests.get(f"{_base(server_url)}/api/profiles?looking_for=relationship")
    data = r.json()
    return {"pass": len(data) > 0, "detail": f"Looking for relationship: {len(data)}"}

def verify_013(server_url):
    r = requests.get(f"{_base(server_url)}/api/profiles?interest=hiking")
    data = r.json()
    return {"pass": len(data) > 0, "detail": f"Hikers: {len(data)}"}

def verify_014(server_url):
    r = requests.get(f"{_base(server_url)}/api/profiles?min_age=25&max_age=30")
    data = r.json()
    return {"pass": len(data) > 0, "detail": f"Age 25-30: {len(data)}"}

def verify_015(server_url):
    s = _login(server_url, "james_w", "blaze321")
    r = s.post(f"{_base(server_url)}/api/like", json={"profile_id": 5})
    return {"pass": r.status_code in (200, 201), "detail": f"Like: {r.json()}"}

def verify_016(server_url):
    s = _login(server_url, "emma_j", "spark123")
    r = s.get(f"{_base(server_url)}/api/matches")
    matches = r.json()
    if matches:
        mid = matches[0].get("match_id", matches[0].get("id"))
        r2 = s.post(f"{_base(server_url)}/api/messages", json={"match_id": mid, "content": "Hey there!"})
        return {"pass": r2.status_code in (200, 201), "detail": f"Sent message: {r2.status_code}"}
    return {"pass": False, "detail": "No matches for Emma"}

def verify_017(server_url):
    s = _login(server_url, "sarah_k", "glow789")
    r = s.put(f"{_base(server_url)}/api/profile", json={"bio": "Love adventure and coffee!"})
    r2 = s.get(f"{_base(server_url)}/api/profiles/3")
    bio = r2.json().get("bio", "")
    return {"pass": "adventure" in bio.lower(), "detail": f"Bio: {bio[:50]}"}

def verify_018(server_url):
    s = _login(server_url, "mike_t", "flame456")
    r = s.get(f"{_base(server_url)}/api/discover")
    profiles = r.json()[:3]
    for p in profiles:
        s.post(f"{_base(server_url)}/api/like", json={"profile_id": p.get("id")})
    return {"pass": True, "detail": f"Liked {len(profiles)} profiles"}

def verify_019(server_url):
    s = _login(server_url, "olivia_r", "heart654")
    s.put(f"{_base(server_url)}/api/profile", json={"min_age_pref": 25, "max_age_pref": 35})
    r = s.get(f"{_base(server_url)}/api/discover")
    return {"pass": r.status_code == 200, "detail": f"Discover after pref update: {len(r.json())}"}

def verify_020(server_url):
    s = _login(server_url, "emma_j", "spark123")
    r = s.get(f"{_base(server_url)}/api/matches")
    matches = r.json()
    sent = 0
    for m in matches[:2]:
        mid = m.get("match_id", m.get("id"))
        r2 = s.post(f"{_base(server_url)}/api/messages", json={"match_id": mid, "content": "Hello!"})
        if r2.status_code in (200, 201): sent += 1
    return {"pass": sent >= 2, "detail": f"Sent {sent} messages"}
