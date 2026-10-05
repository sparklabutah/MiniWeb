"""Capture the supplement's screenshots: every site's landing page and read-only views of the annotation tool.

Needs a running MiniWeb server on a free port, e.g.
    python -c "from app import create_app; create_app().run(host='127.0.0.1', port=8395)"
then: MINIWEB_URL=http://127.0.0.1:8395 python docs/figures/site_gallery/capture.py

The annotation tool requires an annotator session. Instead of logging in, the script signs a session cookie with the
app's own key (local server only). It only opens pages; it never saves a task.
"""
import asyncio, os, sys
from playwright.async_api import async_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, ROOT)
URL = os.environ.get("MINIWEB_URL", "http://127.0.0.1:8395")
CHROME = os.path.expanduser("~/.cache/ms-playwright/chromium-1117/chrome-linux/chrome")
ARGS = ["--headless=new", "--disable-gpu", "--disable-software-rasterizer", "--disable-dev-shm-usage", "--no-sandbox",
        "--use-angle=swiftshader-webgl"]
OUT_SITES = os.path.join(HERE, "shots")
OUT_ANN = os.path.join(HERE, "annotation")
# read-only annotation views: the dashboard, the task editor re-opened on a recorded task, the verifier page,
# and the macro browser
ANNOTATION = {
    "dashboard": "/annotate/",
    "task_editor": "/annotate/task?rerecord=url-shorteners-qr_74e00a&annotator=Farhan",
    "verify": "/annotate/verify",
    "macro_browser": "/annotate/macro-browser",
}


# double-blind: annotator names (some are authors) are replaced in every text node before a screenshot
ANONYMIZE = r"""
(() => {
  const MAP = {minh: 'Annotator A', farhan: 'Annotator B', hernan: 'Annotator C', 'hernán': 'Annotator C',
               kenny: 'Annotator D', reaz: 'Annotator E', omar: 'Annotator F'};
  const RE = /\b(minh|farhan|hern[aá]n|kenny|reaz|omar)\b/gi;
  const fix = t => t.replace(RE, m => MAP[m.toLowerCase()] || 'Annotator');
  const scrub = root => {
    const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    for (let n = w.nextNode(); n; n = w.nextNode()) { const v = fix(n.nodeValue); if (v !== n.nodeValue) n.nodeValue = v; }
    root.querySelectorAll && root.querySelectorAll('input, textarea').forEach(e => { if (RE.test(e.value)) e.value = fix(e.value); });
  };
  window.__mwScrub = () => scrub(document.body);
  document.addEventListener('DOMContentLoaded', () => {
    scrub(document.body);
    new MutationObserver(() => scrub(document.body)).observe(document.body, {childList: true, subtree: true, characterData: true});
  });
})();
"""


def annotator_cookie():
    from app import create_app
    app = create_app()
    value = app.session_interface.get_signing_serializer(app).dumps({"annotator_authenticated": True,
                                                                    "annotator_name": "Annotator"})
    return {"name": app.config.get("SESSION_COOKIE_NAME", "session"), "value": value, "url": URL}


async def main(sites):
    os.makedirs(OUT_SITES, exist_ok=True); os.makedirs(OUT_ANN, exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME if os.path.exists(CHROME) else None, args=ARGS)
        ctx = await b.new_context(viewport={"width": 1280, "height": 800}, device_scale_factor=1)
        pg = await ctx.new_page()
        for s in sites:
            try:
                await pg.goto(f"{URL}/sites/{s}/", wait_until="load", timeout=30000)
                await pg.wait_for_timeout(1200)
                await pg.screenshot(path=os.path.join(OUT_SITES, f"{s}.jpg"), type="jpeg", quality=88)
                print("site", s)
            except Exception as e:                       # keep going; report at the end
                print("FAILED", s, str(e)[:120])
        await ctx.close()
        ctx = await b.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1.5)
        await ctx.add_cookies([annotator_cookie()])
        # the task editor asks for the annotator's name once per tab (sessionStorage); pre-set it to skip the gate
        await ctx.add_init_script("try { sessionStorage.setItem('annotator_name', 'Annotator'); } catch (e) {}")
        await ctx.add_init_script(ANONYMIZE)
        pg = await ctx.new_page()
        for name, path in ANNOTATION.items():
            await pg.goto(URL + path, wait_until="load", timeout=30000)
            await pg.wait_for_timeout(4000)
            if name == "task_editor":                     # dismiss the design-notes popup
                btn = pg.locator("button:has-text('Got it')")
                if await btn.count():
                    await btn.first.click(); await pg.wait_for_timeout(500)
            if name == "verify":                          # open one task in the builder, scrolled to its checks
                await pg.fill("input[placeholder^='Search tasks']", "url-shorteners-qr_74e00a")
                await pg.wait_for_timeout(1000)
                await pg.click("text=url-shorteners-qr_74e00a")
                await pg.wait_for_timeout(3000)
                h = pg.locator("h3:has-text('Verifier Builder')")
                if await h.count():
                    await h.first.scroll_into_view_if_needed()
                    await pg.evaluate("document.querySelectorAll('h3').forEach(e => { if (e.textContent.trim() =="
                                      " 'Verifier Builder') e.scrollIntoView({block: 'start'}); })")
                    await pg.wait_for_timeout(800)
            for f in pg.frames:                           # the embedded site is an iframe
                try:
                    await f.evaluate("window.__mwScrub && window.__mwScrub()")
                except Exception:
                    pass
            await pg.wait_for_timeout(300)
            await pg.screenshot(path=os.path.join(OUT_ANN, f"{name}.png"))
            print("annotation", name, pg.url)
        await b.close()


if __name__ == "__main__":
    import glob, json
    sites = sorted({json.load(open(f))["site"] for f in glob.glob(os.path.join(ROOT, "data", "annotations", "*", "*", "task.json"))})
    asyncio.run(main(sites if "--annotation-only" not in sys.argv else []))
