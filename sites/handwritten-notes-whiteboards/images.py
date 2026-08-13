"""Deterministic placeholder image generation + basic editing for NoteCanvas.

Real user images are not stored in the repo, so image references would render
broken. This module produces *deterministic* placeholder PNG/JPG files (a
soft-colored box with a centered label + a small note icon) and serves them
from the same location the app already exposes for generated media:

    data/static/generated/<filename>   ->   /static/generated/<filename>
    (served by app/__init__.py :: _data_static_files)

It also implements the server-side transforms behind the `edit_by_image`
macro (crop / resize / contrast / vibrance) using PIL. No external fetches --
every pixel is generated locally and deterministically from a seed string.
"""
import colorsys
import hashlib
import json
import os
import pathlib

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

SITE = "handwritten-notes-whiteboards"
SITE_SLUG = SITE.replace("-", "_")

# Ops the editor understands. Kept here so routes + verifiers share one source.
EDIT_OPS = ("crop", "resize", "contrast", "vibrance")


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def _data_static_dir() -> pathlib.Path:
    """Mirror the resolution used by app/__init__.py for /static/<sub>/..."""
    base = os.environ.get(
        "MINIWEB_DATA_STATIC",
        str(pathlib.Path(__file__).resolve().parent.parent.parent
            / "data" / "static"),
    )
    return pathlib.Path(base)


def generated_dir() -> pathlib.Path:
    d = _data_static_dir() / "generated"
    d.mkdir(parents=True, exist_ok=True)
    return d


def served_url(filename: str) -> str:
    return f"/static/generated/{filename}"


# ---------------------------------------------------------------------------
# Deterministic colors / fonts
# ---------------------------------------------------------------------------

def _seed_int(seed: str) -> int:
    return int(hashlib.md5(seed.encode("utf-8")).hexdigest(), 16)


def _soft_color(seed: str):
    """A soft pastel RGB derived deterministically from the seed."""
    n = _seed_int(seed)
    hue = (n % 360) / 360.0
    sat = 0.35 + ((n >> 9) % 20) / 100.0     # 0.35 - 0.55
    light = 0.78 + ((n >> 17) % 12) / 100.0  # 0.78 - 0.90
    r, g, b = colorsys.hls_to_rgb(hue, light, sat)
    return (int(r * 255), int(g * 255), int(b * 255))


def _accent_color(seed: str):
    n = _seed_int(seed)
    hue = (n % 360) / 360.0
    r, g, b = colorsys.hls_to_rgb(hue, 0.38, 0.55)
    return (int(r * 255), int(g * 255), int(b * 255))


def _load_font(size: int):
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
    except Exception:
        try:
            return ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
        except Exception:
            return ImageFont.load_default()


def _text_size(draw, text, font):
    try:
        l, t, r, b = draw.textbbox((0, 0), text, font=font)
        return r - l, b - t
    except Exception:
        return draw.textsize(text, font=font)


# ---------------------------------------------------------------------------
# Placeholder rendering
# ---------------------------------------------------------------------------

