#!/usr/bin/env python
"""Extend Alex Rivera's (user 1) health-fitness-tracking logs so the tracker is
current. Seed data stopped at 2026-03-31; "today" is 2026-08-02, so the
dashboard shows ~4-month-old data. This fills daily_stats, workouts, and
nutrition from 2026-04-01 through 2026-08-02, continuing his existing arc
(strength + half-marathon training, slow weight cut, weekend hikes with Mia),
and refreshes the goal progress notes.

Idempotent: skips if any daily_stats row already exists on/after 2026-04-01.
Deterministic (seeded RNG). Writes to the base tables (visible to all sessions).
"""
import json
import os
import pathlib
import random
import sqlite3
import sys
from datetime import date, timedelta

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _resolve_db():
    from app import create_app
    import app.db as _appdb
    create_app()
    return _appdb._DB_PATH


DB = os.environ.get("MINIWEB_DB") or _resolve_db()
UID = 1
START = date(2026, 4, 1)
END = date(2026, 8, 2)          # "today"
RACE_DAY = date(2026, 7, 31)    # Lakeport Summer Half-Marathon
rnd = random.Random(20260402)

GYM = "Brooks Fitness, 1200 Main St, Lakeport, WA"
LAKE_LOOP = "Cascadia Lake Loop, Lakeport, WA"
TRAILS = "Wildflower Meadow Trail, Cascadia County, WA"

BREAKFASTS = [
    ("Oatmeal with banana, blueberries, and almond butter", "Home", 420, 14, 62, 15, 8),
    ("Greek yogurt parfait with granola and honey", "Home", 350, 24, 40, 10, 5),
    ("Three eggs, avocado toast, and a side of berries", "Home", 480, 26, 34, 26, 7),
    ("Protein smoothie: whey, spinach, banana, peanut butter", "Home", 390, 32, 45, 9, 6),
    ("Egg-white veggie scramble with whole-grain toast", "Home", 360, 28, 32, 12, 6),
]
LUNCHES = [
    ("Grilled chicken wrap with avocado and mixed greens, side salad", "Summit Trail Brewing Co., 520 Main St, Lakeport", 680, 38, 65, 28, 9),
    ("Poke bowl: ahi, brown rice, edamame, seaweed", "Lakeport Poke, 88 Harbor Dr", 620, 40, 70, 18, 7),
    ("Turkey and hummus sandwich with lentil soup", "Home", 560, 34, 55, 20, 8),
    ("Burrito bowl: chicken, black beans, rice, salsa, guac", "Cascadia Cantina, 210 Main St", 720, 42, 80, 24, 12),
    ("Grilled salmon salad with quinoa and vinaigrette", "Home", 590, 40, 44, 26, 9),
]
DINNERS = [
    ("Baked salmon, wild rice, and roasted broccoli", "Home", 650, 45, 55, 26, 8),
    ("Chicken and vegetable stir-fry over jasmine rice", "Home", 600, 44, 60, 18, 7),
    ("Whole-wheat spaghetti with turkey meatballs", "Home", 780, 40, 90, 28, 9),
    ("Carne asada tacos with black beans", "Cascadia Cantina, 210 Main St", 700, 38, 72, 30, 10),
    ("Seared ahi tuna, sweet potato, and asparagus", "Home", 640, 44, 48, 24, 7),
    ("Grilled chicken, mashed cauliflower, and green beans", "Home", 560, 46, 30, 22, 8),
]
SNACKS = [
    ("Protein bar", "Brooks Fitness", 220, 20, 24, 7, 3),
    ("Apple with peanut butter", "Home", 250, 7, 30, 12, 5),
    ("Trail mix and a banana", "Home", 300, 8, 40, 14, 5),
    ("Greek yogurt with honey", "Home", 150, 15, 18, 4, 0),
    ("Cottage cheese and pineapple", "Home", 180, 22, 16, 3, 1),
]


def sleep_quality(h):
    if h >= 7.8: return "excellent"
    if h >= 7.3: return "good"
    if h >= 6.7: return "fair"
    return "poor"


def weight_for(d):
    """Slow cut 78.0 -> ~77.5 by end June, then maintain, with daily noise."""
    days = (d - START).days
    base = 78.0 - 0.5 * min(days / 90.0, 1.0)
    return round(base + rnd.uniform(-0.35, 0.35), 1)


def long_run_km(d):
    """Sunday long-run progression building to the half-marathon."""
    if d > RACE_DAY:                       # August recovery block
        return round(rnd.uniform(8.0, 12.0), 1)
    weeks = (d - START).days // 7
    return round(min(12.0 + weeks * 0.7, 19.0), 1)


