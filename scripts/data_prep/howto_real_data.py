#!/usr/bin/env python3
"""Build visual-howto-guides site data from the real VisualHow/WikiHow dataset.

Source: sites/visual-howto-guides/data/wikiHow_data.json
Output: guides.json, categories.json, users.json, comments.json
Also generates: tasks.json, verifiers.py, reference_solutions.py
"""

import json
import pathlib
import random
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta

SEED = 42
random.seed(SEED)

SITE_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "sites" / "visual-howto-guides"
DATA_DIR = SITE_DIR / "data"

# ── Category mapping: wikiHow top-level -> site categories ──────────────────

CATEGORY_MAP = {
    "Home and Garden": "Home Improvement",
    "Food and Entertaining": "Cooking & Baking",
    "Hobbies and Crafts": "Arts & Crafts",
    "Arts and Entertainment": "Arts & Crafts",
    "Computers and Electronics": "Technology",
    "Pets and Animals": "Gardening",
    "Cars & Other Vehicles": "Automotive",
    "Health": "Health & Fitness",
    "Sports and Fitness": "Health & Fitness",
    "Personal Care and Style": "Health & Fitness",
    "Education and Communications": "Technology",
    "Finance and Business": "Technology",
    "Work World": "Technology",
    "Travel": "Photography",
    "Family Life": "Home Improvement",
    "Relationships": "Home Improvement",
    "Holidays and Traditions": "Arts & Crafts",
    "Youth": "Arts & Crafts",
}

CATEGORY_ICONS = {
    "Home Improvement": "hammer",
    "Cooking & Baking": "utensils",
    "Arts & Crafts": "palette",
    "Technology": "laptop",
    "Gardening": "leaf",
    "Automotive": "car",
    "Health & Fitness": "heart",
    "Photography": "camera",
}

AUTHORS_BY_CATEGORY = {
    "Home Improvement": ["Tom Bradley", "Mike Torres", "Dave Martinez", "Sarah Kim"],
    "Cooking & Baking": ["Elena Rossi", "Carlos Mendez", "Rachel Nguyen", "Priya Sharma"],
    "Arts & Crafts": ["Linda Park", "Ana Petrova", "Marcus Webb", "Yuki Tanaka"],
    "Technology": ["James Chen", "Yuki Tanaka", "Dave Martinez", "Priya Sharma"],
    "Gardening": ["Rachel Nguyen", "Helen Okafor", "Marcus Webb", "Sarah Kim"],
    "Automotive": ["Mike Torres", "Tom Bradley", "Carlos Mendez", "Dave Martinez"],
    "Health & Fitness": ["Ana Petrova", "James Chen", "Priya Sharma", "Elena Rossi"],
    "Photography": ["Linda Park", "Marcus Webb", "Sarah Kim", "Yuki Tanaka"],
}


def load_wikihow():
    path = DATA_DIR / "wikiHow_data.json"
    with open(path) as f:
        return json.load(f)


def group_by_article(raw: dict):
    """Group entries by article_id. Each article becomes one guide."""
    articles = defaultdict(list)
    for entry in raw.values():
        articles[entry["article_id"]].append(entry)
    for aid in articles:
        articles[aid].sort(key=lambda e: int(e["problem_idx"]))
    return articles


def select_articles(articles: dict, target=200):
    """Select ~target articles spread across all 18 top-level categories."""
    by_cat = defaultdict(list)
    for aid, entries in articles.items():
        top_cat = entries[0]["category"][0] if entries[0]["category"] else "Other"
        total_steps = sum(len(e["step_list"]) for e in entries)
        title = entries[0]["article_title"].strip()
        if not title:
            continue
        if 3 <= total_steps <= 12:
            by_cat[top_cat].append((aid, entries, total_steps))

    n_cats = len(by_cat)
    base_per_cat = target // n_cats
    remainder = target - base_per_cat * n_cats

    selected = []
    for i, (cat, art_list) in enumerate(sorted(by_cat.items())):
        quota = base_per_cat + (1 if i < remainder else 0)
        short = [(a, e) for a, e, s in art_list if 3 <= s <= 5]
        medium = [(a, e) for a, e, s in art_list if 6 <= s <= 8]
        long_ = [(a, e) for a, e, s in art_list if 9 <= s <= 12]
        random.shuffle(short)
        random.shuffle(medium)
        random.shuffle(long_)
        n_short = max(1, int(quota * 0.45))
        n_med = max(1, int(quota * 0.35))
        n_long = quota - n_short - n_med
        picked = short[:n_short] + medium[:n_med] + long_[:n_long]
        if len(picked) < quota:
            remaining = short[n_short:] + medium[n_med:] + long_[n_long:]
            picked.extend(remaining[:quota - len(picked)])
        selected.extend(picked[:quota])
    return selected


def slugify(title):
    s = title.lower().strip()
    s = re.sub(r'[^a-z0-9\s-]', '', s)
    s = re.sub(r'[\s-]+', '-', s)
    return s[:80]


def build_guides(selected_articles):
    """Convert selected articles to guide objects matching the site schema."""
    guides = []
    guide_id = 1
    for aid, entries in selected_articles:
        first = entries[0]
        title = first["article_title"].strip()
        if title.startswith("How to "):
            title = title[7:]
        all_steps = []
        for entry in entries:
            all_steps.extend(entry["step_list"])
        top_cat = first["category"][0] if first["category"] else "Other"
        category = CATEGORY_MAP.get(top_cat, "Technology")
        subcategory = first["category"][1] if len(first["category"]) > 1 else category
        author = random.choice(AUTHORS_BY_CATEGORY[category])
        n_steps = len(all_steps)
        if n_steps <= 5:
            difficulty = "Beginner"
        elif n_steps <= 8:
            difficulty = "Intermediate"
        else:
            difficulty = "Advanced"
        duration = n_steps * random.randint(5, 10)
        views = random.randint(500, 50000)
        rating = round(random.uniform(3.0, 5.0), 1)
        num_ratings = random.randint(10, 800)
        desc = all_steps[0] if all_steps else title
        if len(desc) > 200:
            desc = desc[:197] + "..."
        tags = [t.lower().replace(" ", "-") for t in first["category"] if t]
        tags.append(slugify(title).split("-")[0])
        tags = list(dict.fromkeys(tags))[:5]
        all_images = []
        for entry in entries:
            all_images.extend(entry.get("image_url", []))
        thumbnail = all_images[0] if all_images else f"/thumbs/{slugify(title)}.jpg"
        video_url = all_images[0] if all_images else f"/videos/{slugify(title)}.mp4"
        video_duration_sec = duration * 60 + random.randint(-120, 300)
        video_duration_sec = max(120, video_duration_sec)
        base_date = datetime(2025, 3, 1)
        created = base_date + timedelta(days=random.randint(0, 180))
        updated = created + timedelta(days=random.randint(1, 60))
        guide = {
            "id": guide_id,
            "title": title,
            "slug": slugify(title),
            "category": category,
            "subcategory": subcategory,
            "author": author,
            "difficulty": difficulty,
            "duration_minutes": duration,
            "views": views,
            "rating": rating,
            "num_ratings": num_ratings,
            "description": desc,
            "steps": all_steps,
            "tags": tags,
            "created": created.strftime("%Y-%m-%d"),
            "updated": updated.strftime("%Y-%m-%d"),
            "video_url": video_url,
            "video_duration_sec": video_duration_sec,
            "thumbnail": thumbnail,
        }
        guides.append(guide)
        guide_id += 1
    return guides


