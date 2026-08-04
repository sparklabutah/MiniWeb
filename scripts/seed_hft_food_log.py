#!/usr/bin/env python
"""Re-log Alex Rivera's (user 1) nutrition the way a real food tracker works:
individual food items with real gram portions per meal, instead of one
freeform "meal description" row. Each item's macros are scaled from accurate
per-100g values for common whole foods, so meals total realistic calories/macros.

Replaces ALL user-1 nutrition (via db.save_collection, which keeps the FTS
index in sync) with itemized logs from 2026-01-01 through 2026-08-02, denser
for the last three weeks (people log more consistently recently) and with
realistic gaps earlier. Deterministic (seeded RNG).
"""
import pathlib
import random
import sys
from datetime import date, timedelta

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app import create_app
from app import db

create_app()
SITE = "health-fitness-tracking"
UID = 1
START = date(2026, 1, 1)
END = date(2026, 8, 2)
DENSE_FROM = date(2026, 7, 12)     # last ~3 weeks: log every day
rnd = random.Random(20260803)

# name -> (label, kcal, protein, carbs, fat, fiber) per 100 g
F = {
    "oats":        ("Oatmeal, rolled oats (dry)", 375, 13, 68, 6.5, 10),
    "banana":      ("Banana", 89, 1.1, 23, 0.3, 2.6),
    "blueberries": ("Blueberries", 57, 0.7, 14, 0.3, 2.4),
    "strawberries":("Strawberries", 32, 0.7, 7.7, 0.3, 2.0),
    "almond_butter":("Almond butter", 614, 21, 19, 56, 10),
    "peanut_butter":("Peanut butter", 588, 25, 20, 50, 6),
    "eggs":        ("Eggs, whole (cooked)", 155, 13, 1.1, 11, 0),
    "ww_toast":    ("Whole-wheat toast", 250, 11, 43, 3.5, 6),
    "avocado":     ("Avocado", 160, 2, 9, 15, 7),
    "greek_yogurt":("Greek yogurt, plain nonfat", 59, 10, 3.6, 0.4, 0),
    "granola":     ("Granola", 471, 10, 64, 20, 7),
    "honey":       ("Honey", 304, 0.3, 82, 0, 0.2),
    "whey":        ("Whey protein powder", 400, 80, 8, 6, 2),
    "spinach":     ("Spinach", 23, 2.9, 3.6, 0.4, 2.2),
    "chicken":     ("Chicken breast, grilled", 165, 31, 0, 3.6, 0),
    "brown_rice":  ("Brown rice, cooked", 123, 2.7, 26, 1, 1.8),
    "white_rice":  ("Jasmine rice, cooked", 130, 2.7, 28, 0.3, 0.4),
    "broccoli":    ("Broccoli, steamed", 35, 2.4, 7, 0.4, 3.3),
    "salmon":      ("Salmon, baked", 208, 22, 0, 13, 0),
    "sweet_potato":("Sweet potato, baked", 90, 2, 21, 0.1, 3.3),
    "mixed_greens":("Mixed greens salad", 20, 1.5, 3, 0.2, 1.5),
    "olive_oil":   ("Olive oil", 884, 0, 0, 100, 0),
    "quinoa":      ("Quinoa, cooked", 120, 4.4, 21, 1.9, 2.8),
    "turkey_ground":("Ground turkey (93%), cooked", 200, 27, 0, 10, 0),
    "ww_pasta":    ("Whole-wheat pasta, cooked", 158, 6, 31, 1, 4),
    "marinara":    ("Marinara sauce", 60, 1.6, 9, 2, 2),
    "black_beans": ("Black beans, cooked", 132, 8.9, 24, 0.5, 8.7),
    "tortilla":    ("Flour tortilla", 310, 8, 51, 8, 3),
    "ahi":         ("Ahi tuna, seared", 130, 28, 0, 1, 0),
    "turkey_deli": ("Turkey breast, deli", 104, 17, 4, 2, 0),
    "ww_wrap":     ("Whole-wheat wrap", 290, 9, 49, 7, 5),
    "hummus":      ("Hummus", 166, 8, 14, 10, 6),
    "lentil_soup": ("Lentil soup", 60, 4, 10, 1, 3),
    "protein_bar": ("Protein bar", 350, 33, 40, 10, 12),
    "apple":       ("Apple", 52, 0.3, 14, 0.2, 2.4),
    "trail_mix":   ("Trail mix", 462, 14, 45, 29, 7),
    "cottage":     ("Cottage cheese, low-fat", 98, 11, 3.4, 4.3, 0),
    "almonds":     ("Almonds", 579, 21, 22, 50, 12),
}