def make_placeholder(label: str, seed: str = None, size=(480, 320)) -> Image.Image:
    """Return a deterministic placeholder image with a centered label."""
    seed = seed or label
    w, h = size
    bg = _soft_color(seed)
    accent = _accent_color(seed)
    img = Image.new("RGB", (w, h), bg)
    draw = ImageDraw.Draw(img)

    # Inner border for a "framed" look.
    margin = max(4, min(w, h) // 24)
    draw.rectangle([margin, margin, w - margin - 1, h - margin - 1],
                   outline=accent, width=max(2, min(w, h) // 120))

    # Small centered "image / note" glyph (mountain + sun), scaled to size.
    gw = w // 5
    gh = gw * 3 // 4
    gx = (w - gw) // 2
    gy = h // 2 - gh
    draw.ellipse([gx + gw * 0.62, gy + gh * 0.12,
                  gx + gw * 0.62 + gw * 0.16, gy + gh * 0.12 + gw * 0.16],
                 fill=accent)
    draw.polygon([(gx, gy + gh), (gx + gw * 0.38, gy + gh * 0.42),
                  (gx + gw * 0.62, gy + gh * 0.72), (gx + gw, gy + gh)],
                 fill=accent)

    # Label text, centered below the glyph, truncated to fit.
    text = (label or "Image").strip()
    if len(text) > 42:
        text = text[:39] + "..."
    font = _load_font(max(14, w // 22))
    tw, th = _text_size(draw, text, font)
    if tw > w - 2 * margin:  # shrink font until it fits
        font = _load_font(max(10, int((w - 2 * margin) / max(1, len(text)) * 1.6)))
        tw, th = _text_size(draw, text, font)
    tx = (w - tw) // 2
    ty = h // 2 + gh // 3
    draw.text((tx, ty), text, fill=accent, font=font)

    # Tiny "placeholder" caption.
    cap_font = _load_font(max(9, w // 40))
    cap = "placeholder"
    cw, ch = _text_size(draw, cap, cap_font)
    draw.text(((w - cw) // 2, h - margin - ch - 2), cap,
              fill=accent, font=cap_font)
    return img


def note_image_filename(note_id) -> str:
    return f"note_{SITE_SLUG}_{note_id}.png"


def ensure_note_placeholder(note_id, label: str) -> str:
    """Create (idempotently) the base placeholder file for a note's image and
    return its served URL. Overwrites only its own deterministic file."""
    fn = note_image_filename(note_id)
    path = generated_dir() / fn
    img = make_placeholder(label or f"Note {note_id}", seed=fn)
    img.save(path, "PNG")
    return served_url(fn)


def save_upload_placeholder(note_id, original_filename: str) -> str:
    """Store a newly-uploaded image as a generated placeholder (we never keep
    the raw uploaded bytes). Returns the served URL."""
    label = original_filename or f"Note {note_id}"
    return ensure_note_placeholder(note_id, label)


def local_path_for_url(url: str) -> pathlib.Path | None:
    """Map a /static/generated/<fn> URL back to an on-disk path."""
    if not url:
        return None
    fn = url.rsplit("/", 1)[-1]
    return generated_dir() / fn


# ---------------------------------------------------------------------------
# Editing transforms (edit_by_image)
# ---------------------------------------------------------------------------

def _clampi(v, lo, hi):
    try:
        v = int(round(float(v)))
    except (TypeError, ValueError):
        v = lo
    return max(lo, min(hi, v))


def _clampf(v, lo, hi, default):
    try:
        v = float(v)
    except (TypeError, ValueError):
        v = default
    return max(lo, min(hi, v))


def apply_op(img: Image.Image, op: str, params: dict) -> Image.Image:
    """Apply a single edit op to a PIL image and return the new image."""
    op = (op or "").lower()
    if op == "crop":
        W, H = img.size
        x = _clampi(params.get("x", 0), 0, W - 1)
        y = _clampi(params.get("y", 0), 0, H - 1)
        w = _clampi(params.get("w", W - x), 1, W - x)
        h = _clampi(params.get("h", H - y), 1, H - y)
        return img.crop((x, y, x + w, y + h))
    if op == "resize":
        W, H = img.size
        w = _clampi(params.get("w", W), 1, 4000)
        h = _clampi(params.get("h", H), 1, 4000)
        return img.resize((w, h))
    if op == "contrast":
        value = _clampf(params.get("value", 1.0), 0.0, 3.0, 1.0)
        return ImageEnhance.Contrast(img).enhance(value)
    if op == "vibrance":
        # Approximate vibrance via color (saturation) enhancement.
        value = _clampf(params.get("value", 1.0), 0.0, 3.0, 1.0)
        return ImageEnhance.Color(img).enhance(value)
    raise ValueError(f"unknown op: {op}")


def apply_edit_to_note(note: dict, op: str, params: dict) -> str:
    """Apply an edit to the note's current image, writing the result to a new
    deterministic file (base placeholder is never destroyed). Returns the new
    served URL. Caller is responsible for persisting note['image'] to the
    session overlay via db.save_item."""
    # Resolve the source image; generate the base placeholder if missing.
    src_url = note.get("image")
    src_path = local_path_for_url(src_url) if src_url else None
    if not src_path or not src_path.is_file():
        src_url = ensure_note_placeholder(
            note["id"], note.get("title") or f"Note {note['id']}")
        src_path = local_path_for_url(src_url)

    with Image.open(src_path) as im:
        im = im.convert("RGB")
        out = apply_op(im, op, params)

    # Deterministic output name derived from source + op + params so repeated
    # sessions / edits do not collide and remain reproducible.
    digest = hashlib.md5(
        (str(src_url) + op + json.dumps(params, sort_keys=True)).encode()
    ).hexdigest()[:10]
    fn = f"note_{SITE_SLUG}_{note['id']}_e{digest}.png"
    out.save(generated_dir() / fn, "PNG")
    return served_url(fn)


# ---------------------------------------------------------------------------
# Seeding referenced images (avatars) -- fills broken references with
# deterministic placeholders without touching any real images already present.
# ---------------------------------------------------------------------------

def seed_referenced_placeholders(avatar_urls) -> dict:
    """Given an iterable of referenced avatar URLs, generate a JPG placeholder
    for any that do not yet exist on disk. Returns {"created": [...],
    "existing": [...]}."""
    created, existing = [], []
    for url in avatar_urls:
        if not url:
            continue
        fn = url.rsplit("/", 1)[-1]
        path = generated_dir() / fn
        if path.is_file():
            existing.append(fn)
            continue
        # Label from the trailing token, e.g. users_7 -> "User 7"
        stem = fn.rsplit(".", 1)[0]
        label = stem.split("_users_")[-1]
        label = f"User {label}" if label.isdigit() else stem
        img = make_placeholder(label, seed=fn, size=(256, 256))
        img.save(path, "JPEG", quality=85)
        created.append(fn)
    return {"created": created, "existing": existing}
