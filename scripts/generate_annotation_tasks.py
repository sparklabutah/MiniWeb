#!/usr/bin/env python3
"""Pre-generate 60 annotation task drafts per site (20 easy / 20 medium / 20 hard).

Tasks are WebArena/Mind2Web-style natural language instructions, grounded in
actual site data. Each task is macro-centric: the instruction implicitly
exercises specific macros without naming them.

Output: annotation/generated/<site_id>.json

Usage:
    python scripts/generate_annotation_tasks.py
    python scripts/generate_annotation_tasks.py --site email
"""

import argparse
import json
import random
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SITES_DIR = PROJECT_ROOT / "sites"
OUTPUT_DIR = PROJECT_ROOT / "annotation" / "generated"


# ---------------------------------------------------------------------------
# Site context loader
# ---------------------------------------------------------------------------

def load_site_context(site_id):
    site_dir = SITES_DIR / site_id
    ctx = {"site_id": site_id}

    # Data
    ctx["data"] = {}
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
                            if i >= 50: break
                            if line.strip():
                                items.append(json.loads(line))
                    ctx["data"][f.stem.replace("_sample", "")] = items
                else:
                    ctx["data"][f.stem] = json.loads(f.read_text())
            except:
                pass

    ctx["users"] = ctx["data"].get("users", [])
    ctx["entities"] = _extract_entities(ctx["data"])

    # Routes
    routes_file = site_dir / "routes.py"
    if routes_file.exists():
        text = routes_file.read_text()
        ctx["api_endpoints"] = re.findall(r'@blueprint\.route\("(/api/[^"]+)"', text)
        ctx["html_pages"] = [m for m in re.findall(r'@blueprint\.route\("(/[^"]*)"', text)
                             if "/api/" not in m and m not in ("/login", "/logout")]
    else:
        ctx["api_endpoints"] = []
        ctx["html_pages"] = []

    return ctx


def _extract_entities(data_files):
    name_keys = ["name", "title", "word", "subject", "merchant", "company",
                 "campaign", "symbol", "from_addr", "headline", "topic", "slug", "label"]
    filter_keys = ["category", "status", "type", "stage", "difficulty", "tier",
                   "role", "department", "gender", "looking_for", "funding_model",
                   "os", "brand", "sector", "side", "order_type", "section", "pos", "folder"]
    entities = []
    for source, content in data_files.items():
        if source == "users" or not isinstance(content, list):
            continue
        for item in content:
            if not isinstance(item, dict):
                continue
            name = None
            for nk in name_keys:
                val = item.get(nk)
                if val and isinstance(val, str) and 2 < len(val) < 80:
                    name = val
                    break
            if not name:
                continue
            entities.append({
                "name": name, "source": source,
                "filters": {k: v for k, v in item.items() if isinstance(v, str) and k in filter_keys},
                "fields": {k: v for k, v in item.items()
                           if isinstance(v, (str, int, float)) and k not in ("id", "password", "user_id")
                           and len(str(v)) < 100},
            })
    return entities


# ---------------------------------------------------------------------------
# Task generation — natural language, macro-centric
# ---------------------------------------------------------------------------

# Each template: (instruction_format, difficulty, macros)
# Uses {name}, {source}, {field}, {value}, {filter_key}, {filter_val},
#       {user}, {pwd}, {collection}, {site}

EASY_TEMPLATES = [
    # navigate_by_route
    ("Show me the {collection} page on the {site} site.", ["navigate_by_route"]),
    ("Go to the {site} homepage and tell me what categories or sections are available.", ["navigate_by_route", "extract_by_route"]),
    # search_by_query
    ("Search for '{name}' on the {site} site.", ["search_by_query"]),
    ("Find anything related to '{name}' in the {site} search.", ["search_by_query"]),
    ("Look up '{name}' and tell me how many results come up.", ["search_by_query", "extract_by_route"]),
    # extract_by_route
    ("What is the {field} of '{name}'?", ["extract_by_route"]),
    ("Tell me the {field} for '{name}' on the {site} site.", ["search_by_query", "extract_by_route"]),
    ("How many {collection} are listed on the {site} site?", ["navigate_by_route", "extract_by_route"]),
    # navigate_by_dropdown
    ("Browse the {filter_key} section for '{filter_val}' on the {site} site.", ["navigate_by_dropdown"]),
    ("Navigate to the {filter_val} {filter_key} category.", ["navigate_by_dropdown"]),
]

