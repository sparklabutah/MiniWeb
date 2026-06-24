"""MiniWeb Task Annotation Interface.

Three modes:
  1. Blank Slate (Kenny/Farhan) — annotator designs task from scratch
  2. LLM Draft (Minh) — LLM proposes task, annotator validates + walks through
  3. Full Suite (Claude synthesis) — split-screen with all features

Run: python annotation/app.py --port 8081 --miniweb-url http://localhost:8080
"""

import argparse
import json
import os
import random
import sys
import uuid
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

TASKS_DIR = PROJECT_ROOT / "annotation" / "tasks"
MACROS_FILE = PROJECT_ROOT / "annotation" / "macro_bank.json"

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = "annotation-dev-key"

MINIWEB_URL = "http://localhost:8080"


# ---------------------------------------------------------------------------
# Task storage (JSON file per task, simple and portable)
# ---------------------------------------------------------------------------

def _tasks_dir():
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    return TASKS_DIR


def _load_all_tasks():
    tasks = []
    for f in sorted(_tasks_dir().glob("*.json")):
        tasks.append(json.loads(f.read_text()))
    return tasks


def _save_task(task):
    task_id = task.get("task_id", str(uuid.uuid4())[:8])
    task["task_id"] = task_id
    task["created_at"] = datetime.now().isoformat()
    path = _tasks_dir() / f"{task_id}.json"
    path.write_text(json.dumps(task, indent=2))
    return task_id


def _load_sites():
    """Load available MiniWeb sites."""
    sites = []
    sites_dir = PROJECT_ROOT / "sites"
    for site_json in sorted(sites_dir.glob("*/site.json")):
        if site_json.parent.name.startswith("_"):
            continue
        if not (site_json.parent / "routes.py").exists():
            continue
        meta = json.loads(site_json.read_text())
        has_tasks = (site_json.parent / "tasks.json").exists()
        routes_size = (site_json.parent / "routes.py").stat().st_size
        if has_tasks and routes_size > 500:
            meta["built"] = True
            meta["evaluated"] = True  # all built sites with tasks are annotation-ready
            meta["url"] = f"/sites/{meta['id']}/"
            sites.append(meta)
    return sites


def _load_macros():
    """Load macro vocabulary."""
    if MACROS_FILE.exists():
        return json.loads(MACROS_FILE.read_text())
    # Fallback: extract from tasks.json files across sites
    macros = set()
    for tasks_file in (PROJECT_ROOT / "sites").glob("*/tasks.json"):
        tasks = json.loads(tasks_file.read_text())
        for t in tasks:
            for m in t.get("macros", []):
                macros.add(m)
    return sorted(macros)


def _get_macro_coverage():
    """Compute macro × site coverage from annotated tasks."""
    tasks = _load_all_tasks()
    coverage = {}  # macro -> set of sites
    for t in tasks:
        for m in t.get("macros", []):
            coverage.setdefault(m, set()).add(t.get("site", "unknown"))
    return {m: len(sites) for m, sites in coverage.items()}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    sites = _load_sites()
    tasks = _load_all_tasks()
    macros = _load_macros()
    coverage = _get_macro_coverage()
    return render_template("index.html",
                           sites=sites, task_count=len(tasks),
                           macros=macros, coverage=coverage,
                           miniweb_url=MINIWEB_URL)


@app.route("/annotate/<mode>")
def annotate(mode):
    """Annotation interface. Mode: blank, llm_draft, full"""
    site_id = request.args.get("site", "")
    sites = _load_sites()
    macros = _load_macros()
    return render_template("annotate.html",
                           mode=mode, site_id=site_id,
                           sites=sites, macros=macros,
                           miniweb_url=MINIWEB_URL)


@app.route("/api/tasks", methods=["GET"])
def api_list_tasks():
    tasks = _load_all_tasks()
    return jsonify(tasks)


