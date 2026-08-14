"""FitTrack -- health & fitness tracking dashboard (MyFitnessPal style).

Reads workout logs, daily health stats, nutrition entries, fitness goals, food
database, and user profiles from SQLite and exposes them through HTML pages
and a JSON API.

Assigned macros (see annotation/macro_locations.py — the authoritative list):
  navigate_by_route, search_by_query, search_by_semantic,
  filter_by_dropdown, filter_by_date_range, sort_by_ranking,
  extract_by_dropdown, extract_from_table, extract_by_route, extract_by_date_range,
  compute_by_dropdown, compute_by_extremum, compute_by_slider, verify_by_slider,
  create_by_form, submit_by_form, delete_from_table, select_from_table,
  configure_by_slider, export_by_dropdown

Some API endpoints below (compare, replay, quick-create, workout update) have no
UI surface and are intentionally NOT listed in macro_locations.
"""

import csv
import io
import json
import math
import pathlib
import re
from collections import defaultdict
from datetime import datetime, timedelta

from flask import (
    Blueprint,
    Response,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from app import db
from helpers.auth import current_user
from app.events import emit

SITE = "health-fitness-tracking"
SITE_DIR = pathlib.Path(__file__).resolve().parent

blueprint = Blueprint(
    "health-fitness-tracking",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static") if (SITE_DIR / "static").exists() else None,
    static_url_path="/static",
)

MEAL_ORDER = {"breakfast": 0, "lunch": 1, "dinner": 2, "snack": 3}

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _load_workouts(*, where=None, sort=None, limit=None):
    return db.query(SITE, "workouts", where=where, sort=sort, limit=limit)

def _load_daily_stats(*, where=None, sort=None, limit=None):
    return db.query(SITE, "daily_stats", where=where, sort=sort, limit=limit)

def _load_nutrition(*, where=None, sort=None, limit=None):
    return db.query(SITE, "nutrition", where=where, sort=sort, limit=limit)

def _load_goals(*, where=None):
    return db.query(SITE, "goals", where=where)

def _load_users():
    return db.query(SITE, "users")

def _get_user(user_id):
    return db.get_item(SITE, "users", user_id)

def _get_current_user():
    return current_user(_get_user, session_keys=("user_id",))

def _today():
    return datetime.now().strftime("%Y-%m-%d")

def _semantic_score(text, query):
    """Simple keyword-overlap semantic relevance score."""
    query_words = set(re.findall(r'\w+', query.lower()))
    text_words = re.findall(r'\w+', text.lower())
    if not query_words or not text_words:
        return 0
    text_word_set = set(text_words)
    overlap = len(query_words & text_word_set)
    return overlap / len(query_words)

# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

def _dashboard_analytics(uid, view_date, cal_goal, step_goal=10000):
    """Compute dense-analytics aggregates + inline-SVG chart geometry."""
    import math
    vd = datetime.strptime(view_date, "%Y-%m-%d").date()

    def fmt(d):
        return d.strftime("%Y-%m-%d")

    stats = [s for s in _load_daily_stats(where={"user_id": uid}) if s["date"] <= view_date]
    stats.sort(key=lambda s: s["date"])
    by_date = {s["date"]: s for s in stats}
    workouts_all = _load_workouts(where={"user_id": uid})
    workout_dates = {w["date"] for w in workouts_all}

    def sday(d):
        return by_date.get(fmt(d))

    today = sday(vd) or {}
    last7 = [s for s in (sday(vd - timedelta(days=k)) for k in range(7)) if s]
    avg_steps = int(sum(s["steps"] for s in last7) / len(last7)) if last7 else 0

    wlist = [s for s in stats if s.get("weight_kg")]
    weight_current = wlist[-1]["weight_kg"] if wlist else 0
    w30 = [s for s in wlist if s["date"] >= fmt(vd - timedelta(days=30))]
    weight_delta = round(w30[-1]["weight_kg"] - w30[0]["weight_kg"], 1) if len(w30) >= 2 else 0.0

    wk = [w for w in workouts_all if fmt(vd - timedelta(days=6)) <= w["date"] <= view_date]

    streak, dd = 0, vd
    while True:
        s = sday(dd)
        if (s and s.get("active_minutes", 0) >= 30) or fmt(dd) in workout_dates:
            streak += 1
            dd -= timedelta(days=1)
        else:
            break

    kpis = {
        "steps": today.get("steps", 0), "avg_steps": avg_steps,
        "active_min": today.get("active_minutes", 0),
        "weight": weight_current, "weight_delta": weight_delta,
        "sleep": today.get("sleep_hours", 0),
        "workouts_week": len(wk),
        "distance_week": round(sum(w.get("distance_km", 0) for w in wk), 1),
        "cals_burned": today.get("calories_burned", 0),
        "streak": streak,
    }

    # ---- weight trend (last 45 logged points) ----
    wwin = [s for s in stats if s.get("weight_kg")][-45:]
    W, H, P = 560, 150, 12
    weight = None
    if len(wwin) >= 2:
        ws = [s["weight_kg"] for s in wwin]
        wmin, wmax = min(ws), max(ws)
        span = (wmax - wmin) or 1
        iw, ih = W - 2 * P, H - 2 * P
        pts = []
        for i, s in enumerate(wwin):
            x = P + (i / (len(wwin) - 1)) * iw
            y = P + ih - (s["weight_kg"] - wmin) / span * ih
            pts.append((round(x, 1), round(y, 1)))
        poly = " ".join(f"{x},{y}" for x, y in pts)
        area = f"{P},{H-P} " + poly + f" {W-P},{H-P}"
        weight = {"poly": poly, "area": area, "W": W, "H": H,
                  "min": round(wmin, 1), "max": round(wmax, 1),
                  "first": wwin[0]["weight_kg"], "last": wwin[-1]["weight_kg"],
                  "delta": round(wwin[-1]["weight_kg"] - wwin[0]["weight_kg"], 1),
                  "start_date": wwin[0]["date"], "end_date": wwin[-1]["date"]}

    # ---- steps last 14 days (bars) ----
    swin = []
    for k in range(13, -1, -1):
        d = vd - timedelta(days=k)
        s = sday(d)
        swin.append({"date": fmt(d), "dow": d.strftime("%a")[:1], "steps": s["steps"] if s else 0})
    smax = max([x["steps"] for x in swin] + [step_goal, 1])
    BW, BH, bp = 560, 150, 12
    n = len(swin)
    gap = 6
    bw = (BW - 2 * bp - gap * (n - 1)) / n
    for i, x in enumerate(swin):
        x["x"] = round(bp + i * (bw + gap), 1)
        x["w"] = round(bw, 1)
        h = (x["steps"] / smax) * (BH - 2 * bp - 4)
        x["h"] = round(h, 1)
        x["y"] = round(BH - bp - h, 1)
        x["over"] = x["steps"] >= step_goal
    steps = {"bars": swin, "W": BW, "H": BH, "max": smax, "goal": step_goal,
             "goal_y": round(BH - bp - (step_goal / smax) * (BH - 2 * bp - 4), 1)}

    # ---- this week's training dots ----
    week_days = []
    for k in range(6, -1, -1):
        d = vd - timedelta(days=k)
        dws = [w for w in wk if w["date"] == fmt(d)]
        week_days.append({"dow": d.strftime("%a"), "date": fmt(d),
                          "has": bool(dws), "type": (dws[0]["type"] if dws else "")})
    week = {"days": week_days,
            "minutes": sum(w["duration_minutes"] for w in wk),
            "calories": sum(w["calories_burned"] for w in wk),
            "distance": round(sum(w.get("distance_km", 0) for w in wk), 1),
            "count": len(wk)}

    # ---- activity heatmap: 12 weeks x 7 days ----
    def lvl(m):
        return 0 if m <= 0 else 1 if m < 20 else 2 if m < 40 else 3 if m < 60 else 4
    week_monday = vd - timedelta(days=vd.weekday())
    start = week_monday - timedelta(weeks=11)
    CS, CG = 13, 3
    cells = []
    for col in range(12):
        for row in range(7):
            d = start + timedelta(days=col * 7 + row)
            if d > vd:
                continue
            m = (sday(d) or {}).get("active_minutes", 0)
            cells.append({"x": col * (CS + CG), "y": row * (CS + CG),
                          "s": CS, "level": lvl(m), "date": fmt(d), "mins": m})
    heat = {"cells": cells, "W": 12 * (CS + CG), "H": 7 * (CS + CG)}

    return {"kpis": kpis, "weight": weight, "steps": steps, "week": week, "heat": heat}


def _series_charts(rows):
    """Build line/bar chart geometry for the Trends page from daily_stats rows."""
    r = sorted(rows, key=lambda s: s["date"])
    if not r:
        return None

    def line(vals):
        W, H, P = 780, 150, 12
        vmin, vmax = min(vals), max(vals)
        span = (vmax - vmin) or 1
        iw, ih = W - 2 * P, H - 2 * P
        pts = []
        for i, v in enumerate(vals):
            x = P + (i / (len(vals) - 1) if len(vals) > 1 else 0) * iw
            y = P + ih - (v - vmin) / span * ih
            pts.append((round(x, 1), round(y, 1)))
        poly = " ".join(f"{x},{y}" for x, y in pts)
        return {"poly": poly, "area": f"{P},{H-P} {poly} {W-P},{H-P}",
                "W": W, "H": H, "min": round(vmin, 1), "max": round(vmax, 1)}

    def bars(vals, goal=None):
        W, H, bp = 780, 150, 12
        n = len(vals)
        gap = 3 if n <= 14 else 2
        bw = (W - 2 * bp - gap * (n - 1)) / n if n else 0
        vmax = max(vals + ([goal] if goal else []) + [1])
        out = []
        for i, v in enumerate(vals):
            h = (v / vmax) * (H - 2 * bp - 2)
            out.append({"x": round(bp + i * (bw + gap), 1), "w": round(bw, 1),
                        "h": round(h, 1), "y": round(H - bp - h, 1), "v": v})
        gy = round(H - bp - (goal / vmax) * (H - 2 * bp - 2), 1) if goal else None
        return {"bars": out, "W": W, "H": H, "goal_y": gy, "max": vmax}

    wr = [s["weight_kg"] for s in r if s.get("weight_kg")]
    return {
        "weight": line(wr) if len(wr) >= 2 else None,
        "steps": bars([s["steps"] for s in r], 10000),
        "sleep": bars([round(s["sleep_hours"], 1) for s in r], None),
        "active": bars([s["active_minutes"] for s in r], 30),
    }


@blueprint.route("/")
def index():
    """Dashboard -- data-dense fitness analytics."""
    user = _get_current_user()
    uid = user["id"] if user else 1

    display_user = user if user else db.get_item(SITE, "users", 1)

    # Today's stats (or most recent available)
    today_stats_list = _load_daily_stats(where={"user_id": uid}, sort="-date", limit=1)
    today_stats = today_stats_list[0] if today_stats_list else None

    # The date to show on the dashboard
    view_date = request.args.get("date", "")
    if not view_date:
        view_date = today_stats["date"] if today_stats else _today()

    # Today's meals grouped by meal_type
    today_meals = _load_nutrition(where={"user_id": uid, "date": view_date}, sort="id", limit=50)
    meals_by_type = defaultdict(list)
    for m in today_meals:
        meals_by_type[m["meal_type"]].append(m)

    # Meal totals per type
    meal_totals = {}
    for mt in ["breakfast", "lunch", "dinner", "snack"]:
        items = meals_by_type.get(mt, [])
        meal_totals[mt] = sum(m["calories"] for m in items)

    # Nutrition totals for the day
    nutrition_totals = {
        "calories": sum(m["calories"] for m in today_meals),
        "protein_g": sum(m["protein_g"] for m in today_meals),
        "carbs_g": sum(m["carbs_g"] for m in today_meals),
        "fat_g": sum(m["fat_g"] for m in today_meals),
        "fiber_g": sum(m.get("fiber_g", 0) for m in today_meals),
    }

    # User calorie/macro goals (from settings or defaults)
    user_settings = (display_user or {}).get("settings", {})
    calorie_goal = user_settings.get("daily_calorie_target", 2000)
    protein_goal = user_settings.get("daily_protein_target", 150)
    carbs_goal = user_settings.get("daily_carbs_target", 250)
    fat_goal = user_settings.get("daily_fat_target", 65)

    # Today's workouts
    today_workouts = _load_workouts(where={"user_id": uid, "date": view_date}, sort="-start_time", limit=10)
    exercise_calories = sum(w.get("calories_burned", 0) for w in today_workouts)

    # Water tracking from daily_stats
    water_glasses = 0
    if today_stats and today_stats["date"] == view_date:
        water_glasses = round(today_stats.get("water_ml", 0) / 250)  # 250ml per glass

    # Steps from daily_stats
    steps = 0
    if today_stats and today_stats["date"] == view_date:
        steps = today_stats.get("steps", 0)

    # Goals for user
    goals_data = _load_goals(where={"user_id": uid})
    user_goals_rec = goals_data[0] if goals_data else None
    user_goals = user_goals_rec["goals"] if user_goals_rec else []

    # Recent workouts (last 5), honoring the dashboard sort dropdown
    sort_param = request.args.get("sort", "date")
    sort_map = {
        "date": "-date",
        "calories": "-calories_burned",
        "duration": "-duration_minutes",
        "type": "type",
        "heart_rate": "-heart_rate_avg",
    }
    recent_workouts = _load_workouts(
        where={"user_id": uid}, sort=sort_map.get(sort_param, "-date"), limit=8
    )

    # Analytics aggregates + chart geometry
    an = _dashboard_analytics(uid, view_date, calorie_goal)
    _vd = datetime.strptime(view_date, "%Y-%m-%d").date()
    prev_date = (_vd - timedelta(days=1)).strftime("%Y-%m-%d")
    next_date = (_vd + timedelta(days=1)).strftime("%Y-%m-%d")

    # Calorie ring (SVG donut) + macro bars
    import math
    consumed = nutrition_totals["calories"]
    ring_r = 54
    ring_c = round(2 * math.pi * ring_r, 1)
    ring_pct = min(consumed / calorie_goal, 1.0) if calorie_goal else 0
    cal_ring = {
        "consumed": consumed, "goal": calorie_goal, "burned": exercise_calories,
        "net": consumed - exercise_calories, "remaining": calorie_goal - consumed + exercise_calories,
        "r": ring_r, "c": ring_c, "dash": round(ring_pct * ring_c, 1),
        "pct": round(ring_pct * 100),
    }

    def _bar(cur, goal):
        return {"cur": cur, "goal": goal, "pct": min(round(cur / goal * 100), 100) if goal else 0}
    macros = {
        "protein": _bar(nutrition_totals["protein_g"], protein_goal),
        "carbs": _bar(nutrition_totals["carbs_g"], carbs_goal),
        "fat": _bar(nutrition_totals["fat_g"], fat_goal),
        "fiber": _bar(nutrition_totals.get("fiber_g", 0), 30),
    }

    return render_template(
        "health-fitness-tracking/index.html",
        an=an, cal_ring=cal_ring, macros=macros,
        prev_date=prev_date, next_date=next_date,
        user=display_user,
        today_stats=today_stats,
        view_date=view_date,
        meals_by_type=dict(meals_by_type),
        meal_totals=meal_totals,
        nutrition_totals=nutrition_totals,
        calorie_goal=calorie_goal,
        protein_goal=protein_goal,
        carbs_goal=carbs_goal,
        fat_goal=fat_goal,
        today_workouts=today_workouts,
        exercise_calories=exercise_calories,
        water_glasses=water_glasses,
        steps=steps,
        goals=user_goals,
        recent_workouts=recent_workouts,
        logged_in=user is not None,
    )


@blueprint.route("/workouts")
def workouts_page():
    """Workout log with filtering."""
    user = _get_current_user()
    uid = user["id"] if user else 1

    # Filters
    workout_type = request.args.get("type", "")
    date_from = request.args.get("from", "")
    date_to = request.args.get("to", "")

    # Build SQL for filtered query
    where_parts = ["user_id = ?"]
    params = [uid]
    if workout_type:
        where_parts.append("type = ?")
        params.append(workout_type)
    if date_from:
        where_parts.append("date >= ?")
        params.append(date_from)
    if date_to:
        where_parts.append("date <= ?")
        params.append(date_to)

    table = db.get_table_name(SITE, "workouts")
    sql = f"SELECT * FROM [{table}] WHERE {' AND '.join(where_parts)} ORDER BY date DESC LIMIT 50"
    user_workouts = db.execute(sql, tuple(params), fetch="all")

    # Merge in workouts created/edited this session (they live in the overlay,
    # invisible to raw db.execute). Mirror the SQL WHERE clauses in `match`.
    def _match(w):
        if w.get("user_id") != uid:
            return False
        if workout_type and w.get("type") != workout_type:
            return False
        if date_from and w.get("date", "") < date_from:
            return False
        if date_to and w.get("date", "") > date_to:
            return False
        return True

    user_workouts = db.merge_overlay(
        SITE, "workouts", user_workouts, match=_match, sort="-date", limit=50
    )

    # Collect unique workout types for filter dropdown
    types_sql = f"SELECT DISTINCT type FROM [{table}] WHERE user_id = ? ORDER BY type"
    all_types = [r["type"] for r in db.execute(types_sql, (uid,), fetch="all")]

    return render_template(
        "health-fitness-tracking/workouts.html",
        user=user,
        workouts=user_workouts,
        workout_types=all_types,
        current_type=workout_type,
        date_from=date_from,
        date_to=date_to,
        logged_in=user is not None,
        show_log_form=False,
    )


@blueprint.route("/workout/<int:workout_id>")
def workout_detail(workout_id):
    """Single workout detail view."""
    workout = db.get_item(SITE, "workouts", workout_id)
    if not workout:
        abort(404)
    workout_user = db.get_item(SITE, "users", workout["user_id"])
    user = _get_current_user()
    return render_template(
        "health-fitness-tracking/workout_detail.html",
        user=user,
        workout=workout,
        workout_user=workout_user,
        logged_in=user is not None,
    )


@blueprint.route("/nutrition")
def nutrition_page():
    """Daily food diary with expandable meal sections and date navigation."""
    user = _get_current_user()
    uid = user["id"] if user else 1

    # Date navigation
    date_filter = request.args.get("date", _today())
    meal_type_filter = request.args.get("meal_type", "")

    # Build where clause
    where = {"user_id": uid, "date": date_filter}
    if meal_type_filter:
        where["meal_type"] = meal_type_filter

    day_meals = _load_nutrition(where=where, sort="id", limit=50)

    # Group by meal type
    meals_by_type = defaultdict(list)
    for m in day_meals:
        meals_by_type[m["meal_type"]].append(m)

    # Calculate totals per meal and day
    meal_totals = {}
    for mt in ["breakfast", "lunch", "dinner", "snack"]:
        items = meals_by_type.get(mt, [])
        meal_totals[mt] = {
            "calories": sum(m["calories"] for m in items),
            "protein_g": sum(m["protein_g"] for m in items),
            "carbs_g": sum(m["carbs_g"] for m in items),
            "fat_g": sum(m["fat_g"] for m in items),
        }

    day_totals = {
        "calories": sum(m["calories"] for m in day_meals),
        "protein_g": sum(m["protein_g"] for m in day_meals),
        "carbs_g": sum(m["carbs_g"] for m in day_meals),
        "fat_g": sum(m["fat_g"] for m in day_meals),
        "fiber_g": sum(m.get("fiber_g", 0) for m in day_meals),
    }

    # User goals
    display_user = user if user else db.get_item(SITE, "users", 1)
    user_settings = (display_user or {}).get("settings", {})
    calorie_goal = user_settings.get("daily_calorie_target", 2000)
    protein_goal = user_settings.get("daily_protein_target", 150)
    carbs_goal = user_settings.get("daily_carbs_target", 250)
    fat_goal = user_settings.get("daily_fat_target", 65)

    # Prev/next date calculation
    try:
        dt = datetime.strptime(date_filter, "%Y-%m-%d")
        prev_date = (dt - timedelta(days=1)).strftime("%Y-%m-%d")
        next_date = (dt + timedelta(days=1)).strftime("%Y-%m-%d")
    except ValueError:
        prev_date = next_date = date_filter

    return render_template(
        "health-fitness-tracking/nutrition.html",
        user=display_user,
        meals_by_type=dict(meals_by_type),
        meal_totals=meal_totals,
        day_totals=day_totals,
        date_filter=date_filter,
        prev_date=prev_date,
        next_date=next_date,
        calorie_goal=calorie_goal,
        protein_goal=protein_goal,
        carbs_goal=carbs_goal,
        fat_goal=fat_goal,
        meal_type_filter=meal_type_filter,
        logged_in=user is not None,
    )


@blueprint.route("/goals")
def goals_page():
    """Fitness goals tracking."""
    user = _get_current_user()
    uid = user["id"] if user else 1

    goals_data = _load_goals(where={"user_id": uid})
    user_goals_rec = goals_data[0] if goals_data else None
    user_goals = user_goals_rec["goals"] if user_goals_rec else []

    return render_template(
        "health-fitness-tracking/goals.html",
        user=user,
        goals=user_goals,
        goals_record=user_goals_rec,
        logged_in=user is not None,
    )


@blueprint.route("/stats")
def stats_page():
    """Weekly / monthly stats view."""
    user = _get_current_user()
    uid = user["id"] if user else 1

    period = request.args.get("period", "week")
    row_limit = 30 if period == "month" else 7

    # Optional explicit From/To range (filter form) overrides the period window
    date_from = request.args.get("from", "")
    date_to = request.args.get("to", "")
    if date_from or date_to:
        sql = "SELECT * FROM [health_fitness_tracking_daily_stats] WHERE user_id = ?"
        params = [uid]
        if date_from:
            sql += " AND date >= ?"
            params.append(date_from)
        if date_to:
            sql += " AND date <= ?"
            params.append(date_to)
        sql += " ORDER BY date DESC LIMIT 90"
        user_stats = db.execute(sql, tuple(params))
    else:
        user_stats = _load_daily_stats(where={"user_id": uid}, sort="-date", limit=row_limit)

    summary = {}
    if user_stats:
        summary = {
            "period": period,
            "days": len(user_stats),
            "date_from": user_stats[-1]["date"],
            "date_to": user_stats[0]["date"],
            "avg_steps": round(sum(s["steps"] for s in user_stats) / len(user_stats)),
            "total_steps": sum(s["steps"] for s in user_stats),
            "avg_calories": round(sum(s["calories_burned"] for s in user_stats) / len(user_stats)),
            "avg_sleep": round(sum(s["sleep_hours"] for s in user_stats) / len(user_stats), 1),
            "avg_active_min": round(sum(s["active_minutes"] for s in user_stats) / len(user_stats)),
            "total_distance_km": round(sum(s["distance_km"] for s in user_stats), 1),
            "avg_water_ml": round(sum(s["water_ml"] for s in user_stats) / len(user_stats)),
            "weight_start": user_stats[-1].get("weight_kg"),
            "weight_end": user_stats[0].get("weight_kg"),
        }

    charts = _series_charts(user_stats)

    return render_template(
        "health-fitness-tracking/stats.html",
        user=user,
        stats=user_stats,
        summary=summary,
        period=period,
        charts=charts,
        logged_in=user is not None,
    )


# ---------------------------------------------------------------------------
# Inline-editable daily-log grid (edit_by_cell macro)
# ---------------------------------------------------------------------------

# Column layout for the log editor grid. Order here defines the cell column
# index (cell_<row>_<col>) posted by the form and matches the table header.
STATS_GRID_COLS = [
    ("date", "Date", "text"),
    ("steps", "Steps", "int"),
    ("distance_km", "Distance (km)", "float"),
    ("calories_burned", "Calories", "int"),
    ("active_minutes", "Active (min)", "int"),
    ("sleep_hours", "Sleep (h)", "float"),
    ("water_ml", "Water (ml)", "int"),
    ("weight_kg", "Weight (kg)", "float"),
]

# Full default record for a freshly-added daily-stats row (covers every schema
# column so overlay reads return a complete item).
_DAILY_STATS_DEFAULTS = {
    "date": "",
    "steps": 0,
    "distance_km": 0.0,
    "calories_burned": 0,
    "active_minutes": 0,
    "floors_climbed": 0,
    "sleep_hours": 0.0,
    "sleep_quality": "",
    "water_ml": 0,
    "weight_kg": 0.0,
}


def _coerce_cell(raw, ftype):
    """Coerce a raw cell string to the column's type, tolerating blanks."""
    raw = (raw or "").strip()
    if ftype == "int":
        try:
            return int(float(raw)) if raw else 0
        except ValueError:
            return 0
    if ftype == "float":
        try:
            return float(raw) if raw else 0.0
        except ValueError:
            return 0.0
    return raw


@blueprint.route("/log-editor")
def stats_editor_page():
    """Inline-editable grid of recent daily stats (edit_by_cell macro).

    Renders a <form> of cell_<row>_<col> inputs plus a client-side "+ Add row"
    button. Rows are the user's most recent daily-stats entries, fetched with
    SQL-level filter/sort/limit (never a full-table load).
    """
    user = _get_current_user()
    uid = user["id"] if user else 1

    rows = _load_daily_stats(where={"user_id": uid}, sort="-date", limit=14)

    return render_template(
        "health-fitness-tracking/stats_editor.html",
        user=user,
        cols=STATS_GRID_COLS,
        rows=rows,
        logged_in=user is not None,
    )


@blueprint.route("/log-editor/save", methods=["POST"])
def stats_editor_save():
    """Persist inline cell edits from the log-editor grid to the session overlay.

    Reads cell_<row>_<col> values (and a hidden rowid_<row> per existing row).
    Existing rows are updated in place; appended rows without a rowid become new
    daily-stats entries with a db.next_id() primary key. All writes go through
    db.save_item() to the SESSION OVERLAY — base tables are never touched.
    """
    user = _get_current_user()
    uid = user["id"] if user else 1

    ncols = len(STATS_GRID_COLS)

    # Reconstruct grid: row_idx -> {col_idx: value}. Auto-expands to whatever
    # rows/cols were posted (appended rows included).
    grid = {}
    for key, value in request.form.items():
        if not key.startswith("cell_"):
            continue
        parts = key.split("_")
        if len(parts) != 3:
            continue
        try:
            r, c = int(parts[1]), int(parts[2])
        except ValueError:
            continue
        grid.setdefault(r, {})[c] = value

    saved = 0
    for r in sorted(grid.keys()):
        cells = grid[r]
        rowid_raw = request.form.get("rowid_{}".format(r), "").strip()

        # Skip appended rows the user left entirely blank.
        has_content = any(str(cells.get(c, "")).strip() for c in range(ncols))
        if not rowid_raw and not has_content:
            continue

        # Build the edited field values from this row's cells.
        edits = {}
        for c, (field, _label, ftype) in enumerate(STATS_GRID_COLS):
            edits[field] = _coerce_cell(cells.get(c, ""), ftype)

        if rowid_raw:
            try:
                row_id = int(rowid_raw)
            except ValueError:
                continue
            record = db.get_item(SITE, "daily_stats", row_id) or dict(_DAILY_STATS_DEFAULTS)
            record.update(edits)
            record["row_id"] = row_id
            record["user_id"] = uid
        else:
            row_id = db.next_id(SITE, "daily_stats")
            record = dict(_DAILY_STATS_DEFAULTS)
            record.update(edits)
            record["row_id"] = row_id
            record["user_id"] = uid

        db.save_item(SITE, "daily_stats", row_id, record)
        saved += 1

    return redirect(url_for("health-fitness-tracking.stats_editor_page"))


@blueprint.route("/log-workout")
def log_workout_page():
    """Form to log a new workout."""
    user = _get_current_user()
    uid = user["id"] if user else 1
    table = db.get_table_name(SITE, "workouts")
    types_sql = f"SELECT DISTINCT type FROM [{table}] WHERE user_id = ? ORDER BY type"
    all_types = [r["type"] for r in db.execute(types_sql, (uid,), fetch="all")]
    return render_template(
        "health-fitness-tracking/workouts.html",
        user=user,
        workouts=[],
        workout_types=all_types,
        current_type="",
        date_from="",
        date_to="",
        logged_in=user is not None,
        show_log_form=True,
    )


@blueprint.route("/log-workout", methods=["POST"])
def log_workout_submit():
    """Persist a workout logged from the #log-workout-form UI form.

    Mirrors the JSON API (POST /api/workouts) but accepts a plain HTML form
    submission, writes a single row to the SESSION OVERLAY via db.save_item()
    with an overlay-aware db.next_id() primary key, then redirects to the
    Activity log so the new workout is visible.
    """
    user = _get_current_user()
    uid = user["id"] if user else 1

    def _to_int(name, default=0):
        try:
            return int(float(request.form.get(name, "").strip()))
        except (ValueError, TypeError):
            return default

    workout_type = request.form.get("type", "").strip() or "other"
    date = request.form.get("date", "").strip() or _today()

    new_id = db.next_id(SITE, "workouts")
    workout = {
        "id": new_id,
        "user_id": uid,
        "type": workout_type,
        "date": date,
        "start_time": request.form.get("start_time", "").strip(),
        "duration_minutes": _to_int("duration_minutes", 0),
        "calories_burned": _to_int("calories_burned", 0),
        "heart_rate_avg": 0,
        "heart_rate_max": 0,
        "location": request.form.get("location", "").strip(),
        "notes": request.form.get("notes", "").strip(),
        "exercises": "",
        "distance_km": 0.0,
        "elevation_gain_m": 0,
        "companions": "",
        "pace_min_per_km": 0.0,
    }
    db.save_item(SITE, "workouts", new_id, workout)
    emit("booking", user_id=uid, title=f"Workout: {workout['type']}", start=workout["date"], location=workout.get("location", ""))
    return redirect(url_for("health-fitness-tracking.workouts_page"))


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("health-fitness-tracking/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user:
        return render_template("health-fitness-tracking/login.html",
                               error="Invalid username or password")
    stored_pw = user.get("password", "password")
    if password and password != stored_pw:
        return render_template("health-fitness-tracking/login.html", error="Invalid password")
    session["user_id"] = user["id"]
    emit("signup", user_id=user["id"], site_name="health-fitness-tracking", username=request.form.get("username", ""), password=request.form.get("password", ""), email="")
    return redirect(url_for("health-fitness-tracking.index"))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("health-fitness-tracking.index"))


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@blueprint.route("/api/workouts", methods=["GET"])
def api_workouts_list():
    """GET workouts with optional filters: type, from, to, user_id, intensity, sort.

    Macros: filter_by_dropdown (type, intensity), filter_by_date_range (from/to),
            sort_by_ranking (sort param).
    """
    workouts = _load_workouts()

    uid = request.args.get("user_id", type=int)
    workout_type = request.args.get("type", "")
    date_from = request.args.get("from", "")
    date_to = request.args.get("to", "")
    intensity = request.args.get("intensity", "")
    sort_by = request.args.get("sort", "date")

    if uid:
        workouts = [w for w in workouts if w["user_id"] == uid]
    if workout_type:
        workouts = [w for w in workouts if w["type"] == workout_type]
    if date_from:
        workouts = [w for w in workouts if w["date"] >= date_from]
    if date_to:
        workouts = [w for w in workouts if w["date"] <= date_to]
    if intensity:
        if intensity == "low":
            workouts = [w for w in workouts if w.get("heart_rate_avg", 0) < 120]
        elif intensity == "medium":
            workouts = [w for w in workouts if 120 <= w.get("heart_rate_avg", 0) < 150]
        elif intensity == "high":
            workouts = [w for w in workouts if w.get("heart_rate_avg", 0) >= 150]

    # sort_by_ranking support
    reverse = True
    if sort_by == "date":
        key_fn = lambda w: w["date"]
    elif sort_by == "duration":
        key_fn = lambda w: w["duration_minutes"]
    elif sort_by == "calories":
        key_fn = lambda w: w.get("calories_burned", 0)
    elif sort_by == "type":
        key_fn = lambda w: w["type"]
        reverse = False
    elif sort_by == "heart_rate":
        key_fn = lambda w: w.get("heart_rate_avg", 0)
    else:
        key_fn = lambda w: w["date"]

    workouts.sort(key=key_fn, reverse=reverse)
    return jsonify(workouts)


@blueprint.route("/api/workouts", methods=["POST"])
def api_workouts_create():
    """Log a new workout."""
    data = request.get_json(silent=True) or {}
    workouts = _load_workouts()

    required = ["user_id", "type", "date", "duration_minutes"]
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400

    new_id = max((w["id"] for w in workouts), default=0) + 1
    workout = {
        "id": new_id,
        "user_id": data["user_id"],
        "type": data["type"],
        "date": data["date"],
        "start_time": data.get("start_time", ""),
        "duration_minutes": data["duration_minutes"],
        "calories_burned": data.get("calories_burned", 0),
        "heart_rate_avg": data.get("heart_rate_avg"),
        "heart_rate_max": data.get("heart_rate_max"),
        "location": data.get("location", ""),
        "notes": data.get("notes", ""),
    }
    if "distance_km" in data:
        workout["distance_km"] = data["distance_km"]
    if "elevation_gain_m" in data:
        workout["elevation_gain_m"] = data["elevation_gain_m"]
    if "pace_min_per_km" in data:
        workout["pace_min_per_km"] = data["pace_min_per_km"]
    if "exercises" in data:
        workout["exercises"] = data["exercises"]
    if "companions" in data:
        workout["companions"] = data["companions"]

    workouts.append(workout)
    db.save_collection(SITE, "workouts", workouts)
    emit("booking", user_id=workout["user_id"], title=f"Workout: {workout['type']}", start=workout["date"], location=workout.get("location", ""))
    return jsonify(workout), 201


@blueprint.route("/api/workouts/<int:workout_id>", methods=["GET"])
def api_workout_detail(workout_id):
    """Get a single workout."""
    workouts = _load_workouts()
    workout = next((w for w in workouts if w["id"] == workout_id), None)
    if not workout:
        return jsonify({"error": "Workout not found"}), 404
    return jsonify(workout)


@blueprint.route("/api/workouts/<int:workout_id>", methods=["PUT"])
def api_workout_update(workout_id):
    """Update a workout."""
    data = request.get_json(silent=True) or {}
    workouts = _load_workouts()
    workout = next((w for w in workouts if w["id"] == workout_id), None)
    if not workout:
        return jsonify({"error": "Workout not found"}), 404

    updatable = [
        "type", "date", "start_time", "duration_minutes", "calories_burned",
        "heart_rate_avg", "heart_rate_max", "location", "notes", "distance_km",
        "elevation_gain_m", "pace_min_per_km", "exercises", "companions",
    ]
    for key in updatable:
        if key in data:
            workout[key] = data[key]

    db.save_collection(SITE, "workouts", workouts)
    return jsonify(workout)


@blueprint.route("/api/workouts/<int:workout_id>", methods=["DELETE"])
def api_workout_delete(workout_id):
    """Delete a workout."""
    workouts = _load_workouts()
    workout = next((w for w in workouts if w["id"] == workout_id), None)
    if not workout:
        return jsonify({"error": "Workout not found"}), 404
    workouts = [w for w in workouts if w["id"] != workout_id]
    db.save_collection(SITE, "workouts", workouts)
    return jsonify({"deleted": workout_id})


@blueprint.route("/api/daily-stats", methods=["GET"])
def api_daily_stats():
    """GET daily stats with optional date range filter."""
    stats = _load_daily_stats()

    uid = request.args.get("user_id", type=int)
    date_from = request.args.get("from", "")
    date_to = request.args.get("to", "")

    if uid:
        stats = [s for s in stats if s["user_id"] == uid]
    if date_from:
        stats = [s for s in stats if s["date"] >= date_from]
    if date_to:
        stats = [s for s in stats if s["date"] <= date_to]

    stats.sort(key=lambda s: s["date"], reverse=True)
    return jsonify(stats)


@blueprint.route("/api/nutrition", methods=["GET"])
def api_nutrition_list():
    """GET nutrition log with optional filters."""
    nutrition = _load_nutrition()

    uid = request.args.get("user_id", type=int)
    date = request.args.get("date", "")
    meal_type = request.args.get("meal_type", "")

    if uid:
        nutrition = [n for n in nutrition if n["user_id"] == uid]
    if date:
        nutrition = [n for n in nutrition if n["date"] == date]
    if meal_type:
        nutrition = [n for n in nutrition if n["meal_type"] == meal_type]

    nutrition.sort(key=lambda n: n["date"], reverse=True)
    return jsonify(nutrition)


@blueprint.route("/api/nutrition", methods=["POST"])
def api_nutrition_create():
    """Log a meal."""
    data = request.get_json(silent=True) or {}
    nutrition = _load_nutrition()

    required = ["user_id", "date", "meal_type", "description", "calories"]
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400

    new_id = max((n["id"] for n in nutrition), default=0) + 1
    meal = {
        "id": new_id,
        "user_id": data["user_id"],
        "date": data["date"],
        "meal_type": data["meal_type"],
        "description": data["description"],
        "location": data.get("location", ""),
        "calories": data["calories"],
        "protein_g": data.get("protein_g", 0),
        "carbs_g": data.get("carbs_g", 0),
        "fat_g": data.get("fat_g", 0),
        "fiber_g": data.get("fiber_g", 0),
    }
    nutrition.append(meal)
    db.save_collection(SITE, "nutrition", nutrition)
    return jsonify(meal), 201


@blueprint.route("/api/nutrition/<int:meal_id>", methods=["DELETE"])
def api_nutrition_delete(meal_id):
    """Delete a meal entry."""
    nutrition = _load_nutrition()
    meal = next((n for n in nutrition if n["id"] == meal_id), None)
    if not meal:
        return jsonify({"error": "Meal not found"}), 404
    nutrition = [n for n in nutrition if n["id"] != meal_id]
    db.save_collection(SITE, "nutrition", nutrition)
    return jsonify({"deleted": meal_id})


@blueprint.route("/api/goals", methods=["GET"])
def api_goals_list():
    """GET goals, optionally filtered by user_id."""
    goals_data = _load_goals()
    uid = request.args.get("user_id", type=int)
    if uid:
        goals_data = [g for g in goals_data if g["user_id"] == uid]
    return jsonify(goals_data)


@blueprint.route("/api/goals", methods=["POST"])
def api_goals_create():
    """Create a new goal for a user."""
    data = request.get_json(silent=True) or {}
    goals_data = _load_goals()

    uid = data.get("user_id")
    if not uid:
        return jsonify({"error": "Missing user_id"}), 400

    goal = data.get("goal")
    if not goal or "category" not in goal or "target" not in goal:
        return jsonify({"error": "Missing goal with category and target"}), 400

    user_rec = next((g for g in goals_data if g["user_id"] == uid), None)
    if not user_rec:
        new_id = max((g["id"] for g in goals_data), default=0) + 1
        user_rec = {"id": new_id, "user_id": uid, "goals": []}
        goals_data.append(user_rec)

    existing_ids = [g["goal_id"] for g in user_rec["goals"]]
    idx = len(existing_ids) + 1
    goal_id = f"g{uid}-{idx}"
    while goal_id in existing_ids:
        idx += 1
        goal_id = f"g{uid}-{idx}"

    new_goal = {
        "goal_id": goal_id,
        "category": goal["category"],
        "target": goal["target"],
        "unit": goal.get("unit", ""),
        "start_date": goal.get("start_date", _today()),
        "target_date": goal.get("target_date"),
        "status": goal.get("status", "active"),
        "progress_note": goal.get("progress_note", ""),
    }
    user_rec["goals"].append(new_goal)
    db.save_collection(SITE, "goals", goals_data)
    return jsonify(new_goal), 201


@blueprint.route("/api/goals", methods=["PUT"])
def api_goals_update():
    """Update a goal. Requires user_id and goal_id in body."""
    data = request.get_json(silent=True) or {}
    goals_data = _load_goals()

    uid = data.get("user_id")
    goal_id = data.get("goal_id")
    if not uid or not goal_id:
        return jsonify({"error": "Missing user_id or goal_id"}), 400

    user_rec = next((g for g in goals_data if g["user_id"] == uid), None)
    if not user_rec:
        return jsonify({"error": "User goals not found"}), 404

    goal = next((g for g in user_rec["goals"] if g["goal_id"] == goal_id), None)
    if not goal:
        return jsonify({"error": "Goal not found"}), 404

    updatable = ["category", "target", "unit", "start_date", "target_date", "status", "progress_note"]
    for key in updatable:
        if key in data:
            goal[key] = data[key]

    db.save_collection(SITE, "goals", goals_data)
    return jsonify(goal)


@blueprint.route("/api/stats/summary", methods=["GET"])
def api_stats_summary():
    """Return aggregated stats for a period (week or month)."""
    stats = _load_daily_stats()
    uid = request.args.get("user_id", type=int, default=1)
    period = request.args.get("period", "week")

    user_stats = sorted(
        [s for s in stats if s["user_id"] == uid],
        key=lambda s: s["date"],
        reverse=True,
    )

    if period == "month":
        window = user_stats[:30]
    else:
        window = user_stats[:7]

    if not window:
        return jsonify({"error": "No stats found"}), 404

    summary = {
        "period": period,
        "days": len(window),
        "date_from": window[-1]["date"],
        "date_to": window[0]["date"],
        "avg_steps": round(sum(s["steps"] for s in window) / len(window)),
        "total_steps": sum(s["steps"] for s in window),
        "avg_calories_burned": round(sum(s["calories_burned"] for s in window) / len(window)),
        "avg_sleep_hours": round(sum(s["sleep_hours"] for s in window) / len(window), 1),
        "avg_active_minutes": round(sum(s["active_minutes"] for s in window) / len(window)),
        "total_distance_km": round(sum(s["distance_km"] for s in window), 1),
        "avg_water_ml": round(sum(s["water_ml"] for s in window) / len(window)),
        "weight_start": window[-1].get("weight_kg"),
        "weight_end": window[0].get("weight_kg"),
    }
    return jsonify(summary)


@blueprint.route("/api/stats", methods=["GET"])
def api_stats():
    """Return raw daily stats, optionally filtered.

    Macro: extract_by_date_range (from/to).
    """
    stats = _load_daily_stats()
    uid = request.args.get("user_id", type=int)
    date_from = request.args.get("from", "")
    date_to = request.args.get("to", "")

    if uid:
        stats = [s for s in stats if s["user_id"] == uid]
    if date_from:
        stats = [s for s in stats if s["date"] >= date_from]
    if date_to:
        stats = [s for s in stats if s["date"] <= date_to]

    stats.sort(key=lambda s: s["date"], reverse=True)
    return jsonify(stats)


# ---------------------------------------------------------------------------
# Food database search API (USDA foods via FTS5)
# ---------------------------------------------------------------------------

@blueprint.route("/api/foods/search")
def api_food_search():
    """Search the USDA food database by name.

    Returns up to 20 matching foods with nutrition info per 100g.
    """
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    results = db.search(SITE, "foods", q, limit=20)
    return jsonify(results)


# ---------------------------------------------------------------------------
# Macro: search_by_query -- text search across workouts and nutrition
# ---------------------------------------------------------------------------

@blueprint.route("/api/search", methods=["GET"])
def api_search():
    """Full-text search across workouts (notes, type, location) and meals (description).

    Macro: search_by_query
    """
    q = request.args.get("q", "").strip().lower()
    if not q:
        return jsonify([])

    results = []

    for w in _load_workouts():
        searchable = " ".join([
            w.get("type", ""),
            w.get("notes", ""),
            w.get("location", ""),
            " ".join(w.get("exercises", [])),
        ]).lower()
        if q in searchable:
            results.append({"type": "workout", "item": w})

    for m in _load_nutrition():
        searchable = " ".join([
            m.get("description", ""),
            m.get("meal_type", ""),
            m.get("location", ""),
        ]).lower()
        if q in searchable:
            results.append({"type": "meal", "item": m})

    return jsonify(results)


# ---------------------------------------------------------------------------
# Macro: search_by_semantic -- keyword-overlap relevance ranking
# ---------------------------------------------------------------------------

@blueprint.route("/api/search/semantic", methods=["GET"])
def api_search_semantic():
    """Semantic search over workouts using keyword overlap on notes+type+location.

    Macro: search_by_semantic
    """
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])

    scored = []
    for w in _load_workouts():
        text = " ".join([
            w.get("type", ""),
            w.get("notes", ""),
            w.get("location", ""),
            " ".join(w.get("exercises", [])),
        ])
        score = _semantic_score(text, q)
        if score > 0:
            scored.append((score, w))

    scored.sort(key=lambda x: x[0], reverse=True)
    return jsonify([item for _, item in scored])


