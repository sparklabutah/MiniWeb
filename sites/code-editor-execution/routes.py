import json
import pathlib
from flask import Blueprint, render_template
SITE_DIR = pathlib.Path(__file__).resolve().parent
blueprint = Blueprint(
    "code-editor-execution",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
)
@blueprint.route("/")
def index():
    return render_template("code-editor-execution/index.html")