def post_process_guides(guides):
    """Engineer specific data values for predictable, testable tasks.

    This adjusts certain guides/values so that tasks have clear, unique answers.
    """
    # Ensure exactly one guide has the uniquely highest rating with most num_ratings
    # among 5.0-rated guides. First, set only specific guides to 5.0
    for g in guides:
        if g["rating"] == 5.0:
            g["rating"] = 4.9  # reset all 5.0s

    # Pick guide id=16 as the singular highest rated
    g16 = next(g for g in guides if g["id"] == 16)
    g16["rating"] = 5.0
    g16["num_ratings"] = 504

    # Set a few more to 5.0 with lower num_ratings (for "how many 5.0" task)
    for gid in [35, 78, 112, 145, 180, 195]:
        gg = next((g for g in guides if g["id"] == gid), None)
        if gg:
            gg["rating"] = 5.0
            gg["num_ratings"] = random.randint(10, 200)

    # Ensure guide 2 has a rating where adding 5 produces a visible change
    g2 = next(g for g in guides if g["id"] == 2)
    g2["rating"] = 3.8
    g2["num_ratings"] = 45
    # After +5: (3.8*45 + 5) / 46 = (171 + 5) / 46 = 176/46 = 3.826... -> round(,1) = 3.8
    # That's the same. Let's use rating=3.5, num_ratings=19
    # (3.5*19 + 5) / 20 = (66.5 + 5) / 20 = 71.5/20 = 3.575 -> 3.6
    g2["rating"] = 3.5
    g2["num_ratings"] = 19

    # Ensure most-viewed is unique and clear
    # Set the globally most-viewed to be a NON-Technology guide
    # so that t04 (most viewed overall) and t12 (most viewed Tech) differ
    for g in guides:
        if g["views"] > 49000:
            g["views"] = 48000
    # Pick a Home Improvement guide as the globally most-viewed
    hi_guides = [g for g in guides if g["category"] == "Home Improvement"]
    hi_guides[0]["views"] = 49998  # globally highest

    # Ensure Automotive most-viewed is unique
    auto_guides = [g for g in guides if g["category"] == "Automotive"]
    for ag in auto_guides:
        if ag["views"] > 45000:
            ag["views"] = 38000
    auto_guides[0]["views"] = 47500  # first automotive guide gets most views

    # Ensure Technology most-viewed is unique
    tech_guides = [g for g in guides if g["category"] == "Technology"]
    tech_max = max(tech_guides, key=lambda g: g["views"])
    for tg in tech_guides:
        if tg["id"] != tech_max["id"] and tg["views"] > tech_max["views"] - 2000:
            tg["views"] = tech_max["views"] - 2000

    return guides


def build_categories(guides):
    cat_counts = defaultdict(int)
    for g in guides:
        cat_counts[g["category"]] += 1
    ordered = [
        "Home Improvement", "Cooking & Baking", "Arts & Crafts", "Technology",
        "Gardening", "Automotive", "Health & Fitness", "Photography",
    ]
    categories = []
    for i, name in enumerate(ordered, 1):
        categories.append({
            "id": i,
            "name": name,
            "description": f"Guides about {name.lower()}",
            "icon": CATEGORY_ICONS[name],
            "guide_count": cat_counts.get(name, 0),
        })
    return categories


def build_users(guides):
    user_data = [
        (1, "diy_dana", "Dana Williams"),
        (2, "maker_max", "Max Henderson"),
        (3, "craft_queen", "Sophie Turner"),
        (4, "home_hero", "Robert Chang"),
        (5, "green_thumb", "Maria Santos"),
        (6, "tech_tinkerer", "Alex Rivera"),
        (7, "fit_freak", "Jordan Blake"),
        (8, "shutter_bug", "Lisa Nakamura"),
        (9, "garden_guru", "Helen Okafor"),
        (10, "chef_carlo", "Carlo Bianchi"),
        (11, "weekend_warrior", "Derek Olsen"),
        (12, "curious_cat", "Nadia Petrov"),
        (13, "handy_hannah", "Hannah Yee"),
        (14, "learn_it_all", "Ethan Murray"),
        (15, "artsy_anna", "Anna Kowalski"),
    ]
    guide_ids = [g["id"] for g in guides]
    all_authors = sorted(set(g["author"] for g in guides))

    users = []
    for uid, username, name in user_data:
        n_saved = random.randint(3, 8)
        saved = sorted(random.sample(guide_ids, min(n_saved, len(guide_ids))))
        n_follow = random.randint(1, 4)
        following = random.sample(all_authors, min(n_follow, len(all_authors)))
        n_completed = random.randint(2, 6)
        completed = sorted(random.sample(guide_ids, min(n_completed, len(guide_ids))))
        users.append({
            "id": uid,
            "username": username,
            "name": name,
            "email": f"{username}@example.com",
            "saved_guides": saved,
            "following_authors": following,
            "completed_guides": completed,
            "comments_count": random.randint(30, 80),
        })

    # Post-process users for task requirements:
    u1 = next(u for u in users if u["id"] == 1)
    # Ensure guide 10 is NOT in user 1's saved list (for save task)
    if 10 in u1["saved_guides"]:
        u1["saved_guides"].remove(10)

    u3 = next(u for u in users if u["id"] == 3)
    # Ensure 'Rachel Nguyen' is NOT in user 3's following (for follow task)
    if "Rachel Nguyen" in u3["following_authors"]:
        u3["following_authors"].remove("Rachel Nguyen")
    # Ensure 'Mike Torres' IS in user 3's following (for unfollow task)
    if "Mike Torres" not in u3["following_authors"]:
        u3["following_authors"].append("Mike Torres")

    return users


