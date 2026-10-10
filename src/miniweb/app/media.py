"""Serve the sites' external media from a local copy, so pages render without the internet.

Site data links to images on other hosts (wikiHow step images, phone photos, product images, images inside posts) and
the map loads basemap tiles from a CDN. scripts/fetch_site_media.py downloads them into MINIWEB_MEDIA_DIR (default
data/media: <host>/<path> plus manifest.jsonl); scripts/restore_site_db.py unpacks the release's copy there. With a copy
present, every /sites/* page and JSON response has its downloaded links rewritten to /media/<host>/<path>, and the map's
tile URL to /media/tiles/...; anything not in the copy redirects to its original address. Without a copy, nothing
changes.
"""
import json
import re
from pathlib import Path

from flask import Blueprint, abort, redirect, request, send_from_directory

EXT = r"(?:jpe?g|png|gif|webp|svg|bmp|ico|avif|mp4|webm|mov|m4v|mp3|m4a|ogg|oga|opus|wav|flac)"
URL_RX = re.compile(r"https?://[A-Za-z0-9.-]+/[^\"'\s<>)\]]*?\." + EXT + r"(?=[\"'\s<>)\],?#]|$)", re.I)
TILE_HOST = "cartodb-basemaps.global.ssl.fastly.net"
TILE_RX = re.compile(r"https://cartodb-basemaps-(?:\{s\}|[a-d])\.global\.ssl\.fastly\.net/light_nolabels/")
TILE_CDN = "https://cartodb-basemaps-a.global.ssl.fastly.net/light_nolabels/"


class MediaCache:
    def __init__(self, root):
        self.root = Path(root)
        self.local, self.original = {}, {}
        for line in open(self.root / "manifest.jsonl"):
            r = json.loads(line)
            if r.get("path"):
                self.local[r["url"]] = r["path"]
                self.original[r["path"]] = r["url"]

    def rewrite(self, text):
        out = URL_RX.sub(lambda m: "/media/" + self.local[m.group(0)] if m.group(0) in self.local else m.group(0), text)
        return TILE_RX.sub("/media/tiles/light_nolabels/", out)


def init_media(app, root):
    root = Path(root)
    if not (root / "manifest.jsonl").is_file():
        return None
    cache = MediaCache(root)
    bp = Blueprint("site_media", __name__)

    @bp.route("/media/tiles/light_nolabels/<int:z>/<int:x>/<int:y>.png")
    def _tile(z, x, y):
        rel = f"{TILE_HOST}/light_nolabels/{z}/{x}/{y}.png"
        if (root / rel).is_file():
            return send_from_directory(root, rel, max_age=86400)
        return redirect(f"{TILE_CDN}{z}/{x}/{y}.png")

    @bp.route("/media/<path:rel>")
    def _media(rel):
        if (root / rel).is_file():
            return send_from_directory(root, rel, max_age=86400)
        if rel in cache.original:
            return redirect(cache.original[rel])
        abort(404)

    app.register_blueprint(bp)

    @app.after_request
    def _rewrite_media_links(response):
        ctype = response.content_type or ""
        if (request.path.startswith("/sites/") and response.status_code == 200 and not response.direct_passthrough
                and ("text/html" in ctype or "application/json" in ctype)):
            text = response.get_data(as_text=True)
            if "http" in text:
                new = cache.rewrite(text)
                if new != text:
                    response.set_data(new)
        return response

    app.config["MEDIA_CACHE"] = cache
    return cache
