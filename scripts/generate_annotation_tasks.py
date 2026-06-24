#!/usr/bin/env python3
"""Pre-generate 60 annotation task drafts per site (20 easy / 20 medium / 20 hard).

Each task is grounded in the site's actual routes and data.
Output: annotation/generated/<site_id>.json — array of 60 task drafts.

These are DRAFTS for the annotation interface refinement pipeline.
Annotators will walk through each, edit, add trajectory, and verify.

Usage:
    python scripts/generate_annotation_tasks.py                    # all sites
    python scripts/generate_annotation_tasks.py --site email       # single site
    python scripts/generate_annotation_tasks.py --site email --dry-run
"""

import argparse
import json
import os
import random
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SITES_DIR = PROJECT_ROOT / "sites"
OUTPUT_DIR = PROJECT_ROOT / "annotation" / "generated"


def load_site_context(site_id):
    """Load everything we need to generate tasks for a site."""
    site_dir = SITES_DIR / site_id
    ctx = {"site_id": site_id, "site_dir": site_dir}

    # Load routes.py to extract API endpoints
    routes_file = site_dir / "routes.py"
    if routes_file.exists():
        routes_text = routes_file.read_text()
        ctx["routes_text"] = routes_text
        ctx["endpoints"] = extract_endpoints(routes_text)
    else:
        ctx["routes_text"] = ""
        ctx["endpoints"] = []

    # Load data files (JSON + JSONL, first 50 items)
    ctx["data"] = {}
    ctx["entities"] = []
    data_dir = site_dir / "data"
    if data_dir.exists():
        for f in list(data_dir.glob("*.json")) + list(data_dir.glob("*.jsonl")):
            if f.name.startswith("."):
                continue
            try:
                if f.suffix == ".jsonl":
                    items = []
                    with open(f) as fh:
                        for i, line in enumerate(fh):
                            if i >= 50:
                                break
                            line = line.strip()
                            if line:
                                items.append(json.loads(line))
                    ctx["data"][f.stem.replace("_sample", "")] = items
                else:
                    ctx["data"][f.stem] = json.loads(f.read_text())
            except (json.JSONDecodeError, OSError):
                pass

    # Extract named entities from data
    ctx["entities"] = extract_entities(ctx["data"])
    ctx["users"] = ctx["data"].get("users", [])

    return ctx


def extract_endpoints(routes_text):
    """Extract Flask route definitions from routes.py."""
    endpoints = []
    for match in re.finditer(r'@blueprint\.route\("([^"]+)"(?:,\s*methods=\[([^\]]+)\])?\)', routes_text):
        path = match.group(1)
        methods = match.group(2) or '"GET"'
        methods = [m.strip().strip('"\'') for m in methods.split(",")]
        endpoints.append({"path": path, "methods": methods})
    return endpoints


def extract_entities(data_files):
    """Extract named entities from data for grounding tasks."""
    name_keys = ["name", "title", "word", "subject", "merchant", "company",
                 "campaign", "symbol", "from_addr", "headline", "topic",
                 "slug", "label"]
    filter_keys = ["category", "status", "type", "stage", "difficulty", "tier",
                   "role", "department", "gender", "looking_for", "funding_model",
                   "os", "brand", "sector", "side", "order_type", "account_type",
                   "section", "pos", "folder", "primary_category", "top_category"]

    entities = []
    for source, content in data_files.items():
        if source == "users":
            continue
        if not isinstance(content, list):
            continue
        for item in content:
            if not isinstance(item, dict):
                continue
            name = None
            for nk in name_keys:
                val = item.get(nk)
                if val and isinstance(val, str) and len(val) > 2 and len(val) < 100:
                    name = val
                    break
            if not name:
                continue
            filters = {k: v for k, v in item.items()
                       if isinstance(v, str) and k in filter_keys}
            fields = {k: v for k, v in item.items()
                      if isinstance(v, (str, int, float)) and k not in ("id", "password", "user_id")}
            entities.append({
                "name": name,
                "source": source,
                "filters": filters,
                "fields": fields,
            })
    return entities


