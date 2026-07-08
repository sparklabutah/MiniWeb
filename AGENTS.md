# AGENTS.md

Guidance for coding agents (Claude Code, Codex, etc.) working in this repository.

## Quick Start

```bash
pip install -r requirements.txt
python run.py
# Runs on http://localhost:8080
```

No test suite or linter configured.

## Architecture

MiniWeb is a Flask app hosting 65 sites under a browser-like portal, designed for benchmarking browser agents.

**Entry point**: `run.py` → `create_app()` in `app/__init__.py`:
1. Registers portal blueprint at `/`
2. Auto-discovers sites from `sites/*/site.json`
3. Mounts each site at `/sites/<id>/`
4. Registers annotation blueprint at `/annotate/`
5. Sets up admin API, session overlay, script injection

## Key Files

| File | Purpose |
|------|---------|
| `app/__init__.py` | App factory, admin API, auto-login, 2FA, script injection |
| `app/db.py` | Database layer — all queries go through here |
| `app/events.py` | Cross-site event bus, 2FA flow |
| `annotation/app.py` | Annotation interface, macro sampling, auth |
| `annotation/macro_locations.py` | Authoritative macro-to-site mapping |
| `annotation/macro_difficulty.py` | Difficulty categories and sampling weights |
| `evaluation/run_annotated.py` | Run agents against annotated tasks |

## Database Rules (CRITICAL)

All data is in SQLite. NEVER load entire tables:

```python
# WRONG
posts = db.query(SITE, "posts")

# RIGHT
posts = db.query(SITE, "posts", where={"user_id": uid}, sort="-created_at", limit=30)
```

See `CLAUDE.md` for the full list of rules.

## Site Structure

Each `sites/<id>/` contains:
- `site.json` — metadata (name, category, tags)
- `schema.py` — SQLite table definitions
- `routes.py` — Flask blueprint with HTML + API routes
- `templates/<id>/` — Jinja2 templates
- `tasks.json` — legacy benchmark tasks (not used for annotation)

## Annotation System

- Accessed at `/annotate/` (login required)
- Macros sampled from `macro_locations.py` weighted by `macro_difficulty.py`
- Tasks start at the target page (`starting_url`), not the site homepage
- Trajectories include HTML snapshots and accessibility trees after each action
- QA macros (extract, compute) have inline answer fields — no need to tag action ranges

## Things to Avoid

- Don't run `build_db.py` — DB was modified post-build
- Don't add `navigate_by_route` to tasks — navigation is implicit
- Don't add export buttons to social/messaging sites
- Don't use `session.clear()` without preserving `annotator_authenticated` and `_disable_2fa`
