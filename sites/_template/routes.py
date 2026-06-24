import json
import pathlib

from flask import Blueprint, render_template

SITE_DIR = pathlib.Path(__file__).resolve().parent

# IMPORTANT: Change the blueprint name to match your site id from site.json.
# Also update the template_folder subdirectory and template references below.
blueprint = Blueprint(
    "_template",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)


@blueprint.route("/")
def index():
    return render_template("_template/index.html")