def build_comments(guides, users):
    comment_templates = [
        "Great tutorial on {title}! Very helpful.",
        "I followed this guide step by step. The part about '{step}' was especially useful.",
        "Would this work for a different {category} project?",
        "Clear instructions. Thanks for sharing!",
        "How long does this actually take? The {duration} minutes estimate seems {adj}.",
        "Pro tip: be careful during the '{step}' step.",
        "Much easier than I expected. Clear instructions.",
        "Safety tip: always wear safety glasses for this kind of work.",
        "Would this work in a rental apartment?",
        "How long does the finish need to cure before using?",
        "I've been looking for a guide like this. Bookmarked!",
        "The photos really help with understanding each step.",
        "Can you do a follow-up guide on {subcategory}?",
        "I tried this and it worked perfectly on my first attempt!",
        "Any alternative materials that could work for this?",
    ]
    comments = []
    comment_id = 1
    user_ids = [u["id"] for u in users]
    base_date = datetime(2025, 8, 1)

    for guide in guides:
        # Ensure at least 1 comment for early guides (needed for tasks)
        if guide["id"] <= 5:
            n_comments = random.randint(2, 5)
        else:
            n_comments = random.randint(0, 5)
        for _ in range(n_comments):
            template = random.choice(comment_templates)
            step = random.choice(guide["steps"]) if guide["steps"] else guide["title"]
            if len(step) > 50:
                step = step[:47] + "..."
            text = template.format(
                title=guide["title"],
                step=step,
                category=guide["category"],
                subcategory=guide["subcategory"],
                duration=guide["duration_minutes"],
                adj=random.choice(["about right", "a bit optimistic", "generous"]),
            )
            created = base_date + timedelta(days=random.randint(0, 300))
            comments.append({
                "id": comment_id,
                "guide_id": guide["id"],
                "user_id": random.choice(user_ids),
                "text": text,
                "created": created.strftime("%Y-%m-%d"),
                "likes": random.randint(0, 20),
                "parent_id": None,
            })
            comment_id += 1

    return comments


def compute_task_values(guides, categories, users, comments):
    """Compute the exact expected answers for all 20 tasks."""
    vals = {}

    # T01: Highest-rated guide (tiebreaker = most ratings)
    sorted_r = sorted(guides, key=lambda g: (-g["rating"], -g["num_ratings"]))
    top = sorted_r[0]
    vals["t01_title"] = top["title"]

    # T02: Beginner count
    beg = [g for g in guides if g["difficulty"] == "Beginner"]
    vals["t02_count"] = len(beg)

    # T03: Find a guide with a unique searchable word for author lookup
    # Search uses title, description, author, tags - check all
    for g in guides:
        title_lower = g["title"].lower()
        for word in title_lower.split():
            if len(word) >= 6:  # longer words = more unique
                matches = [x for x in guides
                           if word in x["title"].lower()
                           or word in x.get("description", "").lower()
                           or word in x.get("author", "").lower()
                           or any(word in t.lower() for t in x.get("tags", []))]
                if len(matches) == 1:
                    vals["t03_query"] = word
                    vals["t03_title"] = g["title"]
                    vals["t03_author"] = g["author"]
                    vals["t03_id"] = g["id"]
                    break
        if "t03_query" in vals:
            break

    # T04: Most viewed guide
    mv = max(guides, key=lambda g: g["views"])
    vals["t04_title"] = mv["title"]

    # T05: Photography category count
    photo = [g for g in guides if g["category"] == "Photography"]
    vals["t05_count"] = len(photo)

    # T06: Search for a unique word -> single result title
    # Search endpoint checks title, description, author, tags
    used_ids = {vals.get("t03_id")}
    for g in guides:
        if g["id"] in used_ids:
            continue
        title_lower = g["title"].lower()
        for word in title_lower.split():
            if len(word) >= 6 and word != vals.get("t03_query"):
                matches = [x for x in guides
                           if word in x["title"].lower()
                           or word in x.get("description", "").lower()
                           or word in x.get("author", "").lower()
                           or any(word in t.lower() for t in x.get("tags", []))]
                if len(matches) == 1:
                    vals["t06_query"] = word
                    vals["t06_title"] = g["title"]
                    vals["t06_id"] = g["id"]
                    break
        if "t06_query" in vals:
            break

    # T07: Gardening category count via category endpoint (cat_id=5)
    gard = [g for g in guides if g["category"] == "Gardening"]
    vals["t07_count"] = len(gard)

    # T08: Semantic search - find a guide whose title contains multiple distinctive words
    # We pick a guide with at least 3 words in title and construct a multi-word query
    for g in guides:
        words = [w.lower() for w in g["title"].split() if len(w) >= 4]
        if len(words) >= 3:
            # Check that searching these words returns this guide first
            query_words = words[:3]
            scored = []
            for gg in guides:
                text = " ".join([
                    gg["title"].lower(),
                    gg.get("description", "").lower(),
                    gg.get("category", "").lower(),
                    gg.get("subcategory", "").lower(),
                    " ".join(gg.get("tags", [])).lower(),
                    " ".join(gg.get("steps", [])).lower(),
                ])
                score = sum(1 for kw in query_words if kw in text)
                if score > 0:
                    scored.append((score, gg))
            scored.sort(key=lambda x: -x[0])
            if scored and scored[0][1]["id"] == g["id"]:
                vals["t08_query"] = "+".join(query_words)
                vals["t08_query_display"] = " ".join(query_words)
                vals["t08_title"] = g["title"]
                vals["t08_id"] = g["id"]
                break

    # T09: Most-viewed Automotive guide
    auto = [g for g in guides if g["category"] == "Automotive"]
    auto_mv = max(auto, key=lambda g: g["views"])
    vals["t09_title"] = auto_mv["title"]

    # T10: Guides with 5.0 rating
    perfect = [g for g in guides if g["rating"] == 5.0]
    vals["t10_count"] = len(perfect)

    # T11: Average duration of Beginner guides
    avg_dur = round(sum(g["duration_minutes"] for g in beg) / len(beg), 1)
    vals["t11_avg"] = avg_dur

    # T12: Most-viewed Technology guide
    tech = [g for g in guides if g["category"] == "Technology"]
    tech_mv = max(tech, key=lambda g: g["views"])
    vals["t12_title"] = tech_mv["title"]

    # T13: Pick a guide with specific step count
    # Find a guide with an interesting step count (not 3 or 12 - too common)
    for g in guides:
        ns = len(g["steps"])
        if 5 <= ns <= 8:
            vals["t13_id"] = g["id"]
            vals["t13_title"] = g["title"]
            vals["t13_steps"] = ns
            break

    # T14: Video playback (guide with video_duration_sec > 600)
    for g in guides:
        if g["video_duration_sec"] > 800:
            vals["t14_id"] = g["id"]
            vals["t14_title"] = g["title"]
            vals["t14_vid_dur"] = g["video_duration_sec"]
            # Play from 120 to 600 -> duration = 480
            vals["t14_start"] = 120
            vals["t14_end"] = 600
            vals["t14_playback_dur"] = 480
            break

    # T15: Post comment on a specific guide
    # Pick a Technology or Home Improvement guide with a clean title
    skip_words = {"toddler", "touch", "marijuana", "sex", "drug", "kill", "die", "dead"}
    for g in guides:
        if g["id"] >= 20 and len(g["title"]) < 50 and g["category"] in ("Technology", "Home Improvement", "Cooking & Baking"):
            if not any(w in g["title"].lower() for w in skip_words):
                vals["t15_guide_id"] = g["id"]
                vals["t15_title"] = g["title"]
                break

    # T16: Like a comment - find first comment on guide 2
    g2_comments = [c for c in comments if c["guide_id"] == 2]
    if g2_comments:
        c = g2_comments[0]
        vals["t16_comment_id"] = c["id"]
        vals["t16_likes_after"] = c["likes"] + 1
        vals["t16_guide_id"] = 2

    # T17: Rate guide 2
    g2 = next(g for g in guides if g["id"] == 2)
    new_total = g2["rating"] * g2["num_ratings"] + 5
    new_nr = g2["num_ratings"] + 1
    vals["t17_new_rating"] = round(new_total / new_nr, 1)
    vals["t17_new_nr"] = new_nr
    vals["t17_title"] = g2["title"]

    # T18: Save guide 10 for user 1
    u1 = next(u for u in users if u["id"] == 1)
    vals["t18_already_saved"] = 10 in u1["saved_guides"]

    # T19: User 3 follow Rachel Nguyen
    u3 = next(u for u in users if u["id"] == 3)
    vals["t19_already_following"] = "Rachel Nguyen" in u3["following_authors"]

    # T20: User 3 unfollow Mike Torres
    vals["t20_currently_following"] = "Mike Torres" in u3["following_authors"]

    return vals


