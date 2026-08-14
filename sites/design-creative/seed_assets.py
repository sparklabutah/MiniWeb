"""Seed a real stock asset library for the design-creative (DesignFlow) site.

Populates the `design_creative_assets` base table with a few dozen deterministic
stock assets (icons / shapes / photos / illustrations). Each asset carries an
inline SVG plus a self-contained `data:` URI so it renders on the Assets page,
in the editor side panel, and when placed onto a project canvas — no external
hosts (CSP-safe).

Post-build DB mutation (like the other runtime seed deps). Idempotent: re-running
recreates the table and re-inserts the same rows. Re-run after any DB rebuild.

    ~/.conda/envs/miniweb/bin/python sites/design-creative/seed_assets.py

NEVER run build_db.py — this writes straight to the configured DB.
"""
import os
import pathlib
import sys
from urllib.parse import quote

# --- Point db at the configured database (data/trimmed_miniweb.db via .env) ---
REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))


def _db_path():
    env = os.environ.get("MINIWEB_DB")
    if env:
        return env
    dotenv = REPO / ".env"
    if dotenv.exists():
        for line in dotenv.read_text().splitlines():
            line = line.strip()
            if line.startswith("MINIWEB_DB"):
                _, _, val = line.partition("=")
                return val.strip().strip('"').strip("'")
    return str(REPO / "miniweb.db")


DB_PATH = _db_path()
if not os.path.isabs(DB_PATH):
    DB_PATH = str(REPO / DB_PATH)

from app import db  # noqa: E402

db.init_db(DB_PATH)

SITE = "design-creative"
TABLE = "design_creative_assets"


# ---------------------------------------------------------------------------
# Deterministic SVG builders (viewBox 0 0 100 100)
# ---------------------------------------------------------------------------

def _svg(body, bg=None):
    rect = f'<rect width="100" height="100" fill="{bg}"/>' if bg else ""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        + rect + body + "</svg>"
    )


def _grad(id_, c1, c2, angle="0"):
    return (
        f'<defs><linearGradient id="{id_}" x1="0" y1="0" x2="0" y2="1" '
        f'gradientTransform="rotate({angle} .5 .5)">'
        f'<stop offset="0" stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/>'
        f"</linearGradient></defs>"
    )


# --- icons (flat, single accent color on transparent) ---
IC = "#7c3aed"
ICONS = {
    "Star": f'<path d="M50 8 61 38 93 38 67 58 77 90 50 70 23 90 33 58 7 38 39 38z" fill="{IC}"/>',
    "Heart": f'<path d="M50 86C20 64 12 44 24 30c9-11 22-6 26 4 4-10 17-15 26-4 12 14 4 34-26 56z" fill="#ef4444"/>',
    "Arrow Right": f'<path d="M10 44h56V26l30 24-30 24V56H10z" fill="{IC}"/>',
    "Check Circle": f'<circle cx="50" cy="50" r="42" fill="#10b981"/><path d="M30 52l14 14 26-30" stroke="#fff" stroke-width="8" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
    "Bell": f'<path d="M50 12a16 16 0 00-16 16c0 22-8 28-8 34h48c0-6-8-12-8-34a16 16 0 00-16-16z" fill="#f59e0b"/><circle cx="50" cy="82" r="7" fill="#f59e0b"/>',
    "Camera": f'<rect x="12" y="30" width="76" height="52" rx="8" fill="{IC}"/><rect x="36" y="20" width="28" height="14" rx="4" fill="{IC}"/><circle cx="50" cy="56" r="16" fill="#fff"/><circle cx="50" cy="56" r="9" fill="{IC}"/>',
    "Music Note": f'<path d="M40 20l40-8v50" stroke="#ec4899" stroke-width="7" fill="none"/><circle cx="34" cy="72" r="12" fill="#ec4899"/><circle cx="74" cy="62" r="12" fill="#ec4899"/>',
    "Location Pin": f'<path d="M50 90C30 64 24 50 24 38a26 26 0 0152 0c0 12-6 26-26 52z" fill="#ef4444"/><circle cx="50" cy="38" r="11" fill="#fff"/>',
    "Lightning": f'<path d="M56 6L22 56h22l-8 40 38-54H50z" fill="#f59e0b"/>',
    "Gear": f'<path d="M50 30a20 20 0 100 40 20 20 0 000-40zm0 12a8 8 0 110 16 8 8 0 010-16z" fill="#64748b"/><path d="M50 6l6 12h-12zM50 94l-6-12h12zM6 50l12-6v12zM94 50l-12 6v-12z" fill="#64748b"/>',
    "Sun": f'<circle cx="50" cy="50" r="20" fill="#f59e0b"/><g stroke="#f59e0b" stroke-width="6" stroke-linecap="round"><path d="M50 8v14M50 78v14M8 50h14M78 50h14M20 20l10 10M70 70l10 10M80 20l-10 10M30 70l-10 10"/></g>',
    "Moon": f'<path d="M64 10a40 40 0 100 80 32 32 0 010-80z" fill="#6366f1"/>',
}