# ---------------------------------------------------------------------------
# Macro: extract_by_dropdown -- stats per workout type
# ---------------------------------------------------------------------------

@blueprint.route("/api/workouts/stats", methods=["GET"])
def api_workouts_stats():
    """Aggregate statistics for a given workout type.

    Macros: extract_by_dropdown (workout_type), compute_by_dropdown
    """
    workout_type = request.args.get("type", "")
    uid = request.args.get("user_id", type=int)
    workouts = _load_workouts()

    if uid:
        workouts = [w for w in workouts if w["user_id"] == uid]
    if workout_type:
        workouts = [w for w in workouts if w["type"] == workout_type]

    if not workouts:
        return jsonify({"error": "No matching workouts"}), 404

    total_duration = sum(w["duration_minutes"] for w in workouts)
    total_calories = sum(w.get("calories_burned", 0) for w in workouts)
    hr_values = [w["heart_rate_avg"] for w in workouts if w.get("heart_rate_avg")]
    dist_values = [w["distance_km"] for w in workouts if w.get("distance_km")]

    stats = {
        "workout_type": workout_type or "all",
        "count": len(workouts),
        "total_duration_minutes": total_duration,
        "avg_duration_minutes": round(total_duration / len(workouts), 1),
        "total_calories_burned": total_calories,
        "avg_calories_burned": round(total_calories / len(workouts), 1),
        "avg_heart_rate": round(sum(hr_values) / len(hr_values), 1) if hr_values else None,
        "total_distance_km": round(sum(dist_values), 2) if dist_values else None,
        "avg_distance_km": round(sum(dist_values) / len(dist_values), 2) if dist_values else None,
        "date_range": {
            "earliest": min(w["date"] for w in workouts),
            "latest": max(w["date"] for w in workouts),
        },
    }
    return jsonify(stats)