MEDIUM_TEMPLATES = [
    # search + filter
    ("Find all {collection} in the '{filter_val}' {filter_key} and tell me how many there are.", ["search_by_query", "filter_by_dropdown", "extract_by_route"]),
    ("Search for '{name}' and filter by {filter_key} '{filter_val}'. What results show up?", ["search_by_query", "filter_by_dropdown", "extract_by_route"]),
    # filter + sort
    ("Show me {collection} filtered by {filter_key} '{filter_val}', sorted by the most recent first.", ["filter_by_dropdown", "sort_by_ranking", "extract_by_route"]),
    ("List all {collection} in the '{filter_val}' {filter_key}, ordered alphabetically.", ["filter_by_dropdown", "sort_by_ranking"]),
    # search + extract specific field
    ("Find '{name}' and tell me its {field} and {field2}.", ["search_by_query", "extract_by_route"]),
    ("Look up '{name}' — what {filter_key} is it in, and what is its {field}?", ["search_by_query", "extract_by_route"]),
    # compare
    ("Compare '{name}' and '{name2}' — which one has a higher {field}?", ["search_by_query", "extract_by_route", "compare_from_table"]),
    # navigate + extract
    ("Go to the {collection} section and find the first item listed. What are its details?", ["navigate_by_route", "extract_by_route"]),
    # count with filter
    ("How many {collection} have {filter_key} set to '{filter_val}'?", ["filter_by_dropdown", "extract_by_route"]),
]

HARD_TEMPLATES = [
    # authenticate + search + save
    ("Log in as '{user}' (password: '{pwd}'), find '{name}', and save it to your favorites. Confirm it appears in your saved items.", ["authenticate_by_form", "search_by_query", "save_by_toggle", "navigate_by_route", "extract_by_route"]),
    # authenticate + create
    ("Log in as '{user}' (password: '{pwd}') and create a new {single} titled '{new_title}'. Verify it shows up in the listing.", ["authenticate_by_form", "create_from_free_text", "navigate_by_route", "extract_by_route"]),
    # authenticate + filter + sort + extract
    ("Log in as '{user}' (password: '{pwd}'), filter {collection} by {filter_key} '{filter_val}', sort by name, and tell me the top result.", ["authenticate_by_form", "filter_by_dropdown", "sort_by_ranking", "extract_by_route"]),
    # authenticate + edit
    ("Log in as '{user}' (password: '{pwd}') and update the details of '{name}'. Change its {field} to something different. Verify the change saved.", ["authenticate_by_form", "search_by_query", "edit_by_form", "extract_by_route"]),
    # authenticate + multi-step navigation
    ("Log in as '{user}' (password: '{pwd}'). Check your dashboard — how many saved or favorited items do you have? Then navigate to the main listing and report the total count.", ["authenticate_by_form", "navigate_by_route", "extract_by_route"]),
    # search + save + verify
    ("Log in as '{user}' (password: '{pwd}'), search for items related to '{name}', save the first result, then check your profile to confirm the save.", ["authenticate_by_form", "search_by_query", "save_by_toggle", "navigate_by_route", "extract_by_route"]),
    # multi-entity comparison
    ("Find '{name}' and '{name2}' on the {site} site. Compare their details side by side — what are the key differences?", ["search_by_query", "extract_by_route", "compare_from_table"]),
    # authenticate + delete
    ("Log in as '{user}' (password: '{pwd}') and remove '{name}' from your saved items. Verify it's no longer in your list.", ["authenticate_by_form", "navigate_by_route", "delete_from_table", "extract_by_route"]),
]


