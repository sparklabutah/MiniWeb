"""MiniWeb Task Annotation Interface.

Runs as part of the MiniWeb Flask app (same origin) so it can:
- Embed site pages in iframes without cross-origin issues
- Inject trajectory recording scripts into site pages
- Access site APIs directly for live verifier testing

Three modes:
  1. Blank Slate — annotator designs task from scratch
  2. Draft Queue — browse pre-generated drafts, refine each one
  3. Full Suite — all features + trajectory recording

Usage: The annotation blueprint is registered in the main MiniWeb app.
  Access at http://localhost:8080/annotate/
"""

import json
import os
import random
import uuid
from datetime import datetime
from pathlib import Path

from flask import Blueprint, jsonify, render_template, request

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SITES_DIR = PROJECT_ROOT / "sites"
TASKS_DIR = PROJECT_ROOT / "annotation" / "tasks"
GENERATED_DIR = PROJECT_ROOT / "annotation" / "generated"

annotation_bp = Blueprint(
    "annotation",
    __name__,
    template_folder="templates",
    static_folder="static",
    url_prefix="/annotate",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tasks_dir():
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    return TASKS_DIR


def _load_all_tasks():
    tasks = []
    for d in sorted(_tasks_dir().iterdir()):
        # Support both old format (flat .json) and new format (directory with task.json)
        if d.is_dir() and (d / "task.json").exists():
            try:
                tasks.append(json.loads((d / "task.json").read_text()))
            except (json.JSONDecodeError, OSError):
                pass
        elif d.is_file() and d.suffix == ".json":
            try:
                tasks.append(json.loads(d.read_text()))
            except (json.JSONDecodeError, OSError):
                pass
    return tasks


def _save_task(task):
    """Save task with heavy data (HTML, screenshots) in a subdirectory.

    Structure:
      annotation/tasks/<task_id>/
        task.json          — lightweight metadata (instruction, macros, eval, answer)
        trajectory.json    — action/observation sequence (ax_tree only, no raw HTML)
        html/              — raw HTML snapshots per step (step_001.html, ...)
        screenshots/       — screenshot files per step (step_001.png, ...)
    """
    task_id = task.get("task_id", f"task_{uuid.uuid4().hex[:8]}")
    task["task_id"] = task_id
    task["created_at"] = datetime.now().isoformat()

    # Create task directory
    task_dir = _tasks_dir() / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    html_dir = task_dir / "html"
    html_dir.mkdir(exist_ok=True)

    # Extract heavy data from trajectory into separate files
    trajectory = task.pop("trajectory", [])
    clean_trajectory = []
    step_num = 0

    for entry in trajectory:
        if entry.get("type") == "action":
            step_num += 1
            clean_trajectory.append({
                "type": "action",
                "step": step_num,
                "url": entry.get("url", ""),
                "timestamp": entry.get("timestamp", ""),
            })
        elif entry.get("type") == "observation":
            # Save raw HTML to separate file
            raw_html = entry.get("raw_html", "")
            if raw_html:
                (html_dir / f"step_{step_num:03d}.html").write_text(raw_html)

            # Keep ax_tree in trajectory (lightweight), strip raw HTML
            clean_trajectory.append({
                "type": "observation",
                "step": step_num,
                "title": entry.get("title", ""),
                "url": entry.get("url", ""),
                "ax_tree": entry.get("ax_tree", ""),
                "has_html": bool(raw_html),
                "has_screenshot": entry.get("screenshot", "") not in ("", "[screenshot:pending]", "[screenshot:error]"),
                "timestamp": entry.get("timestamp", ""),
            })

    # Save trajectory separately
    (task_dir / "trajectory.json").write_text(json.dumps(clean_trajectory, indent=2))

    # Save lightweight task metadata (no trajectory, no HTML)
    task["trajectory_steps"] = step_num
    (task_dir / "task.json").write_text(json.dumps(task, indent=2))

    return task_id


def _load_sites():
    sites = []
    for site_json in sorted(SITES_DIR.glob("*/site.json")):
        if site_json.parent.name.startswith("_"):
            continue
        if not (site_json.parent / "tasks.json").exists():
            continue
        if (site_json.parent / "routes.py").stat().st_size < 500:
            continue
        meta = json.loads(site_json.read_text())
        meta["url"] = f"/sites/{meta['id']}/"
        # Count generated drafts
        gen_file = GENERATED_DIR / f"{meta['id']}.json"
        meta["draft_count"] = 0
        if gen_file.exists():
            try:
                meta["draft_count"] = len(json.loads(gen_file.read_text()))
            except (json.JSONDecodeError, OSError):
                pass
        # Count annotated tasks
        meta["annotated_count"] = sum(
            1 for f in _tasks_dir().glob("*.json")
            if f.stem.startswith(meta["id"])
        )
        sites.append(meta)
    return sites


def _load_macros():
    macros = set()
    for tasks_file in SITES_DIR.glob("*/tasks.json"):
        try:
            for t in json.loads(tasks_file.read_text()):
                for m in t.get("macros", []):
                    macros.add(m)
        except (json.JSONDecodeError, OSError):
            pass
    return sorted(macros)


def _load_drafts(site_id):
    """Load pre-generated drafts for a site."""
    gen_file = GENERATED_DIR / f"{site_id}.json"
    if gen_file.exists():
        try:
            return json.loads(gen_file.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return []


def _generate_macro_prompt(sites, macros, coverage, preferred_site=None):
    """Sample a random site + macro set for the annotator to build a task around.

    Prioritizes under-covered macros and sites with fewer annotated tasks.
    """
    import random as rng

    # Pick site — prefer sites with fewer tasks
    site_pool = list(sites)  # all loaded sites are built (filtered in _load_sites)
    if not site_pool:
        return None
    if preferred_site and preferred_site.strip():
        site = next((s for s in site_pool if s["id"] == preferred_site), rng.choice(site_pool))
    else:
        # Weight toward sites with fewer annotated tasks
        weights = [1.0 / (s.get("annotated_count", 0) + 1) for s in site_pool]
        total = sum(weights)
        weights = [w / total for w in weights]
        site = rng.choices(site_pool, weights=weights, k=1)[0]

    # Pick 2-4 macros that make sense for this site
    # Get the site's own macros from its existing tasks
    site_dir = SITES_DIR / site["id"]
    site_macros = set()
    tasks_file = site_dir / "tasks.json"
    if tasks_file.exists():
        try:
            for t in json.loads(tasks_file.read_text()):
                for m in t.get("macros", []):
                    site_macros.add(m)
        except:
            pass
    # Fall back to full macro list if site has no tasks
    macro_pool = list(site_macros) if site_macros else list(macros)
    if not macro_pool:
        return None

    # Weight toward under-covered macros on this specific site
    site_coverage = {}
    for t in _load_all_tasks():
        if t.get("site") == site["id"]:
            for m in t.get("macros", []):
                site_coverage[m] = site_coverage.get(m, 0) + 1

    macro_weights = [1.0 / (site_coverage.get(m, 0) + coverage.get(m, 0) + 1) for m in macro_pool]
    total = sum(macro_weights)
    macro_weights = [w / total for w in macro_weights]

    n_macros = rng.choice([2, 2, 3, 3, 3, 4])
    sampled_macros = []
    remaining = list(zip(macro_pool, macro_weights))
    for _ in range(n_macros):
        if not remaining:
            break
        ms, ws = zip(*remaining)
        total = sum(ws)
        ws = [w / total for w in ws]
        pick = rng.choices(ms, weights=ws, k=1)[0]
        sampled_macros.append(pick)
        remaining = [(m, w) for m, w in remaining if m != pick]

    # Determine difficulty from macro count
    if len(sampled_macros) <= 1:
        difficulty = "easy"
    elif len(sampled_macros) <= 3:
        difficulty = "medium"
    else:
        difficulty = "hard"

    return {
        "site": site["id"],
        "site_name": site.get("name", site["id"]),
        "macros": sampled_macros,
        "difficulty": difficulty,
        "hint": f"Design a task on the {site.get('name', site['id'])} site that exercises: {' → '.join(sampled_macros)}",
    }


def _get_macro_coverage():
    tasks = _load_all_tasks()
    coverage = {}
    for t in tasks:
        for m in t.get("macros", []):
            coverage.setdefault(m, set()).add(t.get("site", "unknown"))
    return {m: len(sites) for m, sites in coverage.items()}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@annotation_bp.route("/")
def index():
    sites = _load_sites()
    tasks = _load_all_tasks()
    macros = _load_macros()
    coverage = _get_macro_coverage()
    return render_template("index.html",
                           sites=sites, task_count=len(tasks),
                           macros=macros, coverage=coverage)


@annotation_bp.route("/task/<mode>")
def annotate(mode):
    """Annotation interface. mode: prompt, queue"""
    site_id = request.args.get("site", "")
    draft_idx = request.args.get("idx", 0, type=int)
    sites = _load_sites()
    macros = _load_macros()
    coverage = _get_macro_coverage()

    # Load draft if in queue mode
    draft = None
    drafts = []
    if site_id and mode == "queue":
        drafts = _load_drafts(site_id)
        if drafts and 0 <= draft_idx < len(drafts):
            draft = drafts[draft_idx]

    # Generate macro prompt if in prompt mode
    macro_prompt = None
    if mode == "prompt":
        macro_prompt = _generate_macro_prompt(sites, macros, coverage, site_id)
        if macro_prompt and not site_id:
            site_id = macro_prompt["site"]

    return render_template("annotate.html",
                           mode=mode, site_id=site_id,
                           sites=sites, macros=macros,
                           draft=draft, draft_idx=draft_idx,
                           total_drafts=len(drafts),
                           macro_prompt=macro_prompt)


# --- API ---

@annotation_bp.route("/api/tasks", methods=["GET"])
def api_list_tasks():
    return jsonify(_load_all_tasks())


@annotation_bp.route("/api/tasks", methods=["POST"])
def api_create_task():
    data = request.get_json(silent=True) or {}
    if not data.get("instruction") or not data.get("site"):
        return jsonify({"error": "instruction and site required"}), 400

    task = {
        "task_id": f"{data['site']}_{uuid.uuid4().hex[:6]}",
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
        "draft_source": data.get("draft_source"),
    }
    task_id = _save_task(task)
    return jsonify({"task_id": task_id, "status": "saved"})


@annotation_bp.route("/api/drafts/<site_id>")
def api_drafts(site_id):
    drafts = _load_drafts(site_id)
    idx = request.args.get("idx", type=int)
    if idx is not None and 0 <= idx < len(drafts):
        return jsonify({"draft": drafts[idx], "idx": idx, "total": len(drafts)})
    return jsonify({"drafts": drafts, "total": len(drafts)})


@annotation_bp.route("/api/sites")
def api_sites():
    return jsonify(_load_sites())


@annotation_bp.route("/api/macros")
def api_macros():
    return jsonify(_load_macros())


@annotation_bp.route("/api/coverage")
def api_coverage():
    return jsonify(_get_macro_coverage())


@annotation_bp.route("/api/validate_eval", methods=["POST"])
def api_validate_eval():
    """Run eval config live. Since we're same-origin, we can call site APIs directly."""
    data = request.get_json(silent=True) or {}
    eval_configs = data.get("eval", [])
    agent_answer = data.get("agent_answer", "")

    # We're on the same Flask app — use the request host as server_url
    server_url = request.host_url.rstrip("/")

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


@annotation_bp.route("/dashboard")
def dashboard():
    tasks = _load_all_tasks()
    macros = _load_macros()
    coverage = _get_macro_coverage()

    site_counts = {}
    diff_counts = {"easy": 0, "medium": 0, "hard": 0}
    for t in tasks:
        s = t.get("site", "unknown")
        site_counts[s] = site_counts.get(s, 0) + 1
        d = t.get("difficulty", "medium")
        diff_counts[d] = diff_counts.get(d, 0) + 1

    return render_template("dashboard.html",
                           tasks=tasks, macros=macros, coverage=coverage,
                           site_counts=site_counts, diff_counts=diff_counts)