# ---------------------------------------------------------------------------
# Macro: extract_from_table / select_from_table -- compare workouts
# ---------------------------------------------------------------------------

@blueprint.route("/api/workouts/compare", methods=["GET"])
def api_workouts_compare():
    """Compare multiple workouts side-by-side by IDs.

    Macros: extract_from_table, select_from_table
    """
    ids_str = request.args.get("ids", "")
    if not ids_str:
        return jsonify({"error": "Provide ?ids=1,2,3"}), 400

    try:
        ids = [int(x.strip()) for x in ids_str.split(",")]
    except ValueError:
        return jsonify({"error": "IDs must be integers"}), 400

    workouts = _load_workouts()
    selected = [w for w in workouts if w["id"] in ids]
    selected.sort(key=lambda w: ids.index(w["id"]))
    return jsonify(selected)


# ---------------------------------------------------------------------------
# Macro: compute_by_extremum -- find best/worst workout
# ---------------------------------------------------------------------------

@blueprint.route("/api/workouts/extremum", methods=["GET"])
def api_workouts_extremum():
    """Find the workout with the max or min value of a given metric.

    Macro: compute_by_extremum
    Params: metric (duration_minutes|calories_burned|heart_rate_avg|distance_km),
            direction (max|min), user_id (optional), type (optional)
    """
    metric = request.args.get("metric", "calories_burned")
    direction = request.args.get("direction", "max")
    uid = request.args.get("user_id", type=int)
    workout_type = request.args.get("type", "")

    workouts = _load_workouts()
    if uid:
        workouts = [w for w in workouts if w["user_id"] == uid]
    if workout_type:
        workouts = [w for w in workouts if w["type"] == workout_type]

    # Only consider workouts that have the metric
    workouts = [w for w in workouts if w.get(metric) is not None]
    if not workouts:
        return jsonify({"error": "No workouts with that metric"}), 404

    if direction == "min":
        result = min(workouts, key=lambda w: w[metric])
    else:
        result = max(workouts, key=lambda w: w[metric])

    return jsonify({
        "metric": metric,
        "direction": direction,
        "value": result[metric],
        "workout": result,
    })