def generate_tasks(ctx, rng):
    """Generate 60 tasks: 20 easy, 20 medium, 20 hard."""
    site_id = ctx["site_id"]
    entities = ctx["entities"]
    users = ctx["users"]
    endpoints = ctx["endpoints"]
    data = ctx["data"]

    # Categorize endpoints
    api_gets = [e for e in endpoints if "GET" in e["methods"] and "/api/" in e["path"]]
    api_posts = [e for e in endpoints if "POST" in e["methods"] and "/api/" in e["path"]]
    html_pages = [e for e in endpoints if "GET" in e["methods"] and "/api/" not in e["path"]
                  and e["path"] not in ("/login", "/logout")]

    # Get data collection names and sizes
    collections = {}
    for name, content in data.items():
        if name == "users":
            continue
        if isinstance(content, list):
            collections[name] = len(content)

    tasks = []
    used_instructions = set()

    def add_task(instruction, difficulty, macros):
        """Add task if not duplicate."""
        key = instruction.lower().strip()[:80]
        if key in used_instructions:
            return False
        used_instructions.add(key)
        tasks.append({
            "task_id": f"{site_id}_draft_{len(tasks)+1:03d}",
            "site": site_id,
            "instruction": instruction,
            "difficulty": difficulty,
            "macros": macros,
            "expected_answer": None,
            "eval": [],
            "status": "draft",
        })
        return True

    # ================================================================
    # EASY TASKS (20) — single macro, direct questions
    # ================================================================
    easy_count = 0

    # Count questions per collection
    for coll_name, coll_size in collections.items():
        if easy_count >= 20:
            break
        label = coll_name.replace("_", " ")
        if add_task(f"How many {label} are there in total on the {site_id.replace('-', ' ')} site?",
                    "easy", ["extract_by_route"]):
            easy_count += 1

    # Specific entity lookups
    if entities:
        sampled = rng.sample(entities, min(len(entities), 30))
        for ent in sampled:
            if easy_count >= 20:
                break
            if ent["fields"]:
                field, val = rng.choice(list(ent["fields"].items()))
                if field not in ("name", "title", "word"):
                    if add_task(f"What is the {field.replace('_', ' ')} of '{ent['name']}'?",
                                "easy", ["search_by_query", "extract_by_route"]):
                        easy_count += 1

    # Navigation questions
    for page in html_pages:
        if easy_count >= 20:
            break
        path = page["path"]
        if "<" in path:
            continue
        page_name = path.strip("/").replace("-", " ").replace("_", " ") or "home"
        if add_task(f"Navigate to the {page_name} page. What content is displayed there?",
                    "easy", ["navigate_by_route"]):
            easy_count += 1

    # Pad with search tasks
    if entities:
        for ent in rng.sample(entities, min(len(entities), 20)):
            if easy_count >= 20:
                break
            if add_task(f"Search for '{ent['name']}'. How many results are returned?",
                        "easy", ["search_by_query"]):
                easy_count += 1

    # ================================================================
    # MEDIUM TASKS (20) — 2-3 macros, multi-step
    # ================================================================
    medium_count = 0

    # Search + filter + count
    if entities:
        filter_entities = [e for e in entities if e.get("filters")]
        for ent in rng.sample(filter_entities, min(len(filter_entities), 10)) if filter_entities else []:
            if medium_count >= 20:
                break
            fk, fv = rng.choice(list(ent["filters"].items()))
            label = fk.replace("_", " ")
            if add_task(f"Filter the {ent['source'].replace('_', ' ')} by {label} '{fv}'. How many items match?",
                        "medium", ["filter_by_dropdown", "extract_by_route"]):
                medium_count += 1

    # Search + sort + extract first
    if entities:
        for ent in rng.sample(entities, min(len(entities), 10)):
            if medium_count >= 20:
                break
            if ent["fields"]:
                field = rng.choice(list(ent["fields"].keys()))
                if add_task(
                    f"Search for items related to '{ent['name']}', sort the results alphabetically. "
                    f"What is the {field.replace('_', ' ')} of the first result?",
                    "medium", ["search_by_query", "sort_by_ranking", "extract_by_route"]):
                    medium_count += 1

    # Filter + compute
    if entities:
        filter_entities = [e for e in entities if e.get("filters")]
        for ent in rng.sample(filter_entities, min(len(filter_entities), 10)) if filter_entities else []:
            if medium_count >= 20:
                break
            fk, fv = rng.choice(list(ent["filters"].items()))
            num_fields = [k for k, v in ent["fields"].items() if isinstance(v, (int, float))]
            if num_fields:
                nf = rng.choice(num_fields)
                if add_task(
                    f"Filter by {fk.replace('_', ' ')} = '{fv}'. "
                    f"What is the average {nf.replace('_', ' ')} of the filtered results?",
                    "medium", ["filter_by_dropdown", "extract_by_route", "compute_by_query"]):
                    medium_count += 1

    # Navigate + compare
    if len(entities) >= 2:
        pairs = rng.sample(entities, min(len(entities), 20))
        for i in range(0, len(pairs) - 1, 2):
            if medium_count >= 20:
                break
            a, b = pairs[i], pairs[i + 1]
            if a["source"] == b["source"] and a["fields"] and b["fields"]:
                common_fields = set(a["fields"].keys()) & set(b["fields"].keys())
                common_fields -= {"name", "title", "id"}
                if common_fields:
                    cf = rng.choice(list(common_fields))
                    if add_task(
                        f"Compare '{a['name']}' and '{b['name']}'. "
                        f"Which one has a higher {cf.replace('_', ' ')}?",
                        "medium", ["search_by_query", "extract_by_route", "compare_from_table"]):
                        medium_count += 1

    # Pad medium with navigation + extraction
    for page in html_pages:
        if medium_count >= 20:
            break
        path = page["path"]
        if "<" not in path:
            page_name = path.strip("/").replace("-", " ").replace("_", " ") or "home"
            if add_task(
                f"Go to the {page_name} page and find the most recent or first entry. What are its details?",
                "medium", ["navigate_by_route", "extract_by_route"]):
                medium_count += 1

    # ================================================================
    # HARD TASKS (20) — 4+ macros, require login + mutations
    # ================================================================
    hard_count = 0

    if users and entities:
        for user in rng.sample(users, min(len(users), 5)):
            if hard_count >= 20:
                break
            uname = user.get("username", "")
            pwd = user.get("password", "")
            if not uname or not pwd:
                continue

            ent = rng.choice(entities)

            # Login + search + save
            if add_task(
                f"Log in as '{uname}' (password: '{pwd}'). Search for '{ent['name']}' and "
                f"save/favorite it. Then go to your dashboard and confirm it appears in your saved items. "
                f"How many saved items do you have now?",
                "hard", ["authenticate_by_form", "search_by_query", "save_by_toggle", "navigate_by_route", "extract_by_route"]):
                hard_count += 1

            # Login + filter + sort + extract
            if ent.get("filters"):
                fk, fv = rng.choice(list(ent["filters"].items()))
                if add_task(
                    f"Log in as '{uname}' (password: '{pwd}'). Filter by {fk.replace('_', ' ')} = '{fv}', "
                    f"sort the results, and report the name and details of the top result.",
                    "hard", ["authenticate_by_form", "filter_by_dropdown", "sort_by_ranking", "extract_by_route"]):
                    hard_count += 1

            # Login + navigate + extract + compute
            if add_task(
                f"Log in as '{uname}' (password: '{pwd}'). Navigate to the main listing page. "
                f"How many total items are there? What is the breakdown by category/type if available?",
                "hard", ["authenticate_by_form", "navigate_by_route", "extract_by_route", "compute_by_query"]):
                hard_count += 1

            # Login + create
            if api_posts:
                if add_task(
                    f"Log in as '{uname}' (password: '{pwd}'). Create a new entry with a descriptive "
                    f"title and content. Verify it appears in the listing after creation.",
                    "hard", ["authenticate_by_form", "create_from_free_text", "navigate_by_route", "extract_by_route"]):
                    hard_count += 1

    # Multi-entity hard tasks
    if len(entities) >= 2:
        for _ in range(10):
            if hard_count >= 20:
                break
            a, b = rng.sample(entities, 2)
            if a["source"] == b["source"]:
                if add_task(
                    f"Find '{a['name']}' and '{b['name']}' in the {a['source'].replace('_', ' ')}. "
                    f"Compare their details side by side. Which one was created/added more recently? "
                    f"What are the key differences between them?",
                    "hard", ["search_by_query", "navigate_by_route", "extract_by_route",
                             "search_by_query", "extract_by_route", "compare_from_table"]):
                    hard_count += 1

    # Pad hard with login + exploration
    if users:
        for user in rng.sample(users, min(len(users), 10)):
            if hard_count >= 20:
                break
            uname = user.get("username", "")
            pwd = user.get("password", "")
            if add_task(
                f"Log in as '{uname}' (password: '{pwd}'). Explore all sections of the site. "
                f"Which section has the most content? How many items are in the largest section?",
                "hard", ["authenticate_by_form", "navigate_by_route", "navigate_by_dropdown",
                         "extract_by_route", "compute_by_query"]):
                hard_count += 1

    return tasks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", help="Generate for a single site")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)

    # Find sites
    sites = []
    for site_dir in sorted(SITES_DIR.iterdir()):
        if not site_dir.is_dir() or site_dir.name.startswith("_"):
            continue
        if not (site_dir / "tasks.json").exists():
            continue
        if (site_dir / "routes.py").stat().st_size < 500:
            continue
        if args.site and site_dir.name != args.site:
            continue
        sites.append(site_dir.name)

    print(f"Generating tasks for {len(sites)} sites...")
    total = 0

    for site_id in sites:
        ctx = load_site_context(site_id)
        tasks = generate_tasks(ctx, rng)

        easy = sum(1 for t in tasks if t["difficulty"] == "easy")
        medium = sum(1 for t in tasks if t["difficulty"] == "medium")
        hard = sum(1 for t in tasks if t["difficulty"] == "hard")

        print(f"  {site_id}: {len(tasks)} tasks (E:{easy} M:{medium} H:{hard}) "
              f"| {len(ctx['entities'])} entities, {len(ctx['users'])} users, {len(ctx['endpoints'])} endpoints")

        if not args.dry_run:
            out_path = OUTPUT_DIR / f"{site_id}.json"
            out_path.write_text(json.dumps(tasks, indent=2))

        total += len(tasks)

    print(f"\nTotal: {total} tasks generated")
    if not args.dry_run:
        print(f"Output: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