# --- shapes (solid fill, on transparent) ---
SH = "#0ea5e9"
SHAPES = {
    "Square": f'<rect x="18" y="18" width="64" height="64" fill="{SH}"/>',
    "Circle": f'<circle cx="50" cy="50" r="34" fill="#ec4899"/>',
    "Triangle": f'<path d="M50 14 88 84 12 84z" fill="#f59e0b"/>',
    "Pentagon": f'<path d="M50 12 88 40 74 84 26 84 12 40z" fill="#8b5cf6"/>',
    "Hexagon": f'<path d="M30 18 70 18 90 50 70 82 30 82 10 50z" fill="#10b981"/>',
    "Diamond": f'<path d="M50 10 86 50 50 90 14 50z" fill="#ef4444"/>',
    "Rounded Rect": f'<rect x="14" y="26" width="72" height="48" rx="14" fill="#0ea5e9"/>',
    "Ellipse": f'<ellipse cx="50" cy="50" rx="40" ry="26" fill="#f43f5e"/>',
}


def _photo(id_, c1, c2, extra=""):
    return _svg(_grad(id_, c1, c2, "20") + f'<rect width="100" height="100" fill="url(#{id_})"/>' + extra)


PHOTOS = {
    "Mountain Sunrise": _photo("p1", "#fdba74", "#7c3aed", '<path d="M0 100 30 55 50 75 70 40 100 100z" fill="#1e293b" opacity=".85"/><circle cx="76" cy="30" r="10" fill="#fff" opacity=".9"/>'),
    "Ocean Waves": _photo("p2", "#38bdf8", "#0369a1", '<path d="M0 70q25-12 50 0t50 0v30H0z" fill="#0c4a6e" opacity=".6"/>'),
    "Sunset Beach": _photo("p3", "#fb7185", "#f59e0b", '<circle cx="50" cy="60" r="16" fill="#fff" opacity=".85"/><rect y="76" width="100" height="24" fill="#7c2d12" opacity=".6"/>'),
    "Forest Path": _photo("p4", "#4ade80", "#14532d", '<rect x="44" y="40" width="12" height="60" fill="#3f2d1a" opacity=".7"/>'),
    "City Skyline": _photo("p5", "#a78bfa", "#1e293b", '<g fill="#0f172a" opacity=".8"><rect x="14" y="55" width="12" height="45"/><rect x="32" y="40" width="14" height="60"/><rect x="52" y="60" width="10" height="40"/><rect x="68" y="48" width="16" height="52"/></g>'),
    "Desert Dunes": _photo("p6", "#fcd34d", "#b45309", '<path d="M0 80q30-20 60 0t40 5V100H0z" fill="#92400e" opacity=".5"/>'),
}


def _illus(id_, c1, c2, extra=""):
    return _svg(_grad(id_, c1, c2, "35") + f'<rect width="100" height="100" fill="url(#{id_})"/>' + extra)