# ---------------------------------------------------------------------------
# Macro: compute_by_slider -- compute stats for steps/calories above threshold
# ---------------------------------------------------------------------------

@blueprint.route("/api/stats/threshold", methods=["GET"])
def api_stats_threshold():
    """Count days where a metric exceeds a slider-set threshold.

    Macro: compute_by_slider
    Params: metric (steps|calories_burned|active_minutes|sleep_hours|water_ml),
            min_value (number), user_id (optional)
    """
    metric = request.args.get("metric", "steps")
    min_value = request.args.get("min_value", type=float)
    uid = request.args.get("user_id", type=int, default=1)

    if min_value is None:
        return jsonify({"error": "Provide min_value parameter"}), 400

    stats = _load_daily_stats()
    user_stats = [s for s in stats if s["user_id"] == uid]
    above = [s for s in user_stats if s.get(metric, 0) >= min_value]

    return jsonify({
        "metric": metric,
        "min_value": min_value,
        "total_days": len(user_stats),
        "days_above": len(above),
        "percentage": round(100 * len(above) / len(user_stats), 1) if user_stats else 0,
        "avg_value": round(sum(s.get(metric, 0) for s in above) / len(above), 1) if above else 0,
    })


# ---------------------------------------------------------------------------
# Macro: compare_by_date_range -- compare two date windows
# ---------------------------------------------------------------------------

