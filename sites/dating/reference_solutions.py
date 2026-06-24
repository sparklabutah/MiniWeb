"""Per-task reference solutions via Flask test client for dating."""
import json

def _login(c, base, u, p):
    c.post(f"{base}/api/login", data=json.dumps({"username": u, "password": p}), content_type="application/json")

def solve_001(client, base="/sites/dating"):
    r = client.get(f"{base}/api/profiles")
    return str(len(json.loads(r.data)))

def solve_002(client, base="/sites/dating"):
    r = client.get(f"{base}/api/profiles/1")
    d = json.loads(r.data)
    return f"{d.get('name')}, {d.get('age')}"

def solve_003(client, base="/sites/dating"):
    r = client.get(f"{base}/api/stats")
    d = json.loads(r.data)
    return str(d.get("active_matches", 0))

def solve_004(client, base="/sites/dating"):
    r = client.get(f"{base}/api/messages/all")
    if r.status_code == 200:
        return str(len(json.loads(r.data)))
    return "N/A"

def solve_005(client, base="/sites/dating"):
    r = client.get(f"{base}/api/profiles/3")
    return ", ".join(json.loads(r.data).get("interests", []))

def solve_006(client, base="/sites/dating"):
    r = client.get(f"{base}/api/likes")
    if r.status_code == 200:
        return str(len(json.loads(r.data)))
    return "N/A"

def solve_007(client, base="/sites/dating"):
    _login(client, base, "emma_j", "spark123")
    r = client.get(f"{base}/api/matches")
    return str(len(json.loads(r.data)))

def solve_008(client, base="/sites/dating"):
    _login(client, base, "mike_t", "flame456")
    r = client.get(f"{base}/api/discover")
    return str(len(json.loads(r.data)))

def solve_009(client, base="/sites/dating"):
    _login(client, base, "emma_j", "spark123")
    r = client.get(f"{base}/api/matches")
    matches = json.loads(r.data)
    if matches:
        mid = matches[0].get("match_id", matches[0].get("id"))
        r2 = client.get(f"{base}/api/messages/{mid}")
        return str(len(json.loads(r2.data)))
    return "0"

def solve_010(client, base="/sites/dating"):
    r = client.get(f"{base}/api/profiles?gender=female")
    return str(len(json.loads(r.data)))

def solve_011(client, base="/sites/dating"):
    r = client.get(f"{base}/api/profiles")
    profiles = json.loads(r.data)
    avg = sum(p.get("age", 0) for p in profiles) / len(profiles) if profiles else 0
    return f"{avg:.1f}"

def solve_012(client, base="/sites/dating"):
    r = client.get(f"{base}/api/profiles?looking_for=relationship")
    return str(len(json.loads(r.data)))

def solve_013(client, base="/sites/dating"):
    r = client.get(f"{base}/api/profiles?interest=hiking")
    return str(len(json.loads(r.data)))

def solve_014(client, base="/sites/dating"):
    r = client.get(f"{base}/api/profiles?min_age=25&max_age=30")
    return str(len(json.loads(r.data)))

def solve_015(client, base="/sites/dating"):
    _login(client, base, "james_w", "blaze321")
    r = client.post(f"{base}/api/like", data=json.dumps({"profile_id": 5}), content_type="application/json")
    return json.dumps(json.loads(r.data))

def solve_016(client, base="/sites/dating"):
    _login(client, base, "emma_j", "spark123")
    r = client.get(f"{base}/api/matches")
    matches = json.loads(r.data)
    if matches:
        mid = matches[0].get("match_id", matches[0].get("id"))
        client.post(f"{base}/api/messages", data=json.dumps({"match_id": mid, "content": "Hey there!"}), content_type="application/json")
        return "sent"
    return "no matches"

def solve_017(client, base="/sites/dating"):
    _login(client, base, "sarah_k", "glow789")
    client.put(f"{base}/api/profile", data=json.dumps({"bio": "Love adventure and coffee!"}), content_type="application/json")
    r = client.get(f"{base}/api/profiles/3")
    return json.loads(r.data).get("bio", "")

def solve_018(client, base="/sites/dating"):
    _login(client, base, "mike_t", "flame456")
    r = client.get(f"{base}/api/discover")
    profiles = json.loads(r.data)[:3]
    for p in profiles:
        client.post(f"{base}/api/like", data=json.dumps({"profile_id": p.get("id")}), content_type="application/json")
    return str(len(profiles))

def solve_019(client, base="/sites/dating"):
    _login(client, base, "olivia_r", "heart654")
    client.put(f"{base}/api/profile", data=json.dumps({"min_age_pref": 25, "max_age_pref": 35}), content_type="application/json")
    r = client.get(f"{base}/api/discover")
    return str(len(json.loads(r.data)))

def solve_020(client, base="/sites/dating"):
    _login(client, base, "emma_j", "spark123")
    r = client.get(f"{base}/api/matches")
    matches = json.loads(r.data)
    sent = 0
    for m in matches[:2]:
        mid = m.get("match_id", m.get("id"))
        r2 = client.post(f"{base}/api/messages", data=json.dumps({"match_id": mid, "content": "Hello!"}), content_type="application/json")
        if r2.status_code in (200, 201): sent += 1
    return str(sent)
