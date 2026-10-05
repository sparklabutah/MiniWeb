"""search_by_playback — find information that is only on screen while the playhead is inside a
short span of a video, by scrubbing the seek bar.

Every shared mini-player ([data-mini-player], app/static/player.js) overlays a deterministic
"what is on screen now" stream (app/playback.py): mostly scene lines, plus 2–3 FACTS (a promo
code, a reference number, a contact email, a name, an amount) visible only for a few seconds.
The timeline is a pure function of (key, duration), so the sampler computes it here: each fact
is an argument, its value the answer. The check is an `answer` check whose evidence is the
fact's overlay text — it is on screen only when the playhead is inside the span, so the
trajectory must scrub to it. The executor scrubs in steps shorter than the span (a search,
not a jump to a known position) until the overlay shows the fact, then answers.
"""
from __future__ import annotations

import random

from datagen import browser as B
from datagen.kinds import register
from datagen.kinds.base import Kind


SCREEN, PAUSE = "[data-mini-player] .mp-screen", "[data-mini-player] .mp-pp"


def timeline(ctrl):
    from app.playback import generate_timeline
    return generate_timeline(ctrl["key"], round(ctrl["duration"]), "video")


def scrub_plan(start, end, duration, seed):
    """Seek-bar fractions a person scanning the video would click: from an early point forward
    in steps shorter than the fact's span, ending inside the span."""
    rng = random.Random(seed)
    step = max(0.8 * (end - start), 1.0) / duration
    target = (start + 0.35 * (end - start)) / duration
    f = rng.uniform(0.03, min(0.25, max(0.04, target - 2 * step)))
    if f >= target:
        return [round(target, 4)]
    n = int((target - f) / step) + 1
    if n > 10:                                 # a long way off: a few coarse jumps first, then fine steps
        f = target - 8 * step
    out, x = [], f
    while x < target - 1e-9 and len(out) < 12:
        out.append(round(x, 4))
        x += step
    out.append(round(target, 4))
    return out