@blueprint.route("/api/stats/compare", methods=["GET"])
def api_stats_compare():
    """Compare aggregated daily stats between two date ranges.

    Macro: compare_by_date_range
    Params: from1, to1, from2, to2, user_id (optional)
    """
    uid = request.args.get("user_id", type=int, default=1)
    from1 = request.args.get("from1", "")
    to1 = request.args.get("to1", "")
    from2 = request.args.get("from2", "")
    to2 = request.args.get("to2", "")

    if not (from1 and to1 and from2 and to2):
        return jsonify({"error": "Provide from1, to1, from2, to2"}), 400

    stats = _load_daily_stats()
    user_stats = [s for s in stats if s["user_id"] == uid]

    window1 = [s for s in user_stats if from1 <= s["date"] <= to1]
    window2 = [s for s in user_stats if from2 <= s["date"] <= to2]

    def _agg(window):
        if not window:
            return None
        return {
            "days": len(window),
            "avg_steps": round(sum(s["steps"] for s in window) / len(window)),
            "avg_calories_burned": round(sum(s["calories_burned"] for s in window) / len(window)),
            "avg_sleep_hours": round(sum(s["sleep_hours"] for s in window) / len(window), 1),
            "avg_active_minutes": round(sum(s["active_minutes"] for s in window) / len(window)),
            "total_distance_km": round(sum(s["distance_km"] for s in window), 1),
            "avg_water_ml": round(sum(s["water_ml"] for s in window) / len(window)),
        }

    period1 = _agg(window1)
    period2 = _agg(window2)

    # Compute diffs
    diff = {}
    if period1 and period2:
        for key in ["avg_steps", "avg_calories_burned", "avg_sleep_hours",
                     "avg_active_minutes", "avg_water_ml"]:
            diff[key] = period2[key] - period1[key]

    return jsonify({
        "period1": {"from": from1, "to": to1, "stats": period1},
        "period2": {"from": from2, "to": to2, "stats": period2},
        "diff": diff,
    })