def generate_tasks(vals):
    """Generate tasks.json based on computed values."""
    tasks = [
        {
            "task_id": "howto-001",
            "difficulty": "easy",
            "instruction": "What is the highest-rated guide on HowToHub? If there are ties, name the one with the most ratings.",
            "expected_answer": vals["t01_title"],
            "verifier": "verify_howto_001",
            "reference_solution": "solve_howto_001",
            "macros": ["sort_by_ranking", "extract_from_table"]
        },
        {
            "task_id": "howto-002",
            "difficulty": "easy",
            "instruction": "How many Beginner-difficulty guides are available on HowToHub?",
            "expected_answer": str(vals["t02_count"]),
            "verifier": "verify_howto_002",
            "reference_solution": "solve_howto_002",
            "macros": ["filter_by_dropdown", "extract_from_table"]
        },
        {
            "task_id": "howto-003",
            "difficulty": "easy",
            "instruction": f"Who is the author of the guide '{vals['t03_title']}'?",
            "expected_answer": vals["t03_author"],
            "verifier": "verify_howto_003",
            "reference_solution": "solve_howto_003",
            "macros": ["search_by_query", "extract_by_route"]
        },
        {
            "task_id": "howto-004",
            "difficulty": "easy",
            "instruction": "Which guide has the most views on the platform?",
            "expected_answer": vals["t04_title"],
            "verifier": "verify_howto_004",
            "reference_solution": "solve_howto_004",
            "macros": ["sort_by_ranking", "extract_from_table"]
        },
        {
            "task_id": "howto-005",
            "difficulty": "easy",
            "instruction": "How many guides are in the Photography category?",
            "expected_answer": str(vals["t05_count"]),
            "verifier": "verify_howto_005",
            "reference_solution": "solve_howto_005",
            "macros": ["navigate_by_dropdown", "extract_from_table"]
        },
        {
            "task_id": "howto-006",
            "difficulty": "easy",
            "instruction": f"Search for guides about '{vals['t06_query']}'. What is the title of the result?",
            "expected_answer": vals["t06_title"],
            "verifier": "verify_howto_006",
            "reference_solution": "solve_howto_006",
            "macros": ["search_by_query", "extract_from_table"]
        },
        {
            "task_id": "howto-007",
            "difficulty": "medium",
            "instruction": "Navigate to the Gardening category (category 5) and find how many guides it contains.",
            "expected_answer": str(vals["t07_count"]),
            "verifier": "verify_howto_007",
            "reference_solution": "solve_howto_007",
            "macros": ["navigate_by_dropdown", "extract_from_table"]
        },
        {
            "task_id": "howto-008",
            "difficulty": "medium",
            "instruction": f"Use the semantic search to find guides about '{vals['t08_query_display']}'. What is the title of the top result?",
            "expected_answer": vals["t08_title"],
            "verifier": "verify_howto_008",
            "reference_solution": "solve_howto_008",
            "macros": ["search_by_semantic", "extract_from_table"]
        },
        {
            "task_id": "howto-009",
            "difficulty": "medium",
            "instruction": "Filter guides to show only those in the Automotive category and rank them by views. Which Automotive guide has the most views?",
            "expected_answer": vals["t09_title"],
            "verifier": "verify_howto_009",
            "reference_solution": "solve_howto_009",
            "macros": ["filter_by_dropdown", "sort_by_ranking"]
        },
        {
            "task_id": "howto-010",
            "difficulty": "medium",
            "instruction": "How many guides have a perfect rating of 5.0?",
            "expected_answer": str(vals["t10_count"]),
            "verifier": "verify_howto_010",
            "reference_solution": "solve_howto_010",
            "macros": ["filter_by_slider", "extract_from_table"]
        },
        {
            "task_id": "howto-011",
            "difficulty": "medium",
            "instruction": "What is the average duration (in minutes) of all Beginner guides? Round to one decimal place.",
            "expected_answer": str(vals["t11_avg"]),
            "verifier": "verify_howto_011",
            "reference_solution": "solve_howto_011",
            "macros": ["filter_by_dropdown", "extract_from_table"]
        },
        {
            "task_id": "howto-012",
            "difficulty": "medium",
            "instruction": "View the rankings of Technology guides sorted by views. What is the title of the most-viewed Technology guide?",
            "expected_answer": vals["t12_title"],
            "verifier": "verify_howto_012",
            "reference_solution": "solve_howto_012",
            "macros": ["sort_by_ranking", "filter_by_dropdown"]
        },
        {
            "task_id": "howto-013",
            "difficulty": "medium",
            "instruction": f"Navigate to the guide detail page for guide {vals['t13_id']} ('{vals['t13_title']}'). How many steps does it have?",
            "expected_answer": str(vals["t13_steps"]),
            "verifier": "verify_howto_013",
            "reference_solution": "solve_howto_013",
            "macros": ["navigate_by_route", "extract_by_route"]
        },
        {
            "task_id": "howto-014",
            "difficulty": "medium",
            "instruction": f"Play the video for guide {vals['t14_id']} ('{vals['t14_title']}') from timestamp {vals['t14_start']} to {vals['t14_end']} seconds. What is the playback duration reported?",
            "expected_answer": str(vals["t14_playback_dur"]),
            "verifier": "verify_howto_014",
            "reference_solution": "solve_howto_014",
            "macros": ["play_by_date_range", "play_by_playback"]
        },
        {
            "task_id": "howto-015",
            "difficulty": "hard",
            "instruction": f"Post a comment on guide {vals['t15_guide_id']} ('{vals['t15_title']}') as user 3 with the text 'This tutorial helped me build my first project!'. Verify the comment was created.",
            "expected_answer": "comment_created",
            "verifier": "verify_howto_015",
            "reference_solution": "solve_howto_015",
            "macros": ["post_from_free_text"]
        },
        {
            "task_id": "howto-016",
            "difficulty": "hard",
            "instruction": f"Like comment {vals['t16_comment_id']} on guide 2 ('{vals['t17_title']}'). What is the new like count?",
            "expected_answer": str(vals["t16_likes_after"]),
            "verifier": "verify_howto_016",
            "reference_solution": "solve_howto_016",
            "macros": ["react_by_toggle"]
        },
        {
            "task_id": "howto-017",
            "difficulty": "hard",
            "instruction": f"Rate guide 2 ('{vals['t17_title']}') with a rating of 5. What is the new average rating?",
            "expected_answer": str(vals["t17_new_rating"]),
            "verifier": "verify_howto_017",
            "reference_solution": "solve_howto_017",
            "macros": ["rate_by_slider"]
        },
        {
            "task_id": "howto-018",
            "difficulty": "hard",
            "instruction": "Save guide 10 to user 1's (diy_dana) saved guides list. Then check user 1's profile to confirm. Was the guide saved or unsaved?",
            "expected_answer": "saved",
            "verifier": "verify_howto_018",
            "reference_solution": "solve_howto_018",
            "macros": ["save_by_toggle"]
        },
        {
            "task_id": "howto-019",
            "difficulty": "hard",
            "instruction": "Have user 3 (craft_queen) follow the author 'Rachel Nguyen'. Then verify 'Rachel Nguyen' appears in user 3's following list.",
            "expected_answer": "following",
            "verifier": "verify_howto_019",
            "reference_solution": "solve_howto_019",
            "macros": ["follow_by_dropdown"]
        },
        {
            "task_id": "howto-020",
            "difficulty": "hard",
            "instruction": "User 3 (craft_queen) currently follows 'Mike Torres'. Unfollow 'Mike Torres' for user 3 and confirm the unfollow was successful.",
            "expected_answer": "unfollowed",
            "verifier": "verify_howto_020",
            "reference_solution": "solve_howto_020",
            "macros": ["follow_by_dropdown"]
        },
    ]
    return tasks


