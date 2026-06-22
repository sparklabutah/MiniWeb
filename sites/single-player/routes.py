import json
import pathlib
from flask import Blueprint, render_template
SITE_DIR = pathlib.Path(__file__).resolve().parent
blueprint = Blueprint(
    "single-player",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
)
@blueprint.route("/")
def index():
    return render_template("single-player/index.html")