# ---------------------------------------------------------------------------
# Macro: verify_by_slider -- check if goal target is met with slider threshold
# ---------------------------------------------------------------------------

@blueprint.route("/api/goals/verify", methods=["GET"])
def api_goals_verify():
    """Verify whether a user's actual metric meets a goal target within a tolerance.

    Macro: verify_by_slider
    Params: user_id, goal_id, tolerance (float, e.g. 0.1 for 10% margin)
    """
    uid = request.args.get("user_id", type=int, default=1)
    goal_id = request.args.get("goal_id", "")
    tolerance = request.args.get("tolerance", type=float, default=0.0)

    goals_data = _load_goals()
    user_rec = next((g for g in goals_data if g["user_id"] == uid), None)
    if not user_rec:
        return jsonify({"error": "User goals not found"}), 404

    goal = next((g for g in user_rec["goals"] if g["goal_id"] == goal_id), None)
    if not goal:
        return jsonify({"error": "Goal not found"}), 404

    # Determine actual value based on goal category
    stats = sorted(
        [s for s in _load_daily_stats() if s["user_id"] == uid],
        key=lambda s: s["date"], reverse=True,
    )

    category = goal["category"]
    target = goal["target"]
    actual = None
    metric_name = category

    if category == "daily_steps" and stats:
        recent = stats[:7]
        actual = round(sum(s["steps"] for s in recent) / len(recent))
        metric_name = "avg_daily_steps (7-day)"
    elif category == "weight" and stats:
        actual = stats[0].get("weight_kg")
        metric_name = "current_weight_kg"
    elif category == "sleep" and stats:
        recent = stats[:7]
        actual = round(sum(s["sleep_hours"] for s in recent) / len(recent), 1)
        metric_name = "avg_sleep_hours (7-day)"
    elif category == "workout_frequency":
        workouts = [w for w in _load_workouts() if w["user_id"] == uid]
        if workouts:
            dates = sorted(set(w["date"] for w in workouts))
            if len(dates) >= 7:
                recent_dates = dates[-7:]
            else:
                recent_dates = dates
            weeks = max(1, len(recent_dates) / 7)
            actual = round(len([w for w in workouts if w["date"] >= recent_dates[0]]) / weeks, 1)
        metric_name = "workouts_per_week"
    elif category == "endurance":
        workouts = [w for w in _load_workouts() if w["user_id"] == uid and w.get("distance_km")]
        if workouts:
            actual = max(w["distance_km"] for w in workouts)
        metric_name = "longest_distance_km"

    if actual is None:
        return jsonify({
            "goal_id": goal_id,
            "category": category,
            "target": target,
            "actual": None,
            "met": False,
            "detail": "Could not determine actual value",
        })

    # For weight, "met" means actual <= target (losing weight goal)
    if category == "weight":
        threshold = target * (1 + tolerance)
        met = actual <= threshold
    else:
        threshold = target * (1 - tolerance)
        met = actual >= threshold

    return jsonify({
        "goal_id": goal_id,
        "category": category,
        "target": target,
        "actual": actual,
        "tolerance": tolerance,
        "met": met,
        "metric_name": metric_name,
    })