def generate_verifiers(vals):
    """Generate verifiers.py content using safe quoting."""
    # Use json.dumps for safe string embedding
    lines = []
    lines.append('"""Verifiers for visual-howto-guides tasks.\n')
    lines.append('Each verifier checks backend state via HTTP requests to the running server.')
    lines.append('Returns {"pass": bool, "detail": str}.')
    lines.append('"""\n')
    lines.append('import json')
    lines.append('import requests\n\n')
    lines.append('def _get(server_url, path):')
    lines.append('    r = requests.get(f"{server_url}/sites/visual-howto-guides{path}")')
    lines.append('    r.raise_for_status()')
    lines.append('    return r.json()\n\n')

    def _safe(s):
        """Return a safely-quoted Python string literal."""
        return json.dumps(s)  # json.dumps handles all escaping

    # T01
    lines.append('def verify_howto_001(server_url):')
    lines.append('    """Highest-rated guide, tiebreaker = most ratings."""')
    lines.append('    guides = _get(server_url, "/api/guides?sort=rating")')
    lines.append('    top_rating = guides[0]["rating"]')
    lines.append('    tied = [g for g in guides if g["rating"] == top_rating]')
    lines.append('    best = max(tied, key=lambda g: g["num_ratings"])')
    lines.append('    title = best["title"]')
    lines.append(f'    expected = {_safe(vals["t01_title"])}')
    lines.append('    return {"pass": title == expected, "detail": f"Expected {expected!r}, got {title!r}"}\n\n')

    # T02
    lines.append('def verify_howto_002(server_url):')
    lines.append('    """Count Beginner guides."""')
    lines.append('    guides = _get(server_url, "/api/guides?difficulty=Beginner")')
    lines.append('    count = len(guides)')
    lines.append(f'    return {{"pass": count == {vals["t02_count"]}, "detail": f"Expected {vals["t02_count"]}, got {{count}}"}}\n\n')

    # T03
    lines.append('def verify_howto_003(server_url):')
    lines.append(f'    """Author lookup via search."""')
    lines.append(f'    results = _get(server_url, "/api/guides/search?q={vals["t03_query"]}")')
    lines.append('    if not results:')
    lines.append('        return {"pass": False, "detail": "Guide not found via search"}')
    lines.append('    author = results[0]["author"]')
    lines.append(f'    expected = {_safe(vals["t03_author"])}')
    lines.append('    return {"pass": author == expected, "detail": f"Expected {expected!r}, got {author!r}"}\n\n')

    # T04
    lines.append('def verify_howto_004(server_url):')
    lines.append('    """Most viewed guide."""')
    lines.append('    guides = _get(server_url, "/api/guides?sort=views&limit=1")')
    lines.append('    title = guides[0]["title"]')
    lines.append(f'    expected = {_safe(vals["t04_title"])}')
    lines.append('    return {"pass": title == expected, "detail": f"Expected {expected!r}, got {title!r}"}\n\n')

    # T05
    lines.append('def verify_howto_005(server_url):')
    lines.append('    """Photography category count."""')
    lines.append('    guides = _get(server_url, "/api/guides?category=Photography")')
    lines.append('    count = len(guides)')
    lines.append(f'    return {{"pass": count == {vals["t05_count"]}, "detail": f"Expected {vals["t05_count"]}, got {{count}}"}}\n\n')

    # T06
    lines.append('def verify_howto_006(server_url):')
    lines.append(f'    """Search result title."""')
    lines.append(f'    results = _get(server_url, "/api/guides/search?q={vals["t06_query"]}")')
    lines.append('    if not results:')
    lines.append(f'        return {{"pass": False, "detail": "No search results for \'{vals["t06_query"]}\'"}}')
    lines.append('    title = results[0]["title"]')
    lines.append(f'    expected = {_safe(vals["t06_title"])}')
    lines.append('    return {"pass": title == expected, "detail": f"Expected {expected!r}, got {title!r}"}\n\n')

    # T07
    lines.append('def verify_howto_007(server_url):')
    lines.append('    """Gardening category guide count via category route."""')
    lines.append('    guides = _get(server_url, "/api/categories/5/guides")')
    lines.append('    count = len(guides)')
    lines.append(f'    return {{"pass": count == {vals["t07_count"]}, "detail": f"Expected {vals["t07_count"]}, got {{count}}"}}\n\n')

    # T08
    lines.append('def verify_howto_008(server_url):')
    lines.append('    """Semantic search top result."""')
    lines.append(f'    results = _get(server_url, "/api/guides/semantic?q={vals["t08_query"]}")')
    lines.append('    if not results:')
    lines.append('        return {"pass": False, "detail": "No semantic search results"}')
    lines.append('    title = results[0]["title"]')
    lines.append(f'    expected = {_safe(vals["t08_title"])}')
    lines.append('    return {"pass": title == expected, "detail": f"Expected {expected!r}, got {title!r}"}\n\n')

    # T09
    lines.append('def verify_howto_009(server_url):')
    lines.append('    """Most-viewed Automotive guide."""')
    lines.append('    guides = _get(server_url, "/api/guides/rankings?category=Automotive&sort=views")')
    lines.append('    if not guides:')
    lines.append('        return {"pass": False, "detail": "No Automotive guides found"}')
    lines.append('    title = guides[0]["title"]')
    lines.append(f'    expected = {_safe(vals["t09_title"])}')
    lines.append('    return {"pass": title == expected, "detail": f"Expected {expected!r}, got {title!r}"}\n\n')

    # T10
    lines.append('def verify_howto_010(server_url):')
    lines.append('    """Guides with perfect 5.0 rating."""')
    lines.append('    guides = _get(server_url, "/api/guides?min_rating=5.0")')
    lines.append('    count = len(guides)')
    lines.append(f'    return {{"pass": count == {vals["t10_count"]}, "detail": f"Expected {vals["t10_count"]}, got {{count}}"}}\n\n')

    # T11
    lines.append('def verify_howto_011(server_url):')
    lines.append('    """Average duration of Beginner guides."""')
    lines.append('    guides = _get(server_url, "/api/guides?difficulty=Beginner")')
    lines.append('    avg = round(sum(g["duration_minutes"] for g in guides) / len(guides), 1)')
    lines.append(f'    return {{"pass": avg == {vals["t11_avg"]}, "detail": f"Expected {vals["t11_avg"]}, got {{avg}}"}}\n\n')

    # T12
    lines.append('def verify_howto_012(server_url):')
    lines.append('    """Most-viewed Technology guide."""')
    lines.append('    guides = _get(server_url, "/api/guides/rankings?category=Technology&sort=views")')
    lines.append('    if not guides:')
    lines.append('        return {"pass": False, "detail": "No Technology guides found"}')
    lines.append('    title = guides[0]["title"]')
    lines.append(f'    expected = {_safe(vals["t12_title"])}')
    lines.append('    return {"pass": title == expected, "detail": f"Expected {expected!r}, got {title!r}"}\n\n')

    # T13
    lines.append('def verify_howto_013(server_url):')
    lines.append(f'    """Steps count of guide {vals["t13_id"]}."""')
    lines.append(f'    guide = _get(server_url, "/api/guides/{vals["t13_id"]}")')
    lines.append('    count = len(guide["steps"])')
    lines.append(f'    return {{"pass": count == {vals["t13_steps"]}, "detail": f"Expected {vals["t13_steps"]} steps, got {{count}}"}}\n\n')

    # T14
    lines.append('def verify_howto_014(server_url):')
    lines.append(f'    """Playback duration."""')
    lines.append(f'    result = _get(server_url, "/api/guides/{vals["t14_id"]}/play?start={vals["t14_start"]}&end={vals["t14_end"]}")')
    lines.append('    duration = result["playback"]["duration"]')
    lines.append(f'    return {{"pass": duration == {vals["t14_playback_dur"]}, "detail": f"Expected {vals["t14_playback_dur"]}, got {{duration}}"}}\n\n')

    # T15
    lines.append('def verify_howto_015(server_url):')
    lines.append(f'    """Comment posted on guide {vals["t15_guide_id"]}."""')
    lines.append(f'    comments = _get(server_url, "/api/guides/{vals["t15_guide_id"]}/comments")')
    lines.append('    matching = [c for c in comments if c["user_id"] == 3')
    lines.append('                and "first project" in c.get("text", "").lower()]')
    lines.append(f'    return {{"pass": len(matching) > 0,')
    lines.append(f'            "detail": f"Found {{len(matching)}} matching comments for guide {vals["t15_guide_id"]}"}}\n\n')

    # T16
    lines.append('def verify_howto_016(server_url):')
    lines.append(f'    """Like count on comment {vals["t16_comment_id"]} of guide 2."""')
    lines.append('    comments = _get(server_url, "/api/guides/2/comments")')
    lines.append(f'    comment = next((c for c in comments if c["id"] == {vals["t16_comment_id"]}), None)')
    lines.append('    if comment is None:')
    lines.append(f'        return {{"pass": False, "detail": "Comment {vals["t16_comment_id"]} not found on guide 2"}}')
    lines.append('    likes = comment["likes"]')
    lines.append(f'    return {{"pass": likes == {vals["t16_likes_after"]}, "detail": f"Expected {vals["t16_likes_after"]} likes, got {{likes}}"}}\n\n')

    # T17
    lines.append('def verify_howto_017(server_url):')
    lines.append('    """Rating of guide 2 after submitting a 5."""')
    lines.append('    guide = _get(server_url, "/api/guides/2")')
    lines.append('    rating = guide["rating"]')
    lines.append('    num = guide["num_ratings"]')
    lines.append(f'    return {{"pass": rating == {vals["t17_new_rating"]} and num == {vals["t17_new_nr"]},')
    lines.append(f'            "detail": f"Expected rating={vals["t17_new_rating"]} num_ratings={vals["t17_new_nr"]}, got rating={{rating}} num_ratings={{num}}"}}\n\n')

    # T18
    lines.append('def verify_howto_018(server_url):')
    lines.append('    """User 1 saved guide 10."""')
    lines.append('    user = _get(server_url, "/api/users/1")')
    lines.append('    saved = 10 in user["saved_guides"]')
    lines.append('    return {"pass": saved,')
    lines.append('            "detail": f"Guide 10 {\'is\' if saved else \'is NOT\'} in saved_guides: {user[\'saved_guides\']}"}\n\n')

    # T19
    lines.append('def verify_howto_019(server_url):')
    lines.append('    """User 3 follows Rachel Nguyen."""')
    lines.append('    user = _get(server_url, "/api/users/3")')
    lines.append('    following = "Rachel Nguyen" in user["following_authors"]')
    lines.append('    return {"pass": following,')
    lines.append('            "detail": f"Rachel Nguyen {\'is\' if following else \'is NOT\'} in following_authors: {user[\'following_authors\']}"}\n\n')

    # T20
    lines.append('def verify_howto_020(server_url):')
    lines.append('    """User 3 unfollowed Mike Torres."""')
    lines.append('    user = _get(server_url, "/api/users/3")')
    lines.append('    unfollowed = "Mike Torres" not in user["following_authors"]')
    lines.append('    return {"pass": unfollowed,')
    lines.append('            "detail": f"Mike Torres {\'is NOT\' if unfollowed else \'is still\'} in following_authors: {user[\'following_authors\']}"}\n')

    return "\n".join(lines)


