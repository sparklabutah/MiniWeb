import json
import pathlib
from flask import Blueprint, render_template
SITE_DIR = pathlib.Path(__file__).resolve().parent
blueprint = Blueprint(
    "university-academic",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
)
@blueprint.route("/")
def index():
    return render_template("university-academic/index.html")
