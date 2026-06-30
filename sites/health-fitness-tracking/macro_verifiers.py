"""Per-macro verification functions for health-fitness-tracking.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/health-fitness-tracking"


def verify_macro_navigate_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/users")
    users = r.json()
    if not users:
        return {"pass": False, "detail": "No users returned"}
    uid = users[0]["id"]
    r2 = requests.get(f"{_base(server_url)}/api/workouts?user_id={uid}")
    return {"pass": r2.status_code == 200,
            "detail": f"Navigate to user {uid} workouts: {r2.status_code}"}


def verify_macro_navigate_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/workout/1")
    return {"pass": r.status_code == 200,
            "detail": f"Workout detail page: {r.status_code}"}


def verify_macro_search_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/search?q=bench")
    results = r.json()
    return {"pass": len(results) > 0,
            "detail": f"search_by_query 'bench': {len(results)} results"}


def verify_macro_search_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/api/search/semantic?q=running+trail+outdoor")
    results = r.json()
    return {"pass": r.status_code == 200,
            "detail": f"search_by_semantic: {len(results)} results"}


def verify_macro_filter_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/workouts?user_id=1&type=running")
    workouts = r.json()
    ok = all(w["type"] == "running" for w in workouts)
    return {"pass": ok and len(workouts) > 0,
            "detail": f"filter_by_dropdown running: {len(workouts)}, all_running={ok}"}


def verify_macro_filter_by_date_range(server_url):
    r = requests.get(f"{_base(server_url)}/api/workouts?user_id=1&from=2026-01-01&to=2026-01-31")
    workouts = r.json()
    ok = all("2026-01-01" <= w["date"] <= "2026-01-31" for w in workouts)
    return {"pass": ok and len(workouts) > 0,
            "detail": f"filter Jan 2026: {len(workouts)}, all_in_range={ok}"}


def verify_macro_sort_by_ranking(server_url):
    r = requests.get(f"{_base(server_url)}/api/workouts?user_id=1&sort=calories")
    workouts = r.json()
    if len(workouts) < 2:
        return {"pass": True, "detail": "Too few workouts to verify sort"}
    cals = [w.get("calories_burned", 0) for w in workouts]
    is_sorted = all(cals[i] >= cals[i+1] for i in range(len(cals)-1))
    return {"pass": is_sorted,
            "detail": f"sort_by_ranking: sorted_desc={is_sorted}"}


def verify_macro_extract_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/workouts/stats?type=running&user_id=1")
    stats = r.json()
    return {"pass": "avg_duration_minutes" in stats,
            "detail": f"extract_by_dropdown: running stats={stats.get('count')} workouts"}


def verify_macro_extract_from_table(server_url):
    r = requests.get(f"{_base(server_url)}/api/workouts/compare?ids=1,2")
    workouts = r.json()
    return {"pass": len(workouts) == 2,
            "detail": f"extract_from_table: compared {len(workouts)} workouts"}


def verify_macro_extract_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/workouts/1")
    w = r.json()
    return {"pass": "type" in w and "calories_burned" in w,
            "detail": f"extract_by_route: workout type={w.get('type')}"}


def verify_macro_extract_by_date_range(server_url):
    r = requests.get(f"{_base(server_url)}/api/daily-stats?user_id=1&from=2026-01-01&to=2026-01-07")
    stats = r.json()
    return {"pass": len(stats) > 0,
            "detail": f"extract_by_date_range: {len(stats)} days"}


def verify_macro_compute_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/workouts/stats?type=strength_training&user_id=1")
    stats = r.json()
    return {"pass": "total_calories_burned" in stats and "count" in stats,
            "detail": f"compute_by_dropdown: count={stats.get('count')}, total_cal={stats.get('total_calories_burned')}"}


def verify_macro_compute_by_extremum(server_url):
    r = requests.get(f"{_base(server_url)}/api/workouts/extremum?metric=calories_burned&direction=max&user_id=1")
    data = r.json()
    return {"pass": "value" in data and "workout" in data,
            "detail": f"compute_by_extremum: max_cal={data.get('value')}"}


def verify_macro_compute_by_slider(server_url):
    r = requests.get(f"{_base(server_url)}/api/stats/threshold?metric=steps&min_value=10000&user_id=1")
    data = r.json()
    return {"pass": "percentage" in data and "days_above" in data,
            "detail": f"compute_by_slider: days_above={data.get('days_above')}, pct={data.get('percentage')}%"}


def verify_macro_compare_by_date_range(server_url):
    r = requests.get(f"{_base(server_url)}/api/stats/compare?user_id=1&from1=2026-01-01&to1=2026-01-31&from2=2026-03-01&to2=2026-03-31")
    data = r.json()
    p1 = data.get("period1", {}).get("stats")
    p2 = data.get("period2", {}).get("stats")
    return {"pass": p1 is not None and p2 is not None,
            "detail": f"compare_by_date_range: p1_steps={p1.get('avg_steps') if p1 else None}, p2_steps={p2.get('avg_steps') if p2 else None}"}


def verify_macro_verify_by_slider(server_url):
    r = requests.get(f"{_base(server_url)}/api/goals/verify?user_id=1&goal_id=g1-1&tolerance=0.1")
    data = r.json()
    return {"pass": "met" in data and "actual" in data,
            "detail": f"verify_by_slider: met={data.get('met')}, actual={data.get('actual')}"}


def verify_macro_create_from_free_text(server_url):
    r = requests.post(f"{_base(server_url)}/api/workouts", json={
        "user_id": 1, "type": "running", "date": "2026-05-01",
        "duration_minutes": 30, "notes": "Macro verify test run",
    })
    data = r.json()
    ok = data.get("id") is not None
    # Clean up
    if ok:
        requests.delete(f"{_base(server_url)}/api/workouts/{data['id']}")
    return {"pass": ok, "detail": f"create_from_free_text: id={data.get('id')}"}


def verify_macro_create_by_checkbox(server_url):
    r = requests.post(f"{_base(server_url)}/api/workouts/quick", json={
        "user_id": 1, "date": "2026-05-02",
        "exercises": ["push-ups", "sit-ups"], "duration_minutes": 20,
    })
    data = r.json()
    ok = "exercises" in data and len(data["exercises"]) == 2
    # Clean up
    if data.get("id"):
        requests.delete(f"{_base(server_url)}/api/workouts/{data['id']}")
    return {"pass": ok, "detail": f"create_by_checkbox: exercises={data.get('exercises')}"}


def verify_macro_submit_by_query(server_url):
    r = requests.post(f"{_base(server_url)}/api/nutrition/quick", json={
        "user_id": 1, "query": "test salad", "meal_type": "lunch", "date": "2026-05-01",
    })
    data = r.json()
    ok = data.get("id") is not None
    # Clean up
    if ok:
        requests.delete(f"{_base(server_url)}/api/nutrition/{data['id']}")
    return {"pass": ok, "detail": f"submit_by_query: id={data.get('id')}, cal={data.get('calories')}"}


def verify_macro_edit_by_form(server_url):
    # Read, modify, revert
    r = requests.get(f"{_base(server_url)}/api/workouts/1")
    original_notes = r.json().get("notes", "")
    requests.put(f"{_base(server_url)}/api/workouts/1",
                 json={"notes": "MACRO_VERIFY_TEST"})
    r = requests.get(f"{_base(server_url)}/api/workouts/1")
    ok = r.json().get("notes") == "MACRO_VERIFY_TEST"
    # Revert
    requests.put(f"{_base(server_url)}/api/workouts/1",
                 json={"notes": original_notes})
    return {"pass": ok, "detail": f"edit_by_form: updated={ok}"}


def verify_macro_delete_from_table(server_url):
    # Create a temp workout, then delete
    r = requests.post(f"{_base(server_url)}/api/workouts", json={
        "user_id": 1, "type": "test", "date": "2026-05-05", "duration_minutes": 1,
    })
    wid = r.json().get("id")
    r = requests.delete(f"{_base(server_url)}/api/workouts/{wid}")
    data = r.json()
    return {"pass": data.get("deleted") == wid,
            "detail": f"delete_from_table: deleted={data.get('deleted')}"}


def verify_macro_select_from_table(server_url):
    r = requests.get(f"{_base(server_url)}/api/workouts/compare?ids=1,2,3")
    workouts = r.json()
    return {"pass": len(workouts) >= 2,
            "detail": f"select_from_table: selected {len(workouts)} workouts"}


def verify_macro_configure_by_slider(server_url):
    # Read, set, revert
    r = requests.get(f"{_base(server_url)}/api/users/1/settings")
    original = r.json().get("settings", {}).get("daily_step_target")
    requests.put(f"{_base(server_url)}/api/users/1/settings",
                 json={"daily_step_target": 15000})
    r = requests.get(f"{_base(server_url)}/api/users/1/settings")
    new_val = r.json().get("settings", {}).get("daily_step_target")
    # Revert
    requests.put(f"{_base(server_url)}/api/users/1/settings",
                 json={"daily_step_target": original or 10000})
    return {"pass": new_val == 15000,
            "detail": f"configure_by_slider: set to {new_val}"}


def verify_macro_play_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/workouts/replay?type=hiking&user_id=1")
    data = r.json()
    timeline = data.get("timeline", [])
    return {"pass": len(timeline) >= 2,
            "detail": f"play_by_dropdown: {len(timeline)} phases"}


def verify_macro_play_by_playback(server_url):
    r = requests.get(f"{_base(server_url)}/api/stats/playback?user_id=1&metric=steps&from=2026-01-01&to=2026-01-07")
    data = r.json()
    frames = data.get("frames", [])
    return {"pass": len(frames) > 0,
            "detail": f"play_by_playback: {len(frames)} frames"}


def verify_macro_export_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/export?format=csv&data_type=workouts&user_id=1")
    lines = r.text.strip().split("\n")
    return {"pass": len(lines) > 1,
            "detail": f"export_by_dropdown: CSV {len(lines)} lines"}