def generate_solutions(vals):
    """Generate reference_solutions.py content."""
    lines = []
    lines.append('"""Reference solutions for visual-howto-guides tasks.')
    lines.append('')
    lines.append('Each function takes a Flask test client, executes the solution path')
    lines.append('through the site\'s routes, and returns the expected answer.')
    lines.append('"""')
    lines.append('')
    lines.append('import json')
    lines.append('')
    lines.append('')
    lines.append('BASE = "/sites/visual-howto-guides"')
    lines.append('')
    lines.append('')
    lines.append('def _get_json(client, path):')
    lines.append('    r = client.get(f"{BASE}{path}")')
    lines.append('    return json.loads(r.data)')
    lines.append('')
    lines.append('')
    lines.append('def _post_json(client, path, data):')
    lines.append('    r = client.post(f"{BASE}{path}", data=json.dumps(data), content_type="application/json")')
    lines.append('    return json.loads(r.data), r.status_code')
    lines.append('')
    lines.append('')
    lines.append('def _delete(client, path):')
    lines.append('    r = client.delete(f"{BASE}{path}")')
    lines.append('    return json.loads(r.data), r.status_code')
    lines.append('')
    lines.append('')
    lines.append('def solve_howto_001(client):')
    lines.append('    """Highest-rated guide, tiebreaker = most ratings."""')
    lines.append('    guides = _get_json(client, "/api/guides?sort=rating")')
    lines.append('    top_rating = guides[0]["rating"]')
    lines.append('    tied = [g for g in guides if g["rating"] == top_rating]')
    lines.append('    best = max(tied, key=lambda g: g["num_ratings"])')
    lines.append('    return best["title"]')
    lines.append('')
    lines.append('')
    lines.append('def solve_howto_002(client):')
    lines.append('    """Count Beginner guides."""')
    lines.append('    guides = _get_json(client, "/api/guides?difficulty=Beginner")')
    lines.append('    return str(len(guides))')
    lines.append('')
    lines.append('')
    lines.append('def solve_howto_003(client):')
    lines.append('    """Author lookup via search."""')
    lines.append(f'    results = _get_json(client, "/api/guides/search?q={vals["t03_query"]}")')
    lines.append('    return results[0]["author"]')
    lines.append('')
    lines.append('')
    lines.append('def solve_howto_004(client):')
    lines.append('    """Most viewed guide."""')
    lines.append('    guides = _get_json(client, "/api/guides?sort=views&limit=1")')
    lines.append('    return guides[0]["title"]')
    lines.append('')
    lines.append('')
    lines.append('def solve_howto_005(client):')
    lines.append('    """Photography category count."""')
    lines.append('    guides = _get_json(client, "/api/guides?category=Photography")')
    lines.append('    return str(len(guides))')
    lines.append('')
    lines.append('')
    lines.append('def solve_howto_006(client):')
    lines.append('    """Search result title."""')
    lines.append(f'    results = _get_json(client, "/api/guides/search?q={vals["t06_query"]}")')
    lines.append('    return results[0]["title"]')
    lines.append('')
    lines.append('')
    lines.append('def solve_howto_007(client):')
    lines.append('    """Gardening category guide count via category route."""')
    lines.append('    guides = _get_json(client, "/api/categories/5/guides")')
    lines.append('    return str(len(guides))')
    lines.append('')
    lines.append('')
    lines.append('def solve_howto_008(client):')
    lines.append('    """Semantic search top result."""')
    lines.append(f'    results = _get_json(client, "/api/guides/semantic?q={vals["t08_query"]}")')
    lines.append('    return results[0]["title"]')
    lines.append('')
    lines.append('')
    lines.append('def solve_howto_009(client):')
    lines.append('    """Most-viewed Automotive guide."""')
    lines.append('    guides = _get_json(client, "/api/guides/rankings?category=Automotive&sort=views")')
    lines.append('    return guides[0]["title"]')
    lines.append('')
    lines.append('')
    lines.append('def solve_howto_010(client):')
    lines.append('    """Guides with perfect 5.0 rating."""')
    lines.append('    guides = _get_json(client, "/api/guides?min_rating=5.0")')
    lines.append('    return str(len(guides))')
    lines.append('')
    lines.append('')
    lines.append('def solve_howto_011(client):')
    lines.append('    """Average duration of Beginner guides."""')
    lines.append('    guides = _get_json(client, "/api/guides?difficulty=Beginner")')
    lines.append('    avg = round(sum(g["duration_minutes"] for g in guides) / len(guides), 1)')
    lines.append('    return str(avg)')
    lines.append('')
    lines.append('')
    lines.append('def solve_howto_012(client):')
    lines.append('    """Most-viewed Technology guide."""')
    lines.append('    guides = _get_json(client, "/api/guides/rankings?category=Technology&sort=views")')
    lines.append('    return guides[0]["title"]')
    lines.append('')
    lines.append('')
    lines.append('def solve_howto_013(client):')
    lines.append(f'    """Steps count of guide {vals["t13_id"]}."""')
    lines.append(f'    guide = _get_json(client, "/api/guides/{vals["t13_id"]}")')
    lines.append('    return str(len(guide["steps"]))')
    lines.append('')
    lines.append('')
    lines.append('def solve_howto_014(client):')
    lines.append(f'    """Playback duration."""')
    lines.append(f'    result = _get_json(client, "/api/guides/{vals["t14_id"]}/play?start={vals["t14_start"]}&end={vals["t14_end"]}")')
    lines.append('    return str(result["playback"]["duration"])')
    lines.append('')
    lines.append('')
    lines.append('def solve_howto_015(client):')
    lines.append(f'    """Post a comment on guide {vals["t15_guide_id"]}."""')
    lines.append(f'    _post_json(client, "/api/guides/{vals["t15_guide_id"]}/comments", {{')
    lines.append('        "user_id": 3,')
    lines.append('        "text": "This tutorial helped me build my first project!",')
    lines.append('    })')
    lines.append(f'    comments = _get_json(client, "/api/guides/{vals["t15_guide_id"]}/comments")')
    lines.append('    matching = [c for c in comments if "first project" in c.get("text", "").lower()]')
    lines.append('    return "comment_created" if matching else "comment_not_found"')
    lines.append('')
    lines.append('')
    lines.append('def solve_howto_016(client):')
    lines.append(f'    """Like comment {vals["t16_comment_id"]} on guide 2."""')
    lines.append(f'    result, _ = _post_json(client, "/api/guides/2/comments/{vals["t16_comment_id"]}/like", {{}})')
    lines.append('    return str(result["likes"])')
    lines.append('')
    lines.append('')
    lines.append('def solve_howto_017(client):')
    lines.append('    """Rate guide 2 with 5."""')
    lines.append('    result, _ = _post_json(client, "/api/guides/2/rate", {"rating": 5})')
    lines.append('    return str(result["new_rating"])')
    lines.append('')
    lines.append('')
    lines.append('def solve_howto_018(client):')
    lines.append('    """Save guide 10 as user 1."""')
    lines.append('    result, _ = _post_json(client, "/api/users/1/save", {"guide_id": 10})')
    lines.append('    return result["action"]')
    lines.append('')
    lines.append('')
    lines.append('def solve_howto_019(client):')
    lines.append('    """Follow Rachel Nguyen as user 3."""')
    lines.append('    _post_json(client, "/api/users/3/follow", {"author": "Rachel Nguyen"})')
    lines.append('    user = _get_json(client, "/api/users/3")')
    lines.append('    return "following" if "Rachel Nguyen" in user["following_authors"] else "not_following"')
    lines.append('')
    lines.append('')
    lines.append('def solve_howto_020(client):')
    lines.append('    """Unfollow Mike Torres as user 3."""')
    lines.append('    _delete(client, "/api/users/3/follow/Mike Torres")')
    lines.append('    user = _get_json(client, "/api/users/3")')
    lines.append('    return "unfollowed" if "Mike Torres" not in user["following_authors"] else "not_unfollowed"')
    lines.append('')

    return "\n".join(lines)


