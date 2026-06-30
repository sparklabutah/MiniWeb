#!/usr/bin/env python3
"""Orchestrate end-to-end generation of a MiniWeb site.

Usage:
    python scripts/generate_site.py specs/moocs-language-learning.json
    python scripts/generate_site.py specs/moocs-language-learning.json --step scaffold
    python scripts/generate_site.py specs/moocs-language-learning.json --step validate

Steps (run in order unless --step is given):
  1. scaffold  — run add_site.sh to create the directory skeleton
  2. generate  — invoke Claude Code to produce data, routes, templates, tasks, verifiers, solutions
  3. snapshot  — save data/*.json as pristine baseline
  4. validate  — run validate_site.py (reset + solve + verify for every task)

The 'generate' step prints a prompt to stdout (or invokes Claude Code if --auto).
This script is the reproducible wrapper; the actual content is LLM-generated.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
SITES_DIR = PROJECT_ROOT / "sites"

STEPS = ["scaffold", "generate", "snapshot", "validate"]


def load_spec(spec_path):
    with open(spec_path) as f:
        return json.load(f)


def step_scaffold(spec):
    site_id = spec["site_id"]
    site_dir = SITES_DIR / site_id
    if site_dir.exists():
        print(f"  Site directory already exists: {site_dir}")
        print("  Skipping scaffold (use existing directory).")
        return
    cmd = [
        str(SCRIPTS_DIR / "add_site.sh"),
        site_id,
        spec.get("site_name", site_id),
        spec.get("description", "A MiniWeb site"),
    ]
    subprocess.run(cmd, check=True)


def build_generation_prompt(spec):
    """Build the Claude Code prompt for generating site content."""
    site_id = spec["site_id"]
    site_dir = SITES_DIR / site_id

    # Load the bookstore as a reference
    bookstore_routes = (SITES_DIR / "bookstore" / "routes.py").read_text()

    # Load the MOOC site as a more complete reference (if it exists and isn't the target)
    mooc_ref = ""
    mooc_dir = SITES_DIR / "moocs-language-learning"
    if mooc_dir.exists() and site_id != "moocs-language-learning":
        mooc_ref = f"""
## Full reference site: moocs-language-learning

