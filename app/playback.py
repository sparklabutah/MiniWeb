"""Deterministic on-screen info streams for the shared mini-player.

Every [data-mini-player] video gets a timeline of "what's on screen right now"
segments (lower-third overlay rendered by player.js). Most segments are generic
scene lines, but a few short spans carry FACTS — a promo code, a reference
number, an attendance figure, a contact address — that are visible ONLY while
the playhead is inside that span. Tasks built on this force the agent to scrub
the seek bar to locate the span (search_by_playback macro).

Fully deterministic: the timeline is a pure function of (key, duration), where
the key is the page path + video title. Annotators and verifiers can GET the
same endpoint to know ground truth; parallel sessions see identical streams.
"""
import random
import zlib

from flask import Blueprint, jsonify, request

playback_bp = Blueprint("playback", __name__)

_FILLER = [
    "Wide shot of the presenter on stage",
    "Slide: agenda overview",
    "Close-up: product demo on screen",
    "Audience view, ambient music",
    "Presenter walks through the main charts",
    "Screen share: dashboard walkthrough",
    "B-roll: office exterior",
    "Panel discussion continues",
    "Slide: key takeaways",
    "Q&A — audience microphone",
    "Whiteboard sketch of the architecture",
    "Split screen: interviewer and guest",
    "Timelapse footage plays",
    "Live coding session on screen",
    "Slide: quarterly numbers",
    "Speaker anecdote, light laughter",
    "Demo continues at normal speed",
    "Graph animates on screen",
    "Closing remarks begin",
    "Credits and thank-you slide",
]

# Audio flavor: same segment structure/values, narration-style wording.
_FILLER_AUDIO = [
    "Theme music plays",
    "Host intro continues",
    "Interview segment",
    "Ad read: sponsor message",
    "Host tells a listener story",
    "Music bed under discussion",
    "Caller question on air",
    "Co-host banter",
    "Deep-dive into the main topic",
    "Short musical interlude",
    "Host recaps the last episode",
    "Sound clip plays",
    "Listener mail segment",
    "Host sets up the next guest",
    "Discussion gets technical",
    "Quick news roundup",
    "Host shares a recommendation",
    "Outro music begins",
    "Closing thoughts",
    "Credits and thank-yous",
]

_FIRST = ["Maya", "Daniel", "Aisha", "Tom", "Ingrid", "Rafael", "Yuki", "Omar",
          "Petra", "Liam", "Sofia", "Chen"]
_LAST = ["Torres", "Novak", "Okoye", "Lindqvist", "Ferreira", "Tanaka",
         "Haddad", "Kowalski", "Brennan", "Vargas"]
_DOMAINS = ["brightpeak.io", "northwind-events.com", "cascadia-media.org",
            "summitline.co", "harborlight.tv"]


_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

# Promo prefix -> discount fraction. Codes are checksum-signed, so any site can
# verify a code it has never seen (validate_promo) with no shared registry —
# the e-commerce cart redeems codes found by scrubbing any video on any site.
PROMO_DISCOUNTS = {"SAVE": 0.10, "STREAM": 0.12, "VIP": 0.15, "EARLY": 0.20}


def _checksum_char(base):
    return _ALPHABET[zlib.crc32(("miniweb-promo|" + base).encode("utf-8")) % len(_ALPHABET)]


def make_promo_code(rng):
    """PREFIX-XXXXXXC — six random chars plus a checksum character."""
    prefix = rng.choice(list(PROMO_DISCOUNTS))
    body = "".join(rng.choice(_ALPHABET) for _ in range(6))
    base = f"{prefix}-{body}"
    return base + _checksum_char(base)


def validate_promo(code):
    """Discount fraction (e.g. 0.10) for a playback promo code, else None."""
    code = (code or "").strip().upper()
    prefix, sep, rest = code.partition("-")
    if not sep or prefix not in PROMO_DISCOUNTS or len(rest) != 7:
        return None
    if _checksum_char(code[:-1]) != code[-1]:
        return None
    return PROMO_DISCOUNTS[prefix]


