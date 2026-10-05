"""search_by_pan_zoom — find a place by moving a map: drag it toward the place, zoom in until the
place's marker and label show, open the marker, and report what its popup says.

A control is an interactive (Leaflet) map whose page keeps its places in a `locations` array; the
map renders only the markers inside the current view and names them only when zoomed in. Its
arguments are places that are neither on screen at the start nor in the list beside the map, so
moving the map is the only way to them. The answer is the place's address (from the page data);
the check is an `answer` check whose evidence is that address (shown in the marker's popup), and
the reused verifier also requires a drag of the map. The dry run plans the drags on the live map
(its own projection), performs them with the mouse, zooms in with the + control, clicks the
marker at the centre and requires the popup to show the address.
"""
from __future__ import annotations

import math

from datagen import browser as B
from datagen.kinds import register
from datagen.kinds.base import Kind

ZOOM_TO = 16
POINT_JS = "(t) => { const el = window.map.getContainer(); const p = window.map.latLngToContainerPoint([t.lat, t.lng]); " \
           "return {w: el.clientWidth, h: el.clientHeight, x: p.x, y: p.y, zoom: window.map.getZoom()}; }"


def drag_plan(pt, frac=0.6):
    """Drags (map-box fractions: from -> to) that bring a container point to the centre."""
    w, h = pt["w"], pt["h"]
    dx, dy = w / 2 - pt["x"], h / 2 - pt["y"]
    n = max(1, math.ceil(max(abs(dx) / (frac * w), abs(dy) / (frac * h))))
    out = []
    for _ in range(n):
        sx, sy = dx / n, dy / n
        x0, y0 = 0.5 - sx / w / 2, 0.5 - sy / h / 2
        out.append([[round(x0, 4), round(y0, 4)], [round(x0 + sx / w, 4), round(y0 + sy / h, 4)]])
    return out


