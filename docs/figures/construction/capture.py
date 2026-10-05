"""Capture the construction figure's SnapLink screenshots (shots/c_*.png) and the box around each skill's control (boxes.json).

Needs a running MiniWeb server on a free port, e.g.
    python -c "from app import create_app; create_app().run(host='127.0.0.1', port=8395)"
then: MINIWEB_URL=http://127.0.0.1:8395 python docs/figures/construction/capture.py && python docs/figures/construction/make_construction.py
The mini site tiles reuse ../teaser/shots. Chrome is the eval harness's pinned chromium-1117 with its flags (the default
headless build never loads pages on this machine).
"""
import asyncio, json, os
from playwright.async_api import async_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
URL = os.environ.get("MINIWEB_URL", "http://127.0.0.1:8395")
CHROME = os.path.expanduser("~/.cache/ms-playwright/chromium-1117/chrome-linux/chrome")
ARGS = ["--headless=new", "--disable-gpu", "--disable-software-rasterizer", "--disable-dev-shm-usage", "--no-sandbox",
        "--use-angle=swiftshader-webgl"]
VW = 560                                # narrow viewport: the page stacks, so its text stays legible in a small tile
# shot key: (page, {box key: JS expression for the element to box})
SHOTS = {
    "links": ("/sites/url-shorteners-qr/links?sort=clicks", {
        "sort": "document.querySelector('select[name=sort]')",
        "filter": "Array.from(document.querySelectorAll('button')).find(e => (e.innerText || '').trim() === 'Filter')",
        "top": "Array.from(document.querySelectorAll('code, span, a')).find(e => e.children.length === 0"
               " && (e.innerText || '').trim() === 'snplnk.io/promo1')",
    }),
    "detail": ("/sites/url-shorteners-qr/link/2", {
        "share": "Array.from(document.querySelectorAll('button')).find(e => /Sharing:/.test(e.innerText))",
    }),
}


async def main():
    os.makedirs(os.path.join(HERE, "shots"), exist_ok=True)
    boxes = {"_viewport": VW}
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME if os.path.exists(CHROME) else None, args=ARGS)
        pg = await (await b.new_context(viewport={"width": VW, "height": 700}, device_scale_factor=2)).new_page()
        for key, (path, js) in SHOTS.items():
            await pg.goto(URL + path, wait_until="load")
            await pg.wait_for_timeout(900)
            for bk, expr in js.items():
                boxes[bk] = await pg.evaluate("() => { const e = " + expr + "; if (!e) return null;"
                                              " const r = e.getBoundingClientRect(); return [r.x, r.y, r.width, r.height]; }")
                print(key, bk, boxes[bk])
            await pg.screenshot(path=os.path.join(HERE, "shots", f"c_{key}.png"))
        await b.close()
    json.dump(boxes, open(os.path.join(HERE, "boxes.json"), "w"), indent=1)

asyncio.run(main())