Study these files as the gold-standard pattern:
- sites/moocs-language-learning/routes.py — Flask blueprint with HTML + JSON API routes
- data_sources/moocs-language-learning/*.json — structured seed data
- sites/moocs-language-learning/tasks.json — 20 benchmark tasks (easy/medium/hard)
- sites/moocs-language-learning/verifiers.py — per-task HTTP verification functions
- sites/moocs-language-learning/reference_solutions.py — per-task solutions via test client
- sites/moocs-language-learning/templates/moocs-language-learning/*.html — Jinja2 templates
"""

    # Build the entity/feature description from the spec
    entities_desc = ""
    if "entities" in spec:
        entities_desc = "\n### Data entities\n"
        for e in spec["entities"]:
            fields = ", ".join(e.get("fields", []))
            entities_desc += f"- **{e['name']}**: {e.get('description', '')}. Fields: {fields}\n"

    features_desc = ""
    if "features" in spec:
        features_desc = "\n### Required features/API endpoints\n"
        for f in spec["features"]:
            features_desc += f"- {f}\n"

    task_guidance = ""
    if "task_guidance" in spec:
        task_guidance = f"\n### Task design guidance\n{spec['task_guidance']}\n"

    macros_list = ""
    if "target_macros" in spec:
        macros_list = "\n### Target macros to cover\n" + ", ".join(spec["target_macros"]) + "\n"

    prompt = f"""# Generate MiniWeb site: {spec.get('site_name', site_id)}

## Site spec
- **site_id**: {site_id}
- **name**: {spec.get('site_name', site_id)}
- **description**: {spec.get('description', '')}
- **domain**: {spec.get('domain', '')}
- **tags**: {', '.join(spec.get('tags', []))}
- **num_tasks**: {spec.get('num_tasks', 20)} (aim for ~6 easy, ~8 medium, ~6 hard)
{entities_desc}{features_desc}{task_guidance}{macros_list}
## What to generate

Generate the following files in `sites/{site_id}/`:

### 1. `site.json`
Update with the correct id, name, description, and tags.

### 2. Data files (`data_sources/{site_id}/*.json`)
Create realistic seed data JSON files for each entity in the shared data_sources directory.
Aim for 25-40 items for the primary entity and 5+ users. Data should be internally
consistent and rich enough to support the tasks.

### 3. `routes.py`
Flask blueprint with:
- HTML routes: index (list/search), detail page, user dashboard, comparison page
- JSON API routes: CRUD for all entities, filtering/sorting/search, aggregation/stats
- Write endpoints: create, update, delete operations that mutate data_sources/{site_id}/*.json
- Follow the pattern in the moocs-language-learning reference site exactly.

### 4. `templates/{site_id}/*.html`
Jinja2 templates: index.html, detail page(s), dashboard.html, compare.html.
Use `link rel="stylesheet" href="/static/style.css"` for base styles.

### 5. `tasks.json`
{spec.get('num_tasks', 20)} tasks with this structure:
```json
{{
    "task_id": "{site_id[:5]}-001",
    "difficulty": "easy|medium|hard",
    "instruction": "Natural language question/instruction",
    "expected_answer": "The correct answer",
    "verifier": "verify_{site_id[:5]}_001",
    "reference_solution": "solve_{site_id[:5]}_001",
    "macros": ["macro_name1", "macro_name2"]
}}
```
- Easy tasks: single API call, read-only (lookup, count, filter)
- Medium tasks: multi-step reads, computation, cross-entity joins
- Hard tasks: write operations (create, update, delete) + verification

### 6. `verifiers.py`
One function per task: `verify_XXX_NNN(server_url) -> {{"pass": bool, "detail": str}}`
Uses `requests` to check site state via HTTP. Verifiers check the *result* of the task,
not the process. For read tasks, verify the answer is correct. For write tasks, verify
the mutation is visible in the API.

### 7. `reference_solutions.py`
One function per task: `solve_XXX_NNN(client) -> str`
Uses the Flask test client to execute the solution path programmatically.
For read tasks: make API calls and return the answer.
For write tasks: make POST/PUT/DELETE calls, then verify.

## Critical rules

1. All verifiers and reference solutions must be self-contained — no hardcoded
   assumptions that break if data changes (use the API to look things up).
2. Write tasks must test that mutations persist (verify after writing).
3. Task expected_answers must be deterministic and match what the verifier checks.
4. Data must be rich enough that filter/sort/search tasks have non-trivial answers.
5. The `data_sources/{site_id}/.pristine/` directory is NOT your concern — the snapshot step handles it.
{mooc_ref}
"""
    return prompt


def step_generate(spec, auto=False):
    prompt = build_generation_prompt(spec)
    prompt_file = SCRIPTS_DIR / "last_generation_prompt.md"
    prompt_file.write_text(prompt)
    print(f"  Generation prompt written to: {prompt_file}")

    if auto:
        print("  Invoking Claude Code...")
        result = subprocess.run(
            ["claude", "-p", prompt, "--allowedTools",
             "Read,Write,Edit,Bash,Glob,Grep"],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT),
        )
        if result.returncode != 0:
            print(f"  Claude Code failed:\n{result.stderr}", file=sys.stderr)
            sys.exit(1)
        print(result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout)
    else:
        print("\n  Next: run Claude Code with this prompt to generate the site content.")
        print(f"  Example:  claude -p \"$(cat {prompt_file})\"")
        print(f"  Or copy the prompt and paste it into a Claude Code session.")


def step_snapshot(spec):
    site_id = spec["site_id"]
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "reset_site.py"), "--snapshot", site_id],
        capture_output=True, text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        sys.exit(1)


def step_validate(spec):
    site_id = spec["site_id"]
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "validate_site.py"), site_id],
        text=True, cwd=str(PROJECT_ROOT),
    )
    if result.returncode != 0:
        print("\n  Validation failed. Fix issues and re-run.")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Generate a MiniWeb site from a spec")
    parser.add_argument("spec", help="Path to site spec JSON file")
    parser.add_argument("--step", choices=STEPS, default=None,
                        help="Run only this step (default: run all in order)")
    parser.add_argument("--auto", action="store_true",
                        help="Auto-invoke Claude Code for generation (requires 'claude' CLI)")
    args = parser.parse_args()

    spec = load_spec(args.spec)
    print(f"Site: {spec['site_id']} — {spec.get('site_name', '(unnamed)')}\n")

    steps_to_run = [args.step] if args.step else STEPS

    step_funcs = {
        "scaffold": lambda: step_scaffold(spec),
        "generate": lambda: step_generate(spec, auto=args.auto),
        "snapshot": lambda: step_snapshot(spec),
        "validate": lambda: step_validate(spec),
    }

    for step in steps_to_run:
        print(f"=== Step: {step} ===")
        step_funcs[step]()
        print()


if __name__ == "__main__":
    main()