@register
class PlaybackKind(Kind):
    name = "player"
    macros = {"search_by_playback": "player"}
    needs_probe = False
    example = '''# example: start the video (its controls appear), pause it, then scan through it with the seek bar
# until the overlay shows the fact, then reply
screen = dom.one(css=task["screen_css"])
if not screen.in_viewport:
    screen = act.scroll_into_view(screen)
act.click(screen)
act.click(dom.one(css=task["pause_css"]))
seek = dom.one(css=task["seek_css"])
if not seek.in_viewport:
    seek = act.scroll_into_view(seek)
for frac in task["scrub"]:
    act.click(seek, at=(frac, 0.5))
    shown = dom.find(css=task["overlay_css"], limit=1)       # hidden until the playhead moves
    if shown and task["fact_text"] in (shown[0].text or ""):
        break
act.answer(task["answer"])
expect.backend()'''

    def discover(self, scan, page, site):
        out = []
        players = scan.get("players") or []
        if len(players) != 1:                  # one player per page: its parts have stable selectors
            return out
        for i, p in enumerate(players):
            if p["duration"] < 30 or p.get("stream") == "off" or not p.get("seek_css"):
                continue
            ctrl = {"kind": "player", "role": "player", "css": "[data-mini-player]", "seek_css": "[data-mini-player] .mp-seek",
                    "key": p["key"], "duration": p["duration"],
                    "label": p.get("title") or scan.get("h1") or scan["title"], "name": "player", "id": "",
                    "page": page, "page_title": scan["title"], "site_id": site}
            out.append((("player", page, i), ctrl))             # each page plays its own video
        return out

    def arguments(self, ctrl):
        facts = [s for s in timeline(ctrl)["segments"] if s["kind"] == "fact"]
        return [{"index": i, "value": f"{f['label']}@{f['start']}", "text": f["label"], "label": f["label"],
                 "answer": f["value"], "fact_text": f["text"], "start": f["start"], "end": f["end"]}
                for i, f in enumerate(facts)]

    def has_arguments(self, ctrl):
        return ctrl.get("duration", 0) >= 30

    def element_key(self, ctrl):
        return f"PLAYER {ctrl['key']}"

    def dedup_value(self, arg):
        return arg["label"]

    def view(self, ctrl):
        v = super().view(ctrl)
        v.pop("options", None)
        v.update({k: ctrl.get(k) for k in ("seek_css", "key", "duration", "site_id")})
        return v

    def check(self, ctrl, arg, keep=None):
        return {"kind": "answer", "value": arg["answer"], "alternatives": [], "evidence": [arg["fact_text"]],
                "requires": None}

    def dry_run(self, t, base, b):
        """The live player uses the same key/length, and seeking into the span shows the fact."""
        ctx = B.new_context(b)
        page = ctx.new_page()
        try:
            B.goto_start(page, base + t["start"]["url"])
            B.settle(page)
            c, o = t["control"], t["option"]
            live = next(iter(page.evaluate(_sm()._SCAN_JS, t["site"]).get("players") or []), None)
            if not live or live["key"] != c["key"] or round(live["duration"]) != round(c["duration"]):
                return False, f"player differs on the live page: {live and (live['key'], live['duration'])}"
            page.locator(SCREEN).first.scroll_into_view_if_needed(timeout=5000)
            page.locator(SCREEN).first.click(timeout=5000)
            page.wait_for_timeout(400)
            page.locator(PAUSE).first.click(timeout=5000)
            seek = page.locator(c["seek_css"]).first
            box = seek.bounding_box()
            frac = (o["start"] + 0.5 * (o["end"] - o["start"])) / c["duration"]
            page.mouse.click(box["x"] + frac * box["width"], box["y"] + box["height"] / 2)
            page.wait_for_timeout(800)
            shown = page.locator(c["css"] + " .mp-stream").first.inner_text(timeout=3000)
            if o["fact_text"] not in shown:
                return False, f"seeking into the span shows {shown[:80]!r}, not the fact"
            return True, f"fact {o['label']!r} at {o['start']}-{o['end']}s of {c['duration']:.0f}s"
        finally:
            ctx.close()

    def describe(self, ctrl):
        return {"type": "a video player whose on-screen overlay shows facts only at certain moments",
                "label": ctrl.get("label") or "",
                "note": "ask for the fact (e.g. the promo code shown in the video); name the video by its title; "
                        "do not give the time position and never state the answer"}

    def say(self, ctrl, arg):
        return {"find": f"the {arg['label']} shown in the video", "video": ctrl.get("label"),
                "reply": "ask the assistant to tell it"}

    def mentions(self, arg):
        return []

    def forbidden(self, arg):
        return [arg["answer"]]

    def step_spec(self, step):
        c, o = step["control"], step["option"]
        return [f"START: click the video (css={SCREEN!r}) to start it — the controls appear — then pause it "
                f"(css={PAUSE!r}) so the frame stays put",
                f"FIND: the {o['label']} that the video's overlay (css={c['css'] + ' .mp-stream'!r}) shows only between "
                f"{o['start']}s and {o['end']}s of {c['duration']:.0f}s — its text: {o['fact_text']!r}",
                f"SCRUB: click the seek bar (css={c['seek_css']!r}) at these fractions in order, stopping once the "
                f"overlay shows the fact: {scrub_plan(o['start'], o['end'], c['duration'], o['value'])}",
                f"ANSWER: act.answer({o['answer']!r}) while the fact is on screen"]

    def script_task(self, step):
        c, o = step["control"], step["option"]
        return {"subtask": step["subtask"], "seek_css": c["seek_css"], "screen_css": SCREEN, "pause_css": PAUSE, "overlay_css": c["css"] + " .mp-stream",
                "scrub": scrub_plan(o["start"], o["end"], c["duration"], o["value"]), "fact_text": o["fact_text"],
                "answer": o["answer"], "label": o["label"]}

    def locate(self, driver, step):
        return driver.query(css=step["control"]["seek_css"], limit=1)


def _sm():
    from datagen import sitemap
    return sitemap