# ---------------------------------------------------------------------------
# Macro: create_by_checkbox -- log workout with multiple exercise checkboxes
# ---------------------------------------------------------------------------

@blueprint.route("/api/workouts/quick", methods=["POST"])
def api_workouts_quick_create():
    """Create a workout from checkbox-selected exercises and pre-set fields.

    Macro: create_by_checkbox
    Body: {user_id, date, exercises: ["bench press","squats",...], duration_minutes, ...}
    """
    data = request.get_json(silent=True) or {}
    workouts = _load_workouts()

    uid = data.get("user_id")
    exercises = data.get("exercises", [])
    if not uid or not exercises:
        return jsonify({"error": "Provide user_id and exercises list"}), 400

    new_id = max((w["id"] for w in workouts), default=0) + 1
    workout = {
        "id": new_id,
        "user_id": uid,
        "type": data.get("type", "strength_training"),
        "date": data.get("date", _today()),
        "start_time": data.get("start_time", ""),
        "duration_minutes": data.get("duration_minutes", 60),
        "calories_burned": data.get("calories_burned", 0),
        "heart_rate_avg": data.get("heart_rate_avg"),
        "heart_rate_max": data.get("heart_rate_max"),
        "location": data.get("location", ""),
        "notes": data.get("notes", ""),
        "exercises": exercises,
    }
    workouts.append(workout)
    db.save_collection(SITE, "workouts", workouts)
    return jsonify(workout), 201


# ---------------------------------------------------------------------------
# Macro: submit_by_query -- search and submit a meal by description
# ---------------------------------------------------------------------------

@blueprint.route("/api/nutrition/quick", methods=["POST"])
def api_nutrition_quick():
    """Log a meal by searching common foods and submitting.

    Macro: submit_by_query
    Body: {user_id, query (food description), meal_type, date}
    Estimates calories from description length as a simple heuristic.
    """
    data = request.get_json(silent=True) or {}
    nutrition = _load_nutrition()

    uid = data.get("user_id")
    query = data.get("query", "").strip()
    if not uid or not query:
        return jsonify({"error": "Provide user_id and query"}), 400

    # Simple calorie estimation heuristic based on keywords
    cal_est = 400  # default
    low_cal = ["salad", "soup", "yogurt", "fruit", "vegetables", "oatmeal"]
    high_cal = ["burger", "pizza", "pasta", "steak", "fries", "cake"]
    q_lower = query.lower()
    if any(w in q_lower for w in low_cal):
        cal_est = 250
    elif any(w in q_lower for w in high_cal):
        cal_est = 650

    new_id = max((n["id"] for n in nutrition), default=0) + 1
    meal = {
        "id": new_id,
        "user_id": uid,
        "date": data.get("date", _today()),
        "meal_type": data.get("meal_type", "lunch"),
        "description": query,
        "location": data.get("location", ""),
        "calories": data.get("calories", cal_est),
        "protein_g": data.get("protein_g", 20),
        "carbs_g": data.get("carbs_g", 40),
        "fat_g": data.get("fat_g", 15),
        "fiber_g": data.get("fiber_g", 5),
    }
    nutrition.append(meal)
    db.save_collection(SITE, "nutrition", nutrition)
    return jsonify(meal), 201


# ---------------------------------------------------------------------------
# Macro: configure_by_slider -- set daily targets / notification thresholds
# ---------------------------------------------------------------------------

@blueprint.route("/api/users/<int:user_id>/settings", methods=["GET"])
def api_user_settings_get(user_id):
    """Get user settings (daily targets).

    Macro: configure_by_slider (read current config)
    """
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        return jsonify({"error": "User not found"}), 404
    settings = user.get("settings", {
        "daily_step_target": 10000,
        "daily_calorie_target": 2200,
        "daily_water_target_ml": 2500,
        "sleep_target_hours": 7.5,
        "heart_rate_alert_bpm": 180,
    })
    return jsonify({"user_id": user_id, "settings": settings})


