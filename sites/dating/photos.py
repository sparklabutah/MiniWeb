"""Deterministic synthetic profile photos for the dating site.

Each profile keeps its original portrait avatar (a static SVG) as photo #1 and
gains a small gallery of generated "lifestyle" photos (selfie / outdoors / hobby)
so the Tinder-style card + edit-profile grid have real content. Everything is
rendered on the fly from (user_id, idx) — no image files, fully offline and stable.
"""
from __future__ import annotations

# Gradient palettes, picked per user so a profile's gallery feels cohesive.
_PALETTES = [
    ("#6366f1", "#a855f7"), ("#0ea5e9", "#22d3ee"), ("#f43f5e", "#fb7185"),
    ("#16a34a", "#84cc16"), ("#f59e0b", "#f97316"), ("#8b5cf6", "#ec4899"),
    ("#14b8a6", "#06b6d4"), ("#ef4444", "#f59e0b"), ("#3b82f6", "#6366f1"),
    ("#10b981", "#34d399"), ("#e11d48", "#f43f5e"), ("#7c3aed", "#a78bfa"),
    ("#0891b2", "#3b82f6"), ("#db2777", "#f472b6"), ("#65a30d", "#a3e635"),
]

# Interest -> emoji for the "hobby" photo. Keyed by substring for loose matching.
_HOBBY_ICONS = [
    ("hik", "🥾"), ("trail", "🥾"), ("mountain", "⛰️"), ("travel", "✈️"),
    ("live music", "🎸"), ("music", "🎵"), ("concert", "🎤"), ("guitar", "🎸"),
    ("coffee", "☕"), ("cook", "🍳"), ("food", "🍜"), ("bak", "🧁"),
    ("photo", "📷"), ("read", "📚"), ("book", "📚"), ("writ", "✍️"),
    ("fitness", "🏋️"), ("gym", "🏋️"), ("yoga", "🧘"), ("run", "🏃"),
    ("cycl", "🚴"), ("bike", "🚴"), ("art", "🎨"), ("paint", "🎨"),
    ("gam", "🎮"), ("board game", "🎲"), ("movie", "🎬"), ("film", "🎬"),
    ("dog", "🐶"), ("cat", "🐱"), ("wine", "🍷"), ("beer", "🍺"),
    ("danc", "💃"), ("surf", "🏄"), ("climb", "🧗"), ("beach", "🏖️"),
    ("nature", "🌲"), ("garden", "🪴"), ("ski", "🎿"), ("swim", "🏊"),
    ("tea", "🍵"), ("tech", "💻"), ("code", "💻"), ("dj", "🎧"),
]
_FALLBACK_ICONS = ["🌅", "✨", "🎧", "🍃", "📸", "🌊", "🥂", "🎶"]

_W = 400
_H = 520


def _palette(user_id: int) -> tuple[str, str]:
    return _PALETTES[user_id % len(_PALETTES)]


def _hobby_icon(user_id: int, interests) -> str:
    text = ""
    if isinstance(interests, (list, tuple)):
        text = " ".join(str(i) for i in interests).lower()
    elif isinstance(interests, str):
        text = interests.lower()
    for key, icon in _HOBBY_ICONS:
        if key in text:
            return icon
    return _FALLBACK_ICONS[user_id % len(_FALLBACK_ICONS)]


def _bg(c1: str, c2: str) -> str:
    return (
        f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/>'
        f'</linearGradient></defs>'
        f'<rect width="{_W}" height="{_H}" fill="url(#g)"/>'
    )


def _selfie() -> str:
    white = "rgba(255,255,255,0.30)"
    return (
        f'<circle cx="80" cy="90" r="58" fill="rgba(255,255,255,0.12)"/>'
        f'<circle cx="335" cy="160" r="38" fill="rgba(255,255,255,0.10)"/>'
        f'<circle cx="150" cy="380" r="30" fill="rgba(255,255,255,0.10)"/>'
        f'<circle cx="200" cy="205" r="84" fill="{white}"/>'          # head
        f'<ellipse cx="200" cy="500" rx="150" ry="150" fill="{white}"/>'  # shoulders
    )


def _outdoors(user_id: int) -> str:
    variant = user_id % 3
    sun = '<circle cx="312" cy="110" r="46" fill="rgba(255,255,255,0.38)"/>'
    if variant == 0:  # mountains
        return (
            sun
            + '<polygon points="-20,520 140,290 300,520" fill="rgba(0,0,0,0.18)"/>'
            + '<polygon points="150,520 290,250 440,520" fill="rgba(0,0,0,0.28)"/>'
            + '<polygon points="200,300 230,255 260,300" fill="rgba(255,255,255,0.55)"/>'
            + '<rect y="470" width="400" height="50" fill="rgba(0,0,0,0.15)"/>'
        )
    if variant == 1:  # city skyline
        b = ['<rect y="440" width="400" height="80" fill="rgba(0,0,0,0.20)"/>']
        xs = [(20, 300, 70), (100, 250, 60), (170, 350, 66), (250, 210, 58), (315, 320, 70)]
        for x, top, w in xs:
            b.append(f'<rect x="{x}" y="{top}" width="{w}" height="{520-top}" fill="rgba(0,0,0,0.26)"/>')
            for wy in range(top + 16, 500, 34):
                for wx in range(x + 10, x + w - 8, 22):
                    b.append(f'<rect x="{wx}" y="{wy}" width="8" height="12" fill="rgba(255,255,255,0.35)"/>')
        return sun + "".join(b)
    # variant 2: beach
    return (
        sun
        + '<rect y="300" width="400" height="120" fill="rgba(255,255,255,0.22)"/>'   # sea
        + '<rect y="418" width="400" height="102" fill="rgba(255,255,255,0.42)"/>'   # sand
        + '<path d="M40 418 q30 -70 56 0 Z" fill="rgba(0,0,0,0.22)"/>'               # palm hint
    )


def _hobby(icon: str) -> str:
    return (
        f'<circle cx="200" cy="230" r="120" fill="rgba(255,255,255,0.16)"/>'
        f'<text x="200" y="285" font-size="150" text-anchor="middle">{icon}</text>'
    )


def render_photo(user_id: int, idx: int, name: str = "", interests=None) -> str:
    """Return an SVG string for photo `idx` (1..3) of `user_id`. Deterministic."""
    c1, c2 = _palette(user_id)
    idx = max(1, int(idx))
    if idx == 1:
        body = _selfie()
    elif idx == 2:
        body = _outdoors(user_id)
    else:
        body = _hobby(_hobby_icon(user_id, interests))
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_W}" height="{_H}" '
        f'viewBox="0 0 {_W} {_H}">' + _bg(c1, c2) + body + '</svg>'
    )


# How many generated photos each profile gets (in addition to the portrait).
EXTRA_PHOTOS = 3
