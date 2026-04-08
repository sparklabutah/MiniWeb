import importlib
import json
import pathlib

from flask import Flask

SITES_DIR = pathlib.Path(__file__).resolve().parent.parent / "sites"


def discover_sites():
    """Scan sites/*/site.json and return a list of site metadata dicts."""
    sites = []
    for site_json in sorted(SITES_DIR.glob("*/site.json")):
        if site_json.parent.name.startswith("_"):
            continue
        meta = json.loads(site_json.read_text())
        meta["path"] = f"/sites/{meta['id']}/"
        sites.append(meta)
    return sites


def register_site_blueprints(app: Flask):
    """Import each site's routes.py and mount its blueprint."""
    for site_json in sorted(SITES_DIR.glob("*/site.json")):
        if site_json.parent.name.startswith("_"):
            continue

        meta = json.loads(site_json.read_text())
        site_id = meta["id"]
        site_dir = site_json.parent

        module_path = f"sites.{site_dir.name}.routes"
        module = importlib.import_module(module_path)
        bp = module.blueprint

        app.register_blueprint(bp, url_prefix=f"/sites/{site_id}")


def create_app():
    app = Flask(
        __name__,
        static_folder="static",
        static_url_path="/static",
    )

    from app.portal.routes import portal_bp
    app.register_blueprint(portal_bp)

    register_site_blueprints(app)

    return app
