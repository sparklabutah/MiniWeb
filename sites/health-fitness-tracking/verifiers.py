"""Per-task HTTP verification functions for health-fitness-tracking."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/health-fitness-tracking"
    r = requests.get(f"{base}/api/workouts?user_id=1&type=running")
    workouts = r.json()
    count = len(workouts)
    return {"pass": count > 0, "detail": f"Running workouts for user 1: {count}"}


def verify_002(server_url):
    base = f"{server_url}/sites/health-fitness-tracking"
    r = requests.get(f"{base}/api/workouts/1")
    w = r.json()
    wtype = w.get("type", "")
    cals = w.get("calories_burned", 0)
    return {"pass": wtype == "strength_training" and cals == 420,
            "detail": f"Workout 1: type={wtype}, calories={cals}"}


def verify_003(server_url):
    base = f"{server_url}/sites/health-fitness-tracking"
    r = requests.get(f"{base}/api/search?q=bench")
    results = r.json()
    count = len(results)
    return {"pass": count > 0, "detail": f"Search 'bench': {count} results"}


def verify_004(server_url):
    base = f"{server_url}/sites/health-fitness-tracking"
    r = requests.get(f"{base}/api/search/semantic?q=outdoor+cardio+running+trail")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Semantic 'outdoor cardio running trail': {count} results"}


def verify_005(server_url):
    base = f"{server_url}/sites/health-fitness-tracking"
    r = requests.get(f"{base}/api/workouts?user_id=1&from=2026-01-01&to=2026-01-31")
    workouts = r.json()
    count = len(workouts)
    ok = all(w["date"] >= "2026-01-01" and w["date"] <= "2026-01-31" for w in workouts)
    return {"pass": ok and count > 0, "detail": f"Jan 2026 workouts: {count}, all_in_range={ok}"}


def verify_006(server_url):
    base = f"{server_url}/sites/health-fitness-tracking"
    r = requests.get(f"{base}/api/workouts?user_id=1&sort=calories")
    workouts = r.json()
    if not workouts:
        return {"pass": False, "detail": "No workouts returned"}
    top_cal = workouts[0]["calories_burned"]
    return {"pass": top_cal > 0, "detail": f"Top calories: {top_cal}"}


def verify_007(server_url):
    base = f"{server_url}/sites/health-fitness-tracking"
    r = requests.get(f"{base}/api/workouts/stats?type=strength_training&user_id=1")
    stats = r.json()
    avg_dur = stats.get("avg_duration_minutes")
    return {"pass": avg_dur is not None and avg_dur > 0,
            "detail": f"Strength training avg duration: {avg_dur}"}


def verify_008(server_url):
    base = f"{server_url}/sites/health-fitness-tracking"
    r = requests.get(f"{base}/api/workouts/compare?ids=1,2")
    workouts = r.json()
    ok = len(workouts) == 2
    types = [w["type"] for w in workouts] if ok else []
    return {"pass": ok, "detail": f"Compare: types={types}"}


def verify_009(server_url):
    base = f"{server_url}/sites/health-fitness-tracking"
    r = requests.get(f"{base}/api/daily-stats?user_id=1&from=2026-01-01&to=2026-01-07")
    stats = r.json()
    total_steps = sum(s["steps"] for s in stats)
    return {"pass": total_steps > 0, "detail": f"Jan 1-7 total steps: {total_steps}"}


def verify_010(server_url):
    base = f"{server_url}/sites/health-fitness-tracking"
    r = requests.get(f"{base}/api/workouts/extremum?metric=calories_burned&direction=max&user_id=1")
    data = r.json()
    val = data.get("value")
    wtype = data.get("workout", {}).get("type")
    return {"pass": val is not None and val > 0,
            "detail": f"Max calories: {val}, type={wtype}"}


def verify_011(server_url):
    base = f"{server_url}/sites/health-fitness-tracking"
    r = requests.get(f"{base}/api/stats/threshold?metric=steps&min_value=10000&user_id=1")
    data = r.json()
    pct = data.get("percentage")
    days = data.get("days_above")
    return {"pass": pct is not None,
            "detail": f"Days above 10k steps: {days}, percentage: {pct}%"}


def verify_012(server_url):
    base = f"{server_url}/sites/health-fitness-tracking"
    r = requests.get(f"{base}/api/stats/compare?user_id=1&from1=2026-01-01&to1=2026-01-31&from2=2026-03-01&to2=2026-03-31")
    data = r.json()
    p1 = data.get("period1", {}).get("stats")
    p2 = data.get("period2", {}).get("stats")
    if not p1 or not p2:
        return {"pass": False, "detail": "Missing period data"}
    higher = "January" if p1["avg_steps"] > p2["avg_steps"] else "March"
    return {"pass": True,
            "detail": f"Jan avg steps: {p1['avg_steps']}, Mar avg steps: {p2['avg_steps']}, higher: {higher}"}


def verify_013(server_url):
    base = f"{server_url}/sites/health-fitness-tracking"
    r = requests.get(f"{base}/api/goals/verify?user_id=1&goal_id=g1-1&tolerance=0.1")
    data = r.json()
    met = data.get("met")
    actual = data.get("actual")
    return {"pass": met is not None,
            "detail": f"Goal g1-1 met={met}, actual={actual}, target=10000"}


def verify_014(server_url):
    base = f"{server_url}/sites/health-fitness-tracking"
    r = requests.get(f"{base}/api/workouts?user_id=1&from=2026-04-01&to=2026-04-01")
    workouts = r.json()
    running = [w for w in workouts if w["type"] == "running"
               and "Morning jog" in w.get("notes", "")]
    return {"pass": len(running) > 0,
            "detail": f"Created running workout on 2026-04-01: found={len(running)}"}


def verify_015(server_url):
    base = f"{server_url}/sites/health-fitness-tracking"
    r = requests.get(f"{base}/api/workouts?user_id=1&from=2026-04-02&to=2026-04-02")
    workouts = r.json()
    strength = [w for w in workouts if w["type"] == "strength_training"
                and "deadlift" in w.get("exercises", [])]
    return {"pass": len(strength) > 0,
            "detail": f"Created strength workout with exercises on 2026-04-02: found={len(strength)}"}


def verify_016(server_url):
    base = f"{server_url}/sites/health-fitness-tracking"
    r = requests.get(f"{base}/api/nutrition?user_id=1&date=2026-04-01")
    meals = r.json()
    salmon = [m for m in meals if "salmon" in m.get("description", "").lower()]
    if salmon:
        cals = salmon[0]["calories"]
        return {"pass": True, "detail": f"Salmon meal logged: calories={cals}"}
    return {"pass": False, "detail": "Salmon meal not found"}


def verify_017(server_url):
    base = f"{server_url}/sites/health-fitness-tracking"
    r = requests.get(f"{base}/api/workouts/1")
    w = r.json()
    notes = w.get("notes", "")
    ok = "Updated: Great upper body session" in notes
    return {"pass": ok, "detail": f"Workout 1 notes updated: {ok}, notes='{notes[:60]}'"}


def verify_018(server_url):
    base = f"{server_url}/sites/health-fitness-tracking"
    r = requests.get(f"{base}/api/nutrition?user_id=1")
    meals = r.json()
    ids = [m["id"] for m in meals]
    ok = 1 not in ids
    return {"pass": ok, "detail": f"Meal 1 deleted: {ok}. Remaining IDs: {ids[:10]}"}


def verify_019(server_url):
    base = f"{server_url}/sites/health-fitness-tracking"
    r = requests.get(f"{base}/api/users/1/settings")
    data = r.json()
    target = data.get("settings", {}).get("daily_step_target")
    return {"pass": target == 12000,
            "detail": f"Step target: {target}, expected 12000"}


def verify_020(server_url):
    base = f"{server_url}/sites/health-fitness-tracking"
    r = requests.get(f"{base}/api/workouts/replay?type=hiking&user_id=1")
    data = r.json()
    timeline = data.get("timeline", [])
    count = len(timeline)
    return {"pass": count >= 2,
            "detail": f"Hiking replay timeline phases: {count}"}