@blueprint.route("/api/users/<int:user_id>/settings", methods=["PUT"])
def api_user_settings_update(user_id):
    """Update user settings (daily targets set via sliders).

    Macro: configure_by_slider
    Body: {daily_step_target, daily_calorie_target, ...}
    """
    data = request.get_json(silent=True) or {}
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        return jsonify({"error": "User not found"}), 404

    if "settings" not in user:
        user["settings"] = {
            "daily_step_target": 10000,
            "daily_calorie_target": 2200,
            "daily_water_target_ml": 2500,
            "sleep_target_hours": 7.5,
            "heart_rate_alert_bpm": 180,
        }

    allowed = ["daily_step_target", "daily_calorie_target", "daily_water_target_ml",
               "sleep_target_hours", "heart_rate_alert_bpm"]
    for key in allowed:
        if key in data:
            user["settings"][key] = data[key]

    db.save_collection(SITE, "users", users)
    return jsonify({"user_id": user_id, "settings": user["settings"]})


# ---------------------------------------------------------------------------
# Macro: play_by_dropdown -- replay a workout session by type
# ---------------------------------------------------------------------------

@blueprint.route("/api/workouts/replay", methods=["GET"])
def api_workouts_replay():
    """Get a workout replay timeline (step-by-step breakdown) by workout type.

    Macro: play_by_dropdown
    Params: type (workout type dropdown), user_id (optional)
    Returns the most recent workout of that type with a synthesized timeline.
    """
    workout_type = request.args.get("type", "")
    uid = request.args.get("user_id", type=int)

    if not workout_type:
        return jsonify({"error": "Provide type parameter"}), 400

    workouts = _load_workouts()
    if uid:
        workouts = [w for w in workouts if w["user_id"] == uid]
    workouts = [w for w in workouts if w["type"] == workout_type]
    workouts.sort(key=lambda w: w["date"], reverse=True)

    if not workouts:
        return jsonify({"error": "No workouts of that type found"}), 404

    workout = workouts[0]
    duration = workout["duration_minutes"]

    # Synthesize a timeline from the workout data
    timeline = []
    hr_avg = workout.get("heart_rate_avg", 120)
    hr_max = workout.get("heart_rate_max", 160)
    exercises = workout.get("exercises", [])

    # Warm-up phase
    timeline.append({
        "minute": 0,
        "phase": "warm_up",
        "heart_rate": max(60, hr_avg - 40),
        "description": "Warm-up: light stretching and mobility",
    })

    if exercises:
        per_exercise = max(1, (duration - 10) // len(exercises))
        for i, ex in enumerate(exercises):
            minute = 5 + i * per_exercise
            if minute >= duration:
                break
            progress = (i + 1) / len(exercises)
            hr = int(hr_avg - 20 + 40 * progress)
            hr = min(hr, hr_max)
            timeline.append({
                "minute": minute,
                "phase": "active",
                "heart_rate": hr,
                "description": f"Exercise: {ex}",
            })
    else:
        # Generic phases for cardio
        phases = ["building_pace", "steady_state", "peak_effort", "cool_down"]
        for i, phase in enumerate(phases):
            minute = int(duration * (i + 1) / (len(phases) + 1))
            progress = (i + 1) / len(phases)
            hr = int(hr_avg - 20 + (hr_max - hr_avg + 20) * progress)
            if phase == "cool_down":
                hr = max(80, hr_avg - 20)
            timeline.append({
                "minute": minute,
                "phase": phase,
                "heart_rate": min(hr, hr_max),
                "description": phase.replace("_", " ").title(),
            })

    # Cool-down
    timeline.append({
        "minute": duration,
        "phase": "finished",
        "heart_rate": max(70, hr_avg - 30),
        "description": "Workout complete. Cool down.",
    })

    return jsonify({
        "workout": workout,
        "timeline": timeline,
        "total_minutes": duration,
    })


# ---------------------------------------------------------------------------
# Macro: play_by_playback -- replay daily stats over time
# ---------------------------------------------------------------------------

@blueprint.route("/api/stats/playback", methods=["GET"])
def api_stats_playback():
    """Get daily stats as a time-series for animated playback.

    Macro: play_by_playback
    Params: user_id, from, to, metric (steps|calories_burned|weight_kg|sleep_hours)
    Returns ordered data points for playback animation.
    """
    uid = request.args.get("user_id", type=int, default=1)
    date_from = request.args.get("from", "")
    date_to = request.args.get("to", "")
    metric = request.args.get("metric", "steps")

    stats = _load_daily_stats()
    user_stats = [s for s in stats if s["user_id"] == uid]

    if date_from:
        user_stats = [s for s in user_stats if s["date"] >= date_from]
    if date_to:
        user_stats = [s for s in user_stats if s["date"] <= date_to]

    user_stats.sort(key=lambda s: s["date"])

    frames = []
    running_total = 0
    for i, s in enumerate(user_stats):
        val = s.get(metric, 0)
        running_total += val if metric != "weight_kg" else 0
        frames.append({
            "frame": i + 1,
            "date": s["date"],
            "value": val,
            "running_avg": round((running_total / (i + 1)), 1) if metric != "weight_kg" else val,
        })

    return jsonify({
        "metric": metric,
        "total_frames": len(frames),
        "frames": frames,
    })


# ---------------------------------------------------------------------------
# Macro: export_by_dropdown -- export data as CSV or JSON
# ---------------------------------------------------------------------------

@blueprint.route("/api/export", methods=["GET"])
def api_export():
    """Export workouts, stats, or nutrition as CSV or JSON.

    Macro: export_by_dropdown
    Params: format (csv|json), data_type (workouts|stats|nutrition), user_id (optional)
    """
    fmt = request.args.get("format", "json")
    data_type = request.args.get("data_type", "workouts")
    uid = request.args.get("user_id", type=int)

    if data_type == "workouts":
        data = _load_workouts()
        if uid:
            data = [d for d in data if d["user_id"] == uid]
        columns = ["id", "user_id", "type", "date", "start_time",
                    "duration_minutes", "calories_burned", "heart_rate_avg",
                    "heart_rate_max", "location", "notes"]
    elif data_type == "stats":
        data = _load_daily_stats()
        if uid:
            data = [d for d in data if d["user_id"] == uid]
        columns = ["date", "user_id", "steps", "distance_km", "calories_burned",
                    "active_minutes", "floors_climbed", "sleep_hours",
                    "sleep_quality", "water_ml", "weight_kg"]
    elif data_type == "nutrition":
        data = _load_nutrition()
        if uid:
            data = [d for d in data if d["user_id"] == uid]
        columns = ["id", "user_id", "date", "meal_type", "description",
                    "calories", "protein_g", "carbs_g", "fat_g", "fiber_g"]
    else:
        return jsonify({"error": "data_type must be workouts, stats, or nutrition"}), 400

    if fmt == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in data:
            writer.writerow(row)
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={data_type}.csv"},
        )
    else:
        return jsonify(data)


# ---------------------------------------------------------------------------
# Macro: navigate_by_dropdown -- user profile dropdown
# ---------------------------------------------------------------------------

@blueprint.route("/api/users", methods=["GET"])
def api_users_list():
    """List all users (for profile dropdown navigation).

    Macro: navigate_by_dropdown (select user profile from dropdown)
    """
    users = _load_users()
    return jsonify([{
        "id": u["id"],
        "username": u["username"],
        "display_name": u["display_name"],
        "activity_level": u["activity_level"],
    } for u in users])


@blueprint.route("/api/users/<int:user_id>", methods=["GET"])
def api_user_detail(user_id):
    """Get full user profile.

    Macro: navigate_by_route
    """
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(user)


# ---------------------------------------------------------------------------
# Macro: delete_from_table -- already exists (api_workout_delete, api_nutrition_delete)
# Macro: edit_by_form -- already exists (api_workout_update, api_goals_update)
# Macro: create_from_free_text -- already exists (api_workouts_create, api_nutrition_create)
# Macro: navigate_by_route -- already exists (workout_detail, api_workout_detail)
# Macro: filter_by_dropdown -- already exists (api_workouts_list type filter)
# Macro: filter_by_date_range -- already exists (api_workouts_list from/to)
# Macro: extract_by_route -- already exists (api_workout_detail)
# Macro: extract_by_date_range -- already exists (api_stats from/to, api_daily_stats)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Macro: workout types list (for dropdowns)
# ---------------------------------------------------------------------------

@blueprint.route("/api/workout-types", methods=["GET"])
def api_workout_types():
    """Return all known workout types.

    Used by filter_by_dropdown, play_by_dropdown, extract_by_dropdown UI.
    """
    workouts = _load_workouts()
    uid = request.args.get("user_id", type=int)
    if uid:
        workouts = [w for w in workouts if w["user_id"] == uid]
    types = sorted(set(w["type"] for w in workouts))
    return jsonify(types)
