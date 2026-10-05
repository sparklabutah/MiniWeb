"""Capture the teaser's site screenshots (shots/t_*.png) and the box around each skill's control (boxes.json).

Needs a running MiniWeb server, e.g.
    python -c "from app import create_app; create_app().run(host='127.0.0.1', port=8390)"
then: MINIWEB_URL=http://127.0.0.1:8390 python docs/figures/teaser/capture.py && python docs/figures/teaser/make_teaser.py
"""
import asyncio, json, os
from playwright.async_api import async_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
URL = os.environ.get("MINIWEB_URL", "http://127.0.0.1:8390")
# tile key: (page, JS expression for the element to box, or a fixed [x, y, w, h] in CSS px)
TILES = {
    "shop": ("/sites/e-commerce/", "document.querySelector('input[type=range]').closest('div')"),
    "travel": ("/sites/flights-hotels/", "document.querySelector('input[type=date]').parentElement"),
    "bank": ("/sites/banking/pay-bills", "Array.from(document.querySelectorAll('tr')).find(r => /Pay Now/.test(r.innerText)).lastElementChild"),
    "video": ("/sites/video/upload", "Array.from(document.querySelectorAll('button,label,a')).find(e => /select files/i.test(e.innerText))"),
    "calendar": ("/sites/calendar-todo/", "(() => { const h = Array.from(document.querySelectorAll('*')).find(x => x.children.length === 0"
                 " && /^(THU|Thu)$/.test((x.innerText || '').trim())).closest('div,th'); const r = h.getBoundingClientRect();"
                 " return {x: r.x, y: r.y, width: r.width, height: 780 - r.y}; })()"),
    "sheet": ("/sites/spreadsheets-slides/spreadsheet/1", "Array.from(document.querySelectorAll('input, td, div')).find(x => (x.value || '').trim()"
              " === '12000' || (x.children.length === 0 && x.innerText && x.innerText.trim() === '12000'))"),
}

async def main():
    os.makedirs(os.path.join(HERE, "shots"), exist_ok=True)
    boxes = {}
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await (await b.new_context(viewport={"width": 1280, "height": 800}, device_scale_factor=2)).new_page()
        for key, (path, js) in TILES.items():
            await pg.goto(URL + path, wait_until="networkidle")
            await pg.wait_for_timeout(900)
            boxes[key] = await pg.evaluate("() => { const e = " + js + "; if (!e) return null;"
                                           " const r = e.getBoundingClientRect ? e.getBoundingClientRect() : e;"
                                           " return [r.x, r.y, r.width, r.height]; }")
            await pg.screenshot(path=os.path.join(HERE, "shots", f"t_{key}.png"))
            print(key, boxes[key])
        await b.close()
    json.dump(boxes, open(os.path.join(HERE, "boxes.json"), "w"), indent=1)

asyncio.run(main())