def main():
    conn = sqlite3.connect(DB, timeout=60)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    existing = cur.execute(
        "SELECT COUNT(*) c FROM health_fitness_tracking_daily_stats WHERE user_id=? AND date>=?",
        (UID, START.isoformat())).fetchone()["c"]
    if existing:
        print(f"Already have {existing} daily_stats rows on/after {START} — skipping.")
        conn.close()
        return

    ds_id = (cur.execute("SELECT MAX(row_id) m FROM health_fitness_tracking_daily_stats").fetchone()["m"] or 0)
    w_id = (cur.execute("SELECT MAX(id) m FROM health_fitness_tracking_workouts").fetchone()["m"] or 0)
    n_id = (cur.execute("SELECT MAX(id) m FROM health_fitness_tracking_nutrition").fetchone()["m"] or 0)

    bench = 210  # lbs, progresses toward 225 by late June
    n_days = n_wk = n_nut = 0
    d = START
    while d <= END:
        wd = d.weekday()  # 0=Mon
        workouts = []     # (type, dur, cal, hr_avg, hr_max, loc, notes, exercises, dist, elev, companions, pace)

        if d == RACE_DAY:
            workouts.append(("running", 118, 1180, 168, 184, "Lakeport Waterfront (Race Start), Lakeport, WA",
                             "Lakeport Summer Half-Marathon! Finished 21.1 km in 1:58:xx. Months of training paid off.",
                             "", 21.1, 40, json.dumps([]), round(118 / 21.1, 2)))
        elif wd == 0 and rnd.random() < 0.9:   # Mon push
            if d < date(2026, 7, 1) and rnd.random() < 0.25:
                bench = min(bench + 5, 225)
            workouts.append(("strength_training", 60, 415 + rnd.randint(-25, 35), 126, 160, GYM,
                             f"Push day (chest/shoulders/triceps). Bench {bench} lbs.",
                             json.dumps(["bench press", "overhead press", "incline dumbbell press", "triceps pushdown"]),
                             0.0, 0, "", 0.0))
        elif wd == 1 and rnd.random() < 0.85:  # Tue tempo run
            dist = round(rnd.uniform(6.0, 8.5), 1)
            workouts.append(("running", int(dist * 5.7), int(dist * 78), 158, 179, LAKE_LOOP,
                             "Tempo run. Working on race pace.", "", dist, 0, "", round(rnd.uniform(5.4, 5.9), 2)))
        elif wd == 2 and rnd.random() < 0.9:   # Wed pull
            workouts.append(("strength_training", 58, 400 + rnd.randint(-20, 30), 123, 158, GYM,
                             "Pull day (back/biceps). Deadlifts and rows.",
                             json.dumps(["deadlift", "pull-ups", "barbell row", "face pull"]), 0.0, 0, "", 0.0))
        elif wd == 3 and rnd.random() < 0.75:  # Thu cross-train
            if rnd.random() < 0.5:
                dist = round(rnd.uniform(20.0, 32.0), 1)
                workouts.append(("cycling", int(dist * 2.6), int(dist * 24), 138, 162, "Cascadia Valley Bike Path, WA",
                                 "Easy cycling recovery.", "", dist, rnd.randint(80, 260), "", 0.0))
            else:
                dist = round(rnd.uniform(4.5, 6.0), 1)
                workouts.append(("running", int(dist * 6.1), int(dist * 72), 148, 168, LAKE_LOOP,
                                 "Easy shakeout run.", "", dist, 0, "", round(rnd.uniform(5.9, 6.4), 2)))
        elif wd == 4 and rnd.random() < 0.8:   # Fri legs
            workouts.append(("strength_training", 62, 445 + rnd.randint(-25, 35), 131, 166, GYM,
                             "Leg day. Squats, lunges, calf raises.",
                             json.dumps(["back squat", "romanian deadlift", "walking lunge", "leg press"]), 0.0, 0, "", 0.0))
        elif wd == 5:                          # Sat hike or basketball
            r = rnd.random()
            if r < 0.5:
                dist = round(rnd.uniform(8.0, 13.0), 1)
                comp = json.dumps(["Mia Torres"]) if rnd.random() < 0.6 else ""
                note = "Saturday trail hike" + (" with Mia." if comp else ". Solo miles.")
                workouts.append(("hiking", int(dist * 12 + rnd.randint(-10, 20)), int(dist * 55), 129, 152, TRAILS,
                                 note, "", dist, rnd.randint(280, 520), comp, 0.0))
            elif r < 0.72:
                workouts.append(("basketball", 75, 560 + rnd.randint(-40, 60), 149, 178, "Lakeport Community Rec Center, WA",
                                 "Pickup basketball with the crew.", "", 0.0, 0, json.dumps(["Marcus Chen", "Nathan Brooks"]), 0.0))
        elif wd == 6 and rnd.random() < 0.9 and d != RACE_DAY:  # Sun long run
            dist = long_run_km(d)
            dur = int(dist * 5.95)
            workouts.append(("running", dur, int(dist * 80), 154, 178, "Cascadia Lake Full Loop, Lakeport, WA",
                             f"Sunday long run: {dist} km." + (" Race taper." if RACE_DAY - timedelta(days=14) <= d < RACE_DAY else ""),
                             "", dist, rnd.randint(0, 60), "", round(rnd.uniform(5.7, 6.2), 2)))

        # --- daily stats (partly driven by the day's workouts) ---
        run_hike_km = sum(w[8] for w in workouts if w[0] in ("running", "hiking"))
        base_steps = rnd.randint(7800, 11500) + int(run_hike_km * 1250)
        steps = min(base_steps, 26000)
        dist_km = round(steps * 0.00072, 2)
        wk_cal = sum(w[2] for w in workouts)
        cals = 1950 + int(wk_cal * 0.55) + rnd.randint(-60, 120)
        active = 22 + int(sum(w[1] for w in workouts) * 0.5) + rnd.randint(-5, 12)
        floors = rnd.randint(6, 16) + (rnd.randint(8, 30) if any(w[0] == "hiking" for w in workouts) else 0)
        sleep = round(rnd.uniform(6.5, 8.1) + (0.2 if wd >= 5 else 0), 1)
        water = rnd.randint(1800, 3200)
        ds_id += 1
        cur.execute(
            "INSERT INTO health_fitness_tracking_daily_stats "
            "(row_id,date,user_id,steps,distance_km,calories_burned,active_minutes,floors_climbed,sleep_hours,sleep_quality,water_ml,weight_kg) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (ds_id, d.isoformat(), UID, steps, dist_km, cals, active, floors, sleep,
             sleep_quality(sleep), water, weight_for(d)))
        n_days += 1

        for (typ, dur, cal, hra, hrm, loc, notes, exs, dkm, elev, comp, pace) in workouts:
            st = {"strength_training": "06:30", "running": "06:45", "hiking": "08:00",
                  "cycling": "17:30", "basketball": "18:30"}.get(typ, "07:00")
            w_id += 1
            cur.execute(
                "INSERT INTO health_fitness_tracking_workouts "
                "(id,user_id,type,date,start_time,duration_minutes,calories_burned,heart_rate_avg,heart_rate_max,location,notes,exercises,distance_km,elevation_gain_m,companions,pace_min_per_km) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (w_id, UID, typ, d.isoformat(), st, dur, cal, hra, hrm, loc, notes, exs, dkm, elev, comp, pace))
            n_wk += 1

        # --- nutrition: full logs for the last 2 weeks, sprinkled before ---
        recent = d >= END - timedelta(days=13)
        if recent or rnd.random() < 0.30:
            meals = [("breakfast", rnd.choice(BREAKFASTS)), ("lunch", rnd.choice(LUNCHES)), ("dinner", rnd.choice(DINNERS))]
            if recent and rnd.random() < 0.6:
                meals.append(("snack", rnd.choice(SNACKS)))
            if not recent:                       # earlier days: 1-2 logged meals only
                meals = rnd.sample(meals, rnd.randint(1, 2))
            for meal_type, (desc, locn, cal, p, cb, f, fi) in meals:
                n_id += 1
                cur.execute(
                    "INSERT INTO health_fitness_tracking_nutrition "
                    "(id,user_id,date,meal_type,description,location,calories,protein_g,carbs_g,fat_g,fiber_g) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (n_id, UID, d.isoformat(), meal_type, desc, locn, cal, p, cb, f, fi))
                n_nut += 1

        d += timedelta(days=1)

    # --- refresh goal progress notes to reflect the extended timeline ---
    grow = cur.execute("SELECT id, goals FROM health_fitness_tracking_goals WHERE user_id=?", (UID,)).fetchone()
    if grow:
        goals = json.loads(grow["goals"]) if isinstance(grow["goals"], str) else grow["goals"]
        updates = {
            "daily_steps": ("active", "Averaging ~11,200 steps/day through spring and summer. Consistently above target."),
            "workout_frequency": ("active", "Holding 3–4 sessions/week at Brooks Fitness plus weekend runs."),
            "endurance": ("achieved", "Completed the Lakeport Summer Half-Marathon on 2026-07-31 in about 1:58. Goal met!"),
            "strength": ("achieved", "Hit 225 lbs bench 1RM in late June. Now maintaining and adding volume."),
            "weight": ("achieved", "Reached 78 kg in June; maintaining ~77.6 kg since."),
            "sleep": ("active", "Averaging ~7.2 hours; better on weekends, weekdays still improving."),
        }
        for g in goals:
            if g.get("category") in updates:
                status, note = updates[g["category"]]
                g["status"] = status
                g["progress_note"] = note
        cur.execute("UPDATE health_fitness_tracking_goals SET goals=? WHERE id=?",
                    (json.dumps(goals), grow["id"]))

    conn.commit()
    conn.close()
    print(f"Seeded {n_days} daily_stats, {n_wk} workouts, {n_nut} nutrition entries "
          f"for {START}..{END}; refreshed goal notes.")


if __name__ == "__main__":
    main()