# meal templates: list of (food_key, grams)
BREAKFAST = [
    [("oats", 50), ("banana", 118), ("blueberries", 75), ("almond_butter", 16)],
    [("eggs", 100), ("ww_toast", 56), ("avocado", 68)],
    [("greek_yogurt", 170), ("granola", 45), ("strawberries", 100), ("honey", 21)],
    [("whey", 32), ("banana", 118), ("spinach", 60), ("peanut_butter", 24)],
    [("eggs", 150), ("spinach", 60), ("ww_toast", 56)],
]
LUNCH = [
    [("chicken", 150), ("brown_rice", 150), ("broccoli", 100), ("olive_oil", 8)],
    [("ww_wrap", 62), ("turkey_deli", 60), ("hummus", 30), ("mixed_greens", 60)],
    [("salmon", 140), ("quinoa", 140), ("broccoli", 100)],
    [("chicken", 150), ("black_beans", 100), ("white_rice", 150), ("mixed_greens", 60)],
    [("ahi", 140), ("white_rice", 150), ("avocado", 68), ("mixed_greens", 60)],
    [("chicken", 130), ("mixed_greens", 90), ("olive_oil", 10), ("lentil_soup", 245)],
]
DINNER = [
    [("salmon", 140), ("sweet_potato", 130), ("broccoli", 100), ("olive_oil", 8)],
    [("turkey_ground", 120), ("ww_pasta", 140), ("marinara", 120)],
    [("chicken", 150), ("white_rice", 150), ("broccoli", 100), ("olive_oil", 8)],
    [("turkey_ground", 120), ("tortilla", 98), ("black_beans", 100), ("mixed_greens", 60)],
    [("ahi", 140), ("brown_rice", 150), ("avocado", 68), ("broccoli", 100)],
    [("chicken", 160), ("sweet_potato", 130), ("mixed_greens", 90), ("olive_oil", 10)],
]
SNACK = [
    [("protein_bar", 60)],
    [("apple", 180), ("peanut_butter", 24)],
    [("greek_yogurt", 170), ("honey", 21)],
    [("trail_mix", 40)],
    [("cottage", 150), ("blueberries", 75)],
    [("almonds", 28), ("banana", 118)],
]

RESTAURANTS = ["Summit Trail Brewing Co., 520 Main St, Lakeport",
               "Cascadia Cantina, 210 Main St, Lakeport",
               "Lakeport Poke, 88 Harbor Dr"]


def scale(key, grams):
    label, cal, p, c, f, fi = F[key]
    r = grams / 100.0
    return {
        "label": f"{label} ({grams} g)",
        "calories": round(cal * r),
        "protein_g": round(p * r),
        "carbs_g": round(c * r),
        "fat_g": round(f * r),
        "fiber_g": round(fi * r),
    }


def main():
    rows = []
    nid = 0
    d = START
    n_days = 0
    while d <= END:
        dense = d >= DENSE_FROM
        logged = dense or rnd.random() < 0.55
        if logged:
            meals = [("breakfast", rnd.choice(BREAKFAST)),
                     ("lunch", rnd.choice(LUNCH)),
                     ("dinner", rnd.choice(DINNER))]
            if (dense and rnd.random() < 0.7) or (not dense and rnd.random() < 0.35):
                meals.append(("snack", rnd.choice(SNACK)))
            # occasionally a meal is eaten out
            eat_out_meal = rnd.choice(["lunch", "dinner"]) if rnd.random() < 0.2 else None
            for meal_type, items in meals:
                loc = rnd.choice(RESTAURANTS) if meal_type == eat_out_meal else "Home"
                for key, grams in items:
                    it = scale(key, grams)
                    nid += 1
                    rows.append({
                        "id": nid, "user_id": UID, "date": d.isoformat(),
                        "meal_type": meal_type, "description": it["label"], "location": loc,
                        "calories": it["calories"], "protein_g": it["protein_g"],
                        "carbs_g": it["carbs_g"], "fat_g": it["fat_g"], "fiber_g": it["fiber_g"],
                    })
            n_days += 1
        d += timedelta(days=1)

    # Write to the BASE table (shared seed data), not a session overlay, so all
    # users see it. Also clear any stray overlay from an earlier save_collection.
    import sqlite3
    import app.db as adb
    conn = sqlite3.connect(adb._DB_PATH, timeout=60)
    cur = conn.cursor()
    prev = cur.execute("SELECT COUNT(*) FROM health_fitness_tracking_nutrition").fetchone()[0]
    cur.execute("DELETE FROM session_overlay WHERE site=? AND collection='nutrition'", (SITE,))
    cur.execute("DELETE FROM session_collection_replaced WHERE site=? AND collection='nutrition'", (SITE,))
    cur.execute("DELETE FROM health_fitness_tracking_nutrition WHERE user_id=?", (UID,))
    cur.executemany(
        "INSERT INTO health_fitness_tracking_nutrition "
        "(id,user_id,date,meal_type,description,location,calories,protein_g,carbs_g,fat_g,fiber_g) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [(r["id"], r["user_id"], r["date"], r["meal_type"], r["description"], r["location"],
          r["calories"], r["protein_g"], r["carbs_g"], r["fat_g"], r["fiber_g"]) for r in rows],
    )
    conn.commit()
    try:
        cur.execute("INSERT INTO fts_health_fitness_tracking_nutrition"
                    "(fts_health_fitness_tracking_nutrition) VALUES('rebuild')")
        conn.commit()
    except sqlite3.Error as e:
        print("  (nutrition FTS rebuild note:", e, ")")
    conn.close()
    print(f"Replaced BASE nutrition ({prev} old rows) with {len(rows)} itemized food entries "
          f"across {n_days} logged days ({START}..{END}); rebuilt FTS.")


if __name__ == "__main__":
    main()