def _make_facts(rng, flavor="video"):
    """Candidate fact generators — each returns (label, stream text, value).

    The flavor changes ONLY the wording; value generation and rng consumption
    are identical, so the same key yields the same values in either flavor.
    """
    promo = make_promo_code(rng)
    ref = f"{rng.randint(10000, 99999)}"
    email = f"{rng.choice(['events', 'support', 'press', 'booking'])}@{rng.choice(_DOMAINS)}"
    count = f"{rng.randint(1200, 48000):,}"
    name = f"{rng.choice(_FIRST)} {rng.choice(_LAST)}"
    amount = f"${rng.randint(90, 4900):,}"
    if flavor == "audio":
        pool = [
            ("promo code", f"Host reads out promo code {promo} — redeem at the online store", promo),
            ("reference number", f"Host gives reference number #{ref}", ref),
            ("contact email", f"Contact mentioned on air: {email}", email),
            ("live viewer count", f"Host: {count} listening live right now", count),
            ("guest name", f"Guest introduced: {name}", name),
            ("prize amount", f"Prize announced: {amount}", amount),
        ]
    else:
        pool = [
            ("promo code", f"On screen: promo code {promo} — redeem at the online store", promo),
            ("reference number", f"Overlay: reference #{ref}", ref),
            ("contact email", f"Lower third: contact {email}", email),
            ("live viewer count", f"Ticker: {count} watching live", count),
            ("guest name", f"Name card: {name}", name),
            ("prize amount", f"Banner: prize pool {amount}", amount),
        ]
    rng.shuffle(pool)
    return pool


def generate_timeline(key, duration, flavor="video"):
    """[{start, end, text, kind, (label, value)}] covering 0..duration."""
    duration = max(30, min(int(duration or 0), 36000))
    rng = random.Random(zlib.crc32(("miniweb-playback|" + key).encode("utf-8")))

    n_facts = 2 if duration < 180 else 3
    span = max(4, min(int(duration * 0.06), 25))     # facts visible only briefly
    # Fact spans: distinct slots away from 0:00 so nothing is visible pre-scrub.
    slots = []
    for _ in range(200):
        if len(slots) >= n_facts:
            break
        s = rng.randint(int(duration * 0.08), max(int(duration * 0.92) - span, int(duration * 0.08) + 1))
        if all(abs(s - o) > span * 3 for o in slots):
            slots.append(s)
    slots.sort()

    facts = _make_facts(rng, flavor)[:len(slots)]
    segments = []
    cursor = 0
    fi = 0
    filler = (_FILLER_AUDIO if flavor == "audio" else _FILLER)[:]
    rng.shuffle(filler)
    fill_i = 0
    while cursor < duration:
        if fi < len(slots) and cursor >= slots[fi] - 1:
            label, text, value = facts[fi]
            end = min(slots[fi] + span, duration)
            segments.append({"start": slots[fi], "end": end, "text": text,
                             "kind": "fact", "label": label, "value": value})
            cursor = end
            fi += 1
            continue
        nxt = slots[fi] if fi < len(slots) else duration
        end = min(cursor + rng.randint(8, 22), nxt, duration)
        segments.append({"start": cursor, "end": end,
                         "text": filler[fill_i % len(filler)], "kind": "scene"})
        fill_i += 1
        cursor = end
    return {"duration": duration, "segments": segments}


@playback_bp.route("/timeline")
def api_timeline():
    key = (request.args.get("key") or "").strip()
    duration = request.args.get("duration", type=float) or 0
    flavor = "audio" if request.args.get("flavor") == "audio" else "video"
    if not key:
        return jsonify({"error": "key required"}), 400
    return jsonify(generate_timeline(key, duration, flavor))


def register_playback_routes(app):
    app.register_blueprint(playback_bp, url_prefix="/_player")
