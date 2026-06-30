"""Per-task reference solutions via Flask test client for health-fitness-tracking."""
import json


def solve_001(client, base="/sites/health-fitness-tracking"):
    r = client.get(f"{base}/api/workouts?user_id=1&type=running")
    workouts = json.loads(r.data)
    return str(len(workouts))


def solve_002(client, base="/sites/health-fitness-tracking"):
    r = client.get(f"{base}/api/workouts/1")
    w = json.loads(r.data)
    return f"{w['type']}, {w['calories_burned']} calories"


def solve_003(client, base="/sites/health-fitness-tracking"):
    r = client.get(f"{base}/api/search?q=bench")
    return str(len(json.loads(r.data)))


def solve_004(client, base="/sites/health-fitness-tracking"):
    r = client.get(f"{base}/api/search/semantic?q=outdoor+cardio+running+trail")
    return str(len(json.loads(r.data)))


def solve_005(client, base="/sites/health-fitness-tracking"):
    r = client.get(f"{base}/api/workouts?user_id=1&from=2026-01-01&to=2026-01-31")
    return str(len(json.loads(r.data)))


def solve_006(client, base="/sites/health-fitness-tracking"):
    r = client.get(f"{base}/api/workouts?user_id=1&sort=calories")
    workouts = json.loads(r.data)
    return str(workouts[0]["calories_burned"]) if workouts else "0"


def solve_007(client, base="/sites/health-fitness-tracking"):
    r = client.get(f"{base}/api/workouts/stats?type=strength_training&user_id=1")
    stats = json.loads(r.data)
    return str(stats["avg_duration_minutes"])


def solve_008(client, base="/sites/health-fitness-tracking"):
    r = client.get(f"{base}/api/workouts/compare?ids=1,2")
    workouts = json.loads(r.data)
    types = [w["type"] for w in workouts]
    return ", ".join(types)


def solve_009(client, base="/sites/health-fitness-tracking"):
    r = client.get(f"{base}/api/daily-stats?user_id=1&from=2026-01-01&to=2026-01-07")
    stats = json.loads(r.data)
    total = sum(s["steps"] for s in stats)
    return str(total)


def solve_010(client, base="/sites/health-fitness-tracking"):
    r = client.get(f"{base}/api/workouts/extremum?metric=calories_burned&direction=max&user_id=1")
    data = json.loads(r.data)
    return f"{data['workout']['type']}, {data['value']} calories"


def solve_011(client, base="/sites/health-fitness-tracking"):
    r = client.get(f"{base}/api/stats/threshold?metric=steps&min_value=10000&user_id=1")
    data = json.loads(r.data)
    return f"{data['percentage']}%"


def solve_012(client, base="/sites/health-fitness-tracking"):
    r = client.get(f"{base}/api/stats/compare?user_id=1&from1=2026-01-01&to1=2026-01-31&from2=2026-03-01&to2=2026-03-31")
    data = json.loads(r.data)
    p1 = data["period1"]["stats"]["avg_steps"]
    p2 = data["period2"]["stats"]["avg_steps"]
    return "January" if p1 > p2 else "March"


def solve_013(client, base="/sites/health-fitness-tracking"):
    r = client.get(f"{base}/api/goals/verify?user_id=1&goal_id=g1-1&tolerance=0.1")
    data = json.loads(r.data)
    return "Yes" if data["met"] else "No"


def solve_014(client, base="/sites/health-fitness-tracking"):
    client.post(f"{base}/api/workouts", json={
        "user_id": 1,
        "type": "running",
        "date": "2026-04-01",
        "duration_minutes": 45,
        "calories_burned": 380,
        "notes": "Morning jog along the waterfront",
    })
    r = client.get(f"{base}/api/workouts?user_id=1&from=2026-04-01&to=2026-04-01")
    workouts = json.loads(r.data)
    running = [w for w in workouts if w["type"] == "running"]
    return "created" if running else "failed"


def solve_015(client, base="/sites/health-fitness-tracking"):
    r = client.post(f"{base}/api/workouts/quick", json={
        "user_id": 1,
        "date": "2026-04-02",
        "exercises": ["deadlift", "barbell row", "pull-ups"],
        "duration_minutes": 50,
    })
    w = json.loads(r.data)
    exercises = w.get("exercises", [])
    return ", ".join(exercises)


def solve_016(client, base="/sites/health-fitness-tracking"):
    r = client.post(f"{base}/api/nutrition/quick", json={
        "user_id": 1,
        "query": "grilled salmon with vegetables",
        "meal_type": "dinner",
        "date": "2026-04-01",
    })
    meal = json.loads(r.data)
    return str(meal["calories"])


def solve_017(client, base="/sites/health-fitness-tracking"):
    client.put(f"{base}/api/workouts/1", json={
        "notes": "Updated: Great upper body session with Nathan. Bench PR!",
    })
    r = client.get(f"{base}/api/workouts/1")
    w = json.loads(r.data)
    return w["notes"]


def solve_018(client, base="/sites/health-fitness-tracking"):
    client.delete(f"{base}/api/nutrition/1")
    r = client.get(f"{base}/api/nutrition?user_id=1")
    meals = json.loads(r.data)
    ids = [m["id"] for m in meals]
    return "deleted" if 1 not in ids else "failed"


def solve_019(client, base="/sites/health-fitness-tracking"):
    client.put(f"{base}/api/users/1/settings", json={
        "daily_step_target": 12000,
    })
    r = client.get(f"{base}/api/users/1/settings")
    data = json.loads(r.data)
    return str(data["settings"]["daily_step_target"])


def solve_020(client, base="/sites/health-fitness-tracking"):
    r = client.get(f"{base}/api/workouts/replay?type=hiking&user_id=1")
    data = json.loads(r.data)
    timeline = data.get("timeline", [])
    return str(len(timeline))