@register
class MapViewKind(Kind):
    name = "mapview"
    macros = {"search_by_pan_zoom": "mapview"}
    needs_probe = False
    example = '''# example: drag the map toward the place, zoom in, open its marker, read the popup, reply
m = dom.one(css=task["map_css"])
for src, dst in task["drags"]:
    act.drag(m, m, at_source=src, at_target=dst)
for _ in range(task["zoom_clicks"]):
    act.click(dom.one(css=task["zoom_in_css"]))
act.wait(1)
act.click(m, at=task["marker_at"])                  # the place's marker, now at the centre
popup = dom.one(text=task["address"])
act.answer(task["answer"])
expect.backend()'''

    def discover(self, scan, page, site):
        lf = scan.get("leaflet")
        if not lf or not lf.get("zoom_in_css"):
            return []
        hidden = [p for p in lf["places"] if not p["in_view"] and p["address"] and p["category"] != "bus_stop"]
        hidden.sort(key=lambda p: p["listed"])              # unlisted first: the map is the only way there
        if not hidden:
            return []
        ctrl = {"kind": "mapview", "role": "mapview", "css": lf["css"], "zoom_in_css": lf["zoom_in_css"],
                "label": scan.get("h1") or scan["title"], "name": "map", "id": "", "zoom": lf["zoom"],
                "places": hidden[:80], "page": page, "page_title": scan["title"], "site_id": site}
        return [(("mapview", _sm()._pattern(page)), ctrl)]

    def arguments(self, ctrl):
        return [{"index": i, "value": p["id"], "text": p["name"], **p} for i, p in enumerate(ctrl.get("places") or [])]

    def element_key(self, ctrl):
        return f"MAP {_sm()._pattern(ctrl['page'])}"

    def view(self, ctrl):
        v = super().view(ctrl)
        v.pop("options", None)
        v.update({k: ctrl.get(k) for k in ("zoom_in_css", "zoom", "site_id")})
        return v

    def check(self, ctrl, arg, keep=None):
        return {"kind": "answer", "value": arg["address"], "alternatives": [], "evidence": [arg["address"]],
                "requires": None, "actions": ["drag"]}

    def dry_run(self, t, base, b):
        c, o = t["control"], t["option"]
        ctx = B.new_context(b)
        page = ctx.new_page()
        try:
            B.goto_start(page, base + t["start"]["url"])
            B.settle(page)
            page.wait_for_timeout(600)
            pt = page.evaluate(POINT_JS, {"lat": o["lat"], "lng": o["lng"]})
            if 0 <= pt["x"] <= pt["w"] and 0 <= pt["y"] <= pt["h"]:
                return False, "the place is already on screen"
            drags = drag_plan(pt)
            box = page.locator(c["css"]).first.bounding_box()
            for (fx0, fy0), (fx1, fy1) in drags:
                page.mouse.move(box["x"] + fx0 * box["width"], box["y"] + fy0 * box["height"])
                page.mouse.down()
                for k in range(1, 13):
                    page.mouse.move(box["x"] + (fx0 + (fx1 - fx0) * k / 12) * box["width"],
                                    box["y"] + (fy0 + (fy1 - fy0) * k / 12) * box["height"])
                page.wait_for_timeout(200)
                page.mouse.up()
                page.wait_for_timeout(300)
            clicks = max(0, math.ceil(ZOOM_TO - pt["zoom"]))
            for _ in range(clicks):
                page.locator(c["zoom_in_css"]).first.click(timeout=5000)
                page.wait_for_timeout(350)
            after = page.evaluate(POINT_JS, {"lat": o["lat"], "lng": o["lng"]})
            if abs(after["x"] - after["w"] / 2) > 40 or abs(after["y"] - after["h"] / 2) > 40:
                return False, f"the plan does not centre the place ({after['x']:.0f},{after['y']:.0f})"
            marker_at = [0.5, round(0.5 - 14 / after["h"], 4)]            # the pin's body sits above its anchor
            page.mouse.click(box["x"] + marker_at[0] * box["width"], box["y"] + marker_at[1] * box["height"])
            page.wait_for_timeout(500)
            popup = page.locator(".leaflet-popup-content")
            if not popup.count() or o["address"] not in popup.first.inner_text():
                return False, "clicking the centred marker does not show the place's popup"
            o.update(drags=drags, zoom_clicks=clicks, marker_at=marker_at)
            return True, f"{len(drags)} drags, {clicks} zoom clicks -> {o['name']}: {o['address']}"
        finally:
            ctx.close()

    def describe(self, ctrl):
        return {"type": "an interactive map (drag to pan, + / − to zoom); only places in view are drawn",
                "label": ctrl.get("label") or "",
                "note": "ask to find the named place ON THE MAP (by moving and zooming it) and report its address; do "
                        "not say the address"}

    def say(self, ctrl, arg):
        return {"find on the map": arg["name"], "report": "its address, from its marker's popup"}

    def mentions(self, arg):
        return [arg["name"]]

    def forbidden(self, arg):
        return [arg["address"]]

    def step_spec(self, step):
        c, o = step["control"], step["option"]
        return [f"PAN: drag the map (css={c['css']!r}) with these box-fraction drags: {o['drags']}",
                f"ZOOM: click {c['zoom_in_css']!r} {o['zoom_clicks']} times",
                f"OPEN: click the marker at the centre: act.click(map, at={tuple(o['marker_at'])})",
                f"ANSWER: the popup shows {o['address']!r}; act.answer({o['address']!r})"]

    def script_task(self, step):
        c, o = step["control"], step["option"]
        return {"subtask": step["subtask"], "map_css": c["css"], "drags": o["drags"], "zoom_clicks": o["zoom_clicks"],
                "zoom_in_css": c["zoom_in_css"], "marker_at": o["marker_at"], "address": o["address"],
                "answer": o["address"], "name": o["name"]}

    def locate(self, driver, step):
        return driver.query(css=step["control"]["css"], limit=1)


def _sm():
    from datagen import sitemap
    return sitemap
