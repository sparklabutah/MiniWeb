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
        has_results = (site_json.parent / "results").exists() and any((site_json.parent / "results").iterdir()) if (site_json.parent / "results").exists() else False
        routes_size = (site_json.parent / "routes.py").stat().st_size
        if has_tasks and routes_size > 500:
            meta["built"] = True
            meta["evaluated"] = has_results
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
    """Generate a data-grounded task draft by reading the site's actual data and routes."""
    data = request.get_json(silent=True) or {}
    site_id = data.get("site", "")
    if not site_id:
        return jsonify({"error": "No site specified"}), 400

    site_dir = PROJECT_ROOT / "sites" / site_id

    # Load real data from the site to ground the task
    draft = _generate_data_grounded_draft(site_id, site_dir)
    return jsonify(draft)


def _generate_data_grounded_draft(site_id, site_dir):
    """Generate task drafts grounded in actual site data."""
    rng = random.Random()

    # Load site data files
    data_files = {}
    data_dir = site_dir / "data"
    if data_dir.exists():
        for f in data_dir.glob("*.json"):
            if f.name.startswith("."):
                continue
            try:
                content = json.loads(f.read_text())
                data_files[f.stem] = content
            except (json.JSONDecodeError, OSError):
                pass

    # Load existing tasks to get macro patterns
    existing_macros = []
    tasks_file = site_dir / "tasks.json"
    if tasks_file.exists():
        try:
            for t in json.loads(tasks_file.read_text()):
                existing_macros.extend(t.get("macros", []))
        except (json.JSONDecodeError, OSError):
            pass

    # Pick a random data entity to ground the task
    users = data_files.get("users", [])
    entity_name = None
    entity_data = {}
    entity_source = None

    # Try to find interesting data entities — prefer ones with good name fields
    name_keys = ["name", "title", "word", "subject", "merchant", "company", "campaign"]
    best_entity = None
    best_name = None
    best_source = None

    for key, content in data_files.items():
        if key in ("users",):
            continue
        if isinstance(content, list) and len(content) > 2 and isinstance(content[0], dict):
            # Pick entities that have a meaningful name field
            candidates = []
            for item in content:
                for nk in name_keys:
                    val = item.get(nk)
                    if val and isinstance(val, str) and len(val) > 2:
                        candidates.append((item, val, key))
                        break
            if candidates:
                entity_data, entity_name, entity_source = rng.choice(candidates)
                best_entity = entity_data
                best_name = entity_name
                best_source = entity_source
                break

    if best_entity:
        entity_name = best_name
        entity_data = best_entity
        entity_source = best_source

    # Pick a random user for auth-required tasks
    user = rng.choice(users) if users else None

    # Generate task templates grounded in real data
    templates = []

    # Easy tasks (1 macro) — data extraction
    if entity_name and entity_source:
        templates.append({
            "instruction": f"How many items are in the {entity_source.replace('_', ' ')} collection? Use the site's search or browse features to find the total count.",
            "difficulty": "easy",
            "macros": ["extract_by_route"],
        })
        if isinstance(entity_data, dict):
            # Pick a real field from the entity
            fields = [k for k, v in entity_data.items() if isinstance(v, (str, int, float)) and k not in ("id", "password")]
            if fields:
                field = rng.choice(fields)
                val = entity_data[field]
                templates.append({
                    "instruction": f"Look up '{entity_name}' on the site. What is its {field.replace('_', ' ')}?",
                    "difficulty": "easy",
                    "macros": ["search_by_query", "extract_by_route"],
                    "expected_answer": str(val),
                })

    if entity_source:
        templates.append({
            "instruction": f"Navigate to the site and search for '{entity_name}'. How many results appear?",
            "difficulty": "easy",
            "macros": ["search_by_query"],
        })

    # Medium tasks (2-3 macros) — search + filter + extract
    if entity_data and isinstance(entity_data, dict):
        # Find a filterable field
        cat_fields = [k for k, v in entity_data.items() if isinstance(v, str) and k in (
            "category", "status", "type", "stage", "difficulty", "tier", "role",
            "department", "gender", "looking_for", "funding_model", "os", "brand",
        )]
        if cat_fields:
            cf = rng.choice(cat_fields)
            cv = entity_data[cf]
            templates.append({
                "instruction": f"Filter the {entity_source.replace('_', ' ')} by {cf.replace('_', ' ')} = '{cv}'. How many results match this filter?",
                "difficulty": "medium",
                "macros": ["filter_by_dropdown", "extract_by_route"],
            })

    # Hard tasks (4+ macros) — login + multi-step
    if user:
        uname = user.get("username", "")
        pwd = user.get("password", "")
        templates.append({
            "instruction": f"Log in as '{uname}' (password: '{pwd}'). Navigate to the dashboard or profile page. How many saved/favorited items does this user have?",
            "difficulty": "hard",
            "macros": ["authenticate_by_form", "navigate_by_route", "extract_by_route"],
        })
        if entity_name:
            templates.append({
                "instruction": f"Log in as '{uname}' (password: '{pwd}'). Search for '{entity_name}', view its detail page, and save/favorite it. Then check your dashboard to confirm it was saved.",
                "difficulty": "hard",
                "macros": ["authenticate_by_form", "search_by_query", "navigate_by_route", "save_by_toggle", "extract_by_route"],
            })

    if not templates:
        templates.append({
            "instruction": f"Navigate to the {site_id} site. Explore the main page and report what the primary content type is and how many items are displayed.",
            "difficulty": "easy",
            "macros": ["navigate_by_route", "extract_by_route"],
        })

    draft = rng.choice(templates)
    draft["site"] = site_id
    draft["grounded_entity"] = {"name": entity_name, "source": entity_source}
    return draft


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