ILLUS = {
    "Abstract Waves": _illus("i1", "#8b5cf6", "#06b6d4", '<path d="M0 50q25-25 50 0t50 0" stroke="#fff" stroke-width="5" fill="none" opacity=".6"/><path d="M0 68q25-25 50 0t50 0" stroke="#fff" stroke-width="5" fill="none" opacity=".4"/>'),
    "Organic Blob": _illus("i2", "#f472b6", "#f59e0b", '<path d="M50 20c18 0 32 12 30 32s-16 28-34 26-28-18-24-36 10-22 28-22z" fill="#fff" opacity=".55"/>'),
    "Confetti": _illus("i3", "#22d3ee", "#a855f7", '<g opacity=".85"><rect x="20" y="24" width="8" height="8" fill="#fde047" transform="rotate(20 24 28)"/><rect x="66" y="30" width="8" height="8" fill="#f87171" transform="rotate(-15 70 34)"/><circle cx="40" cy="60" r="5" fill="#4ade80"/><rect x="72" y="64" width="8" height="8" fill="#fff" transform="rotate(30 76 68)"/></g>'),
    "Gradient Mesh": _illus("i4", "#6366f1", "#ec4899", '<circle cx="30" cy="34" r="22" fill="#fff" opacity=".25"/><circle cx="70" cy="66" r="26" fill="#fff" opacity=".2"/>'),
    "Geometric Lines": _illus("i5", "#0ea5e9", "#14b8a6", '<g stroke="#fff" stroke-width="3" opacity=".55"><path d="M10 90 90 10M30 90 90 30M10 70 70 10"/></g>'),
    "Floral Accent": _illus("i6", "#fb7185", "#c084fc", '<g fill="#fff" opacity=".6"><circle cx="50" cy="38" r="8"/><circle cx="38" cy="50" r="8"/><circle cx="62" cy="50" r="8"/><circle cx="50" cy="62" r="8"/><circle cx="50" cy="50" r="7" fill="#fde047" opacity=".9"/></g>'),
}


def _data_uri(svg):
    return "data:image/svg+xml," + quote(svg, safe="")


TAGS = {
    "icon": ["icon", "flat", "ui"],
    "shape": ["shape", "vector", "geometric"],
    "photo": ["photo", "background", "stock"],
    "illustration": ["illustration", "abstract", "graphic"],
}

CATEGORY = {
    "icon": "Icons",
    "shape": "Shapes",
    "photo": "Photos",
    "illustration": "Illustrations",
}


def build_assets():
    assets = []
    aid = 1

    def add(name, atype, svg):
        nonlocal aid
        tags = TAGS[atype] + [name.split()[0].lower()]
        assets.append({
            "id": aid,
            "name": name,
            "type": atype,
            "category": CATEGORY[atype],
            "tags": tags,
            "svg": svg,
            "src": _data_uri(svg),
            "width": 200,
            "height": 200,
        })
        aid += 1

    for name, body in ICONS.items():
        add(name, "icon", _svg(body))
    for name, body in SHAPES.items():
        add(name, "shape", _svg(body))
    for name, svg in PHOTOS.items():
        add(name, "photo", svg)
    for name, svg in ILLUS.items():
        add(name, "illustration", svg)
    return assets


def main():
    conn = db.get_conn()
    columns = [
        ("id", "INTEGER PRIMARY KEY"),
        ("name", "TEXT NOT NULL DEFAULT ''"),
        ("type", "TEXT NOT NULL DEFAULT ''"),
        ("category", "TEXT NOT NULL DEFAULT ''"),
        ("tags", "TEXT NOT NULL DEFAULT ''"),
        ("svg", "TEXT NOT NULL DEFAULT ''"),
        ("src", "TEXT NOT NULL DEFAULT ''"),
        ("width", "INTEGER NOT NULL DEFAULT 200"),
        ("height", "INTEGER NOT NULL DEFAULT 200"),
    ]
    db.create_site_table(conn, TABLE, columns, indexes=["type", "category"])
    # Idempotent re-seed: clear our own seed table only, then re-insert.
    conn.execute(f"DELETE FROM [{TABLE}]")
    assets = build_assets()
    db.bulk_insert(conn, TABLE, columns, assets)
    db.register_table(SITE, "assets", TABLE, "id", conn=conn)
    conn.commit()

    n = conn.execute(f"SELECT COUNT(*) FROM [{TABLE}]").fetchone()[0]
    by_type = conn.execute(
        f"SELECT type, COUNT(*) FROM [{TABLE}] GROUP BY type ORDER BY type"
    ).fetchall()
    print(f"DB: {DB_PATH}")
    print(f"Seeded {n} assets into {TABLE}")
    for t, c in by_type:
        print(f"  {t}: {c}")
    print("Registered (design-creative, assets) ->", db.get_table_name(SITE, "assets"))


if __name__ == "__main__":
    main()
