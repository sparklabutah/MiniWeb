import json
import pathlib

from flask import Blueprint, abort, jsonify, render_template, request

SITE_DIR = pathlib.Path(__file__).resolve().parent
DATA_FILE = SITE_DIR / "data" / "books.json"

blueprint = Blueprint(
    "bookstore",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)


def _load_books():
    return json.loads(DATA_FILE.read_text())


@blueprint.route("/")
def index():
    return render_template("bookstore/index.html", books=_load_books())


@blueprint.route("/book/<int:book_id>")
def book_detail(book_id):
    books = _load_books()
    book = next((b for b in books if b["id"] == book_id), None)
    if book is None:
        abort(404)
    return render_template("bookstore/book.html", book=book)


@blueprint.route("/api/books")
def api_books():
    q = request.args.get("q", "").lower().strip()
    books = _load_books()
    if q:
        books = [
            b for b in books
            if q in b["title"].lower()
            or q in b["author"].lower()
            or q in b.get("genre", "").lower()
        ]
    return jsonify(books)


@blueprint.route("/api/books/<int:book_id>")
def api_book(book_id):
    books = _load_books()
    book = next((b for b in books if b["id"] == book_id), None)
    if book is None:
        abort(404)
    return jsonify(book)