@app.route("/api/tasks", methods=["POST"])
def api_create_task():
    data = request.get_json(silent=True) or {}
    required = ["instruction", "site"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing fields: {missing}"}), 400

    task = {
        "task_id": f"{data['site']}_{str(uuid.uuid4())[:6]}",
        "site": data["site"],
        "sites": data.get("sites", [data["site"]]),
        "instruction": data["instruction"],
        "difficulty": data.get("difficulty", "medium"),
        "macros": data.get("macros", []),
        "expected_answer": data.get("expected_answer"),
        "eval": data.get("eval", []),
        "eval_logic": data.get("eval_logic", "all"),
        "trajectory": data.get("trajectory", []),
        "annotator": data.get("annotator", "anonymous"),
        "mode": data.get("mode", "unknown"),
    }

    task_id = _save_task(task)
    return jsonify({"task_id": task_id, "status": "saved"})


@app.route("/api/tasks/<task_id>", methods=["GET"])
def api_get_task(task_id):
    path = _tasks_dir() / f"{task_id}.json"
    if not path.exists():
        return jsonify({"error": "not found"}), 404
    return jsonify(json.loads(path.read_text()))


@app.route("/api/generate_draft", methods=["POST"])
def api_generate_draft():
    """Generate a task draft using macro-chain-first approach:
    1. Sample a macro chain (reject if duplicate)
    2. Explore site data to ground the task in real entities
    3. Compose a specific, data-grounded instruction
    """
    data = request.get_json(silent=True) or {}
    site_id = data.get("site", "")
    if not site_id:
        return jsonify({"error": "No site specified"}), 400

    site_dir = PROJECT_ROOT / "sites" / site_id
    draft = _macro_first_draft(site_id, site_dir)
    return jsonify(draft)


def _macro_first_draft(site_id, site_dir):
    """Macro-chain-first task generation:
    Step 1: Sample a macro chain from the vocabulary
    Step 2: Explore site data to find entities that match the chain
    Step 3: Write a specific instruction grounded in real data
    """
    rng = random.Random()

    # --- Step 0: Load site context ---
    data_files = _load_site_data(site_dir)
    users = data_files.get("users", [])
    existing_chains = _load_existing_chains(site_dir)
    entities = _extract_entities(data_files)

    # --- Step 1: Sample a macro chain ---
    # Define valid chain patterns by difficulty
    easy_chains = [
        ["navigate_by_route"],
        ["search_by_query"],
        ["extract_by_route"],
        ["navigate_by_dropdown"],
    ]
    medium_chains = [
        ["search_by_query", "extract_by_route"],
        ["filter_by_dropdown", "extract_by_route"],
        ["search_by_query", "sort_by_ranking", "extract_by_route"],
        ["navigate_by_route", "extract_by_route", "compute_by_query"],
        ["filter_by_dropdown", "sort_by_ranking", "extract_by_route"],
        ["search_by_query", "filter_by_dropdown", "extract_by_route"],
        ["navigate_by_dropdown", "extract_by_route", "compare_from_table"],
    ]
    hard_chains = [
        ["authenticate_by_form", "search_by_query", "extract_by_route"],
        ["authenticate_by_form", "navigate_by_route", "extract_by_route", "compute_by_query"],
        ["authenticate_by_form", "search_by_query", "save_by_toggle", "extract_by_route"],
        ["authenticate_by_form", "create_from_free_text", "extract_by_route"],
        ["authenticate_by_form", "navigate_by_route", "edit_by_form", "extract_by_route"],
        ["authenticate_by_form", "filter_by_dropdown", "sort_by_ranking", "extract_by_route", "compute_by_query"],
        ["search_by_query", "navigate_by_route", "extract_by_route", "search_by_query", "compare_from_table"],
    ]

    # Pick difficulty and sample chain, rejecting duplicates
    all_pools = [("easy", easy_chains), ("medium", medium_chains), ("hard", hard_chains)]
    rng.shuffle(all_pools)

    chain = None
    difficulty = None
    for diff, pool in all_pools:
        rng.shuffle(pool)
        for candidate in pool:
            chain_key = tuple(candidate)
            if chain_key not in existing_chains:
                chain = candidate
                difficulty = diff
                break
        if chain:
            break

    if not chain:
        # All chains used — pick a random one anyway
        pool = easy_chains + medium_chains + hard_chains
        chain = rng.choice(pool)
        difficulty = "easy" if len(chain) <= 1 else ("medium" if len(chain) <= 3 else "hard")

    # --- Step 2: Explore data to find entities matching the chain ---
    user = rng.choice(users) if users else None
    entity = rng.choice(entities) if entities else None

    # --- Step 3: Compose instruction from chain + data ---
    instruction = _compose_instruction(chain, difficulty, site_id, entity, user, data_files, rng)

    return {
        "site": site_id,
        "instruction": instruction,
        "difficulty": difficulty,
        "macros": chain,
        "expected_answer": None,
        "grounded_entity": {
            "name": entity["name"] if entity else None,
            "source": entity["source"] if entity else None,
        },
    }


def _load_site_data(site_dir):
    """Load all JSON data files from a site."""
    data_files = {}
    data_dir = site_dir / "data"
    if data_dir.exists():
        for f in data_dir.glob("*.json"):
            if f.name.startswith("."):
                continue
            try:
                data_files[f.stem] = json.loads(f.read_text())
            except (json.JSONDecodeError, OSError):
                pass
    return data_files


def _load_existing_chains(site_dir):
    """Load macro chains already used in existing + annotated tasks."""
    chains = set()
    # From construction tasks
    tasks_file = site_dir / "tasks.json"
    if tasks_file.exists():
        try:
            for t in json.loads(tasks_file.read_text()):
                chains.add(tuple(t.get("macros", [])))
        except (json.JSONDecodeError, OSError):
            pass
    # From annotated tasks
    for f in _tasks_dir().glob("*.json"):
        try:
            t = json.loads(f.read_text())
            if t.get("site") == site_dir.name:
                chains.add(tuple(t.get("macros", [])))
        except (json.JSONDecodeError, OSError):
            pass
    return chains


def _extract_entities(data_files):
    """Extract named entities from data files for grounding tasks."""
    name_keys = ["name", "title", "word", "subject", "merchant", "company",
                 "campaign", "symbol", "sender", "from", "from_addr", "username",
                 "slug", "question", "topic", "headline", "label", "description"]
    entities = []
    for source, content in data_files.items():
        if source == "users":
            continue
        if isinstance(content, list):
            for item in content:
                if not isinstance(item, dict):
                    continue
                for nk in name_keys:
                    val = item.get(nk)
                    if val and isinstance(val, str) and len(val) > 2:
                        # Collect filterable fields
                        filters = {}
                        for fk, fv in item.items():
                            if isinstance(fv, str) and fk in (
                                "category", "status", "type", "stage", "difficulty", "tier",
                                "role", "department", "gender", "looking_for", "funding_model",
                                "os", "brand", "sector", "side", "order_type", "account_type",
                                "section", "pos", "folder",
                            ):
                                filters[fk] = fv
                        entities.append({
                            "name": val,
                            "source": source,
                            "data": item,
                            "filters": filters,
                            "fields": {k: v for k, v in item.items()
                                       if isinstance(v, (str, int, float)) and k not in ("id", "password")},
                        })
                        break
    return entities


def _compose_instruction(chain, difficulty, site_id, entity, user, data_files, rng):
    """Compose a natural language instruction from a macro chain + grounded data."""
    site_label = site_id.replace("-", " ").replace("_", " ")
    parts = []

    # Auth step
    if "authenticate_by_form" in chain and user:
        parts.append(f"Log in as '{user.get('username', '')}' (password: '{user.get('password', '')}').")

    # Navigation
    if "navigate_by_route" in chain and entity:
        parts.append(f"Go to the detail page for '{entity['name']}'.")
    elif "navigate_by_dropdown" in chain and entity and entity.get("filters"):
        fk, fv = next(iter(entity["filters"].items()))
        parts.append(f"Navigate to the {fk.replace('_', ' ')} section for '{fv}'.")

    # Search
    if "search_by_query" in chain and entity:
        parts.append(f"Search for '{entity['name']}'.")

    # Filter
    if "filter_by_dropdown" in chain and entity and entity.get("filters"):
        fk, fv = rng.choice(list(entity["filters"].items()))
        parts.append(f"Filter by {fk.replace('_', ' ')} = '{fv}'.")

    # Sort
    if "sort_by_ranking" in chain:
        sort_fields = ["name", "date", "price", "amount", "rating", "score"]
        parts.append(f"Sort the results by {rng.choice(sort_fields)}.")

    # Extract / compute
    if "extract_by_route" in chain and entity and entity.get("fields"):
        field, val = rng.choice(list(entity["fields"].items()))
        parts.append(f"What is the {field.replace('_', ' ')} of '{entity['name']}'?")
    elif "extract_by_route" in chain:
        parts.append("How many results are shown?")

    if "compute_by_query" in chain:
        parts.append("What is the total count or sum?")

    # Mutation actions
    if "save_by_toggle" in chain and entity:
        parts.append(f"Save or favorite '{entity['name']}'.")
    if "create_from_free_text" in chain:
        parts.append("Create a new entry with a descriptive title and content.")
    if "edit_by_form" in chain and entity:
        parts.append(f"Edit the details of '{entity['name']}' — change one field.")

    # Compare
    if "compare_from_table" in chain:
        parts.append("Compare the top two results side by side.")

    # Verification step for mutation tasks
    if any(m in chain for m in ("save_by_toggle", "create_from_free_text", "edit_by_form")):
        parts.append("Verify the change was saved successfully.")

    # Assemble
    if parts:
        instruction = " ".join(parts)
    else:
        # Fallback — still grounded
        if entity:
            instruction = f"On the {site_label} site, find '{entity['name']}' in the {entity['source'].replace('_', ' ')} and report its details."
        else:
            source = rng.choice([k for k in data_files if k != "users"]) if len(data_files) > 1 else site_label
            instruction = f"On the {site_label} site, browse the {source.replace('_', ' ')} and report how many entries there are."

    return instruction


@app.route("/api/sites", methods=["GET"])
def api_sites():
    return jsonify(_load_sites())


@app.route("/api/macros", methods=["GET"])
def api_macros():
    return jsonify(_load_macros())


@app.route("/api/coverage", methods=["GET"])
def api_coverage():
    return jsonify(_get_macro_coverage())


@app.route("/api/validate_eval", methods=["POST"])
def api_validate_eval():
    """Run eval config against provided answer/state. Live validation for the UI."""
    data = request.get_json(silent=True) or {}
    eval_configs = data.get("eval", [])
    agent_answer = data.get("agent_answer", "")
    server_url = MINIWEB_URL

    from annotation.evaluators import run_task_eval
    passed, results = run_task_eval(
        eval_configs,
        eval_logic=data.get("eval_logic", "all"),
        agent_answer=agent_answer,
        server_url=server_url,
        navigation_trace=data.get("navigation_trace", []),
    )
    return jsonify({
        "passed": passed,
        "results": [{"evaluator": r[0], "passed": r[1], "detail": r[2]} for r in results],
    })


@app.route("/dashboard")
def dashboard():
    tasks = _load_all_tasks()
    macros = _load_macros()
    coverage = _get_macro_coverage()

    # Per-site counts
    site_counts = {}
    for t in tasks:
        s = t.get("site", "unknown")
        site_counts[s] = site_counts.get(s, 0) + 1

    # Per-difficulty counts
    diff_counts = {"easy": 0, "medium": 0, "hard": 0}
    for t in tasks:
        d = t.get("difficulty", "medium")
        diff_counts[d] = diff_counts.get(d, 0) + 1

    return render_template("dashboard.html",
                           tasks=tasks, macros=macros, coverage=coverage,
                           site_counts=site_counts, diff_counts=diff_counts,
                           miniweb_url=MINIWEB_URL)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MiniWeb Annotation Interface")
    parser.add_argument("--port", type=int, default=8081)
    parser.add_argument("--miniweb-url", default="http://localhost:8080")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    MINIWEB_URL = args.miniweb_url

    print(f"Annotation interface: http://localhost:{args.port}")
    print(f"MiniWeb server:       {MINIWEB_URL}")
    print(f"Tasks stored in:      {TASKS_DIR}")

    app.run(port=args.port, debug=args.debug)