def generate_tasks(ctx, rng):
    site_id = ctx["site_id"]
    site_label = site_id.replace("-", " ").replace("_", " ")
    entities = ctx["entities"]
    users = ctx["users"]
    data = ctx["data"]

    # Collection names (data file names, human-readable)
    collections = {}
    for name, content in data.items():
        if name != "users" and isinstance(content, list) and len(content) > 0:
            collections[name] = name.replace("_", " ")

    tasks = []
    used = set()

    def add(instruction, difficulty, macros):
        key = instruction.lower()[:80]
        if key in used:
            return False
        used.add(key)
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

    def fill_template(template, difficulty, macros):
        """Try to fill a template with real data. Returns None if can't fill."""
        t = template
        needs = set(re.findall(r'\{(\w+)\}', t))

        replacements = {"site": site_label}

        # Collection
        if "collection" in needs and collections:
            coll_key = rng.choice(list(collections.keys()))
            replacements["collection"] = collections[coll_key]
            replacements["single"] = collections[coll_key].rstrip("s")  # naive singular

        # Entity
        ent = rng.choice(entities) if entities else None
        if ent:
            replacements["name"] = ent["name"]
            replacements["source"] = ent["source"].replace("_", " ")

            # Fields
            if ent["fields"]:
                field_keys = [k for k in ent["fields"] if k not in ("name", "title", "word")]
                if field_keys:
                    f1 = rng.choice(field_keys)
                    replacements["field"] = f1.replace("_", " ")
                    replacements["value"] = str(ent["fields"][f1])
                    remaining = [k for k in field_keys if k != f1]
                    if remaining:
                        replacements["field2"] = rng.choice(remaining).replace("_", " ")

            # Filters
            if ent["filters"]:
                fk, fv = rng.choice(list(ent["filters"].items()))
                replacements["filter_key"] = fk.replace("_", " ")
                replacements["filter_val"] = fv

        # Second entity for comparison
        if "name2" in needs and len(entities) >= 2:
            ent2 = rng.choice([e for e in entities if e["name"] != replacements.get("name", "")])
            replacements["name2"] = ent2["name"]

        # User
        if "user" in needs and users:
            u = rng.choice(users)
            replacements["user"] = u.get("username", "")
            replacements["pwd"] = u.get("password", "")

        # New title for creation tasks
        if "new_title" in needs:
            adjectives = ["Updated", "New", "Draft", "Test", "Review", "Weekly", "Monthly"]
            nouns = ["Report", "Entry", "Document", "Item", "Record", "Note", "Summary"]
            replacements["new_title"] = f"{rng.choice(adjectives)} {rng.choice(nouns)} {rng.randint(1,99)}"

        # Check all placeholders filled
        for need in needs:
            if need not in replacements:
                return None

        try:
            instruction = t.format(**replacements)
            return instruction
        except (KeyError, IndexError):
            return None

    # Generate easy (20)
    easy_count = 0
    templates = list(EASY_TEMPLATES) * 4  # repeat for variety
    rng.shuffle(templates)
    for tmpl, macros in templates:
        if easy_count >= 20:
            break
        instruction = fill_template(tmpl, "easy", macros)
        if instruction and add(instruction, "easy", macros):
            easy_count += 1

    # Generate medium (20)
    medium_count = 0
    templates = list(MEDIUM_TEMPLATES) * 4
    rng.shuffle(templates)
    for tmpl, macros in templates:
        if medium_count >= 20:
            break
        instruction = fill_template(tmpl, "medium", macros)
        if instruction and add(instruction, "medium", macros):
            medium_count += 1

    # Generate hard (20)
    hard_count = 0
    templates = list(HARD_TEMPLATES) * 4
    rng.shuffle(templates)
    for tmpl, macros in templates:
        if hard_count >= 20:
            break
        instruction = fill_template(tmpl, "hard", macros)
        if instruction and add(instruction, "hard", macros):
            hard_count += 1

    return tasks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", help="Single site")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)

    sites = []
    for d in sorted(SITES_DIR.iterdir()):
        if not d.is_dir() or d.name.startswith("_"):
            continue
        if not (d / "tasks.json").exists() or (d / "routes.py").stat().st_size < 500:
            continue
        if args.site and d.name != args.site:
            continue
        sites.append(d.name)

    print(f"Generating for {len(sites)} sites...")
    total = 0

    for site_id in sites:
        ctx = load_site_context(site_id)
        tasks = generate_tasks(ctx, rng)

        e = sum(1 for t in tasks if t["difficulty"] == "easy")
        m = sum(1 for t in tasks if t["difficulty"] == "medium")
        h = sum(1 for t in tasks if t["difficulty"] == "hard")

        print(f"  {site_id}: {len(tasks)} tasks (E:{e} M:{m} H:{h}) | {len(ctx['entities'])} entities")

        out = OUTPUT_DIR / f"{site_id}.json"
        out.write_text(json.dumps(tasks, indent=2))
        total += len(tasks)

    print(f"\nTotal: {total}")


if __name__ == "__main__":
    main()