def main():
    print("Loading wikiHow_data.json...")
    raw = load_wikihow()
    print(f"  {len(raw)} entries loaded")

    print("Grouping by article_id...")
    articles = group_by_article(raw)
    print(f"  {len(articles)} unique articles")

    print("Selecting ~200 articles across 18 categories...")
    selected = select_articles(articles, target=200)
    print(f"  {len(selected)} articles selected")

    print("Building guides...")
    guides = build_guides(selected)
    guides.sort(key=lambda g: g["id"])
    print(f"  {len(guides)} guides built")

    print("Post-processing guides for task consistency...")
    guides = post_process_guides(guides)

    print("Building categories...")
    categories = build_categories(guides)
    for c in categories:
        print(f"  {c['name']}: {c['guide_count']} guides")

    print("Building users...")
    users = build_users(guides)
    print(f"  {len(users)} users built")

    print("Building comments...")
    comments = build_comments(guides, users)
    print(f"  {len(comments)} comments built")

    # Save data files
    for name, data in [
        ("guides.json", guides),
        ("categories.json", categories),
        ("users.json", users),
        ("comments.json", comments),
    ]:
        path = DATA_DIR / name
        path.write_text(json.dumps(data, indent=4))
        print(f"  Wrote {path}")

    # Compute task values and generate task/verifier/solution files
    print("\nComputing task values...")
    vals = compute_task_values(guides, categories, users, comments)
    for k, v in sorted(vals.items()):
        print(f"  {k}: {v}")

    print("\nGenerating tasks.json...")
    tasks = generate_tasks(vals)
    tasks_path = SITE_DIR / "tasks.json"
    tasks_path.write_text(json.dumps(tasks, indent=4))
    print(f"  Wrote {tasks_path}")

    print("Generating verifiers.py...")
    verifiers_content = generate_verifiers(vals)
    verifiers_path = SITE_DIR / "verifiers.py"
    verifiers_path.write_text(verifiers_content)
    print(f"  Wrote {verifiers_path}")

    print("Generating reference_solutions.py...")
    solutions_content = generate_solutions(vals)
    solutions_path = SITE_DIR / "reference_solutions.py"
    solutions_path.write_text(solutions_content)
    print(f"  Wrote {solutions_path}")

    # Summary
    print("\n=== Final Summary ===")
    diff_counts = Counter(g["difficulty"] for g in guides)
    print(f"Guides: {len(guides)} total, {dict(diff_counts)}")
    print(f"Categories: {len(categories)}")
    print(f"Users: {len(users)}")
    print(f"Comments: {len(comments)}")
    print(f"Tasks: {len(tasks)}")


if __name__ == "__main__":
    main()
