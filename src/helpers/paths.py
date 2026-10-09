"""The repository root (src/helpers/paths.py -> two levels up), for code that reads data/, models/, .env or the
database: since the src/ layout (2026-10-08) a module's own location no longer says where the repository is."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SITES_DIR = REPO_ROOT / "src" / "miniweb" / "sites"          # the 65 sites (<site>/site.json, routes.py, doc/)
