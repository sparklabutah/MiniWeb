# MiniWeb

A lightweight, self-contained web platform for agentic benchmarking. One Flask process serves a search portal and any number of mini-sites, each with its own pages and JSON data.

## Quick Start

### Option A: Python (no Docker)

```bash
pip install -r requirements.txt
python run.py
```

Open [http://localhost:8080](http://localhost:8080).

### Option B: Docker

```bash
docker build -t miniweb .
docker run -p 8080:8080 miniweb
```

## Project Structure

```
MiniWeb/
├── run.py                  # Entry point
├── requirements.txt        # Flask
├── Dockerfile              # Optional container
├── app/
│   ├── __init__.py         # Auto-discovers sites and mounts blueprints
│   ├── portal/             # Search homepage
│   └── static/             # Shared CSS
└── sites/
    ├── bookstore/          # Example site (fully functional)
    └── _template/          # Copy to create a new site
```

## How It Works

At startup, `app/__init__.py` scans `sites/*/site.json` and auto-registers each site as a Flask Blueprint mounted at `/sites/<id>/`. The portal at `/` reads all `site.json` files to build a searchable index.

No config files to edit. No routing to update. Just drop a folder and restart.

## Adding a New Site

### Using the helper script

```bash
./scripts/add_site.sh my-site "My Site Name" "A short description"
```

This copies the template, renames files, and updates `site.json` and `routes.py` for you.

### Manually

1. Copy `sites/_template/` to `sites/my-site/`
2. Rename `sites/my-site/templates/_template/` to `sites/my-site/templates/my-site/`
3. Edit `sites/my-site/site.json`:
   ```json
   {
       "id": "my-site",
       "name": "My Site Name",
       "description": "What this site does",
       "tags": ["tag1", "tag2"]
   }
   ```
4. Update the blueprint name and template references in `sites/my-site/routes.py`
5. Add an `__init__.py` to the site directory
6. Build your pages and data
7. Restart: `python run.py`

## Site Anatomy

Each site is a directory under `sites/` with:

| File | Purpose |
|---|---|
| `site.json` | Metadata (id, name, description, tags) |
| `routes.py` | Flask Blueprint with routes |
| `__init__.py` | Empty, makes the directory a Python package |
| `templates/<id>/` | Jinja2 HTML templates |
| `data/` | JSON data files |

## API

### Portal

- `GET /` -- search homepage
- `GET /api/sites` -- list all sites (optional `?q=` filter)

### Per-site

Each site defines its own routes under `/sites/<id>/`. For example, the bookstore provides:

- `GET /sites/bookstore/` -- book listing
- `GET /sites/bookstore/book/<id>` -- book detail
- `GET /sites/bookstore/api/books` -- JSON list (optional `?q=` filter)
- `GET /sites/bookstore/api/books/<id>` -- JSON detail
