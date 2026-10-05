"""Playwright implementation of `actions.Driver` — the harness side of the wrapper.

Everything here is trusted harness code: the JS it evaluates only READS the page
(boxes, styles, labels, hit-tests); state changes happen only through real mouse and
keyboard input (`page.mouse` / `page.keyboard`) issued by `actions.Act`.
"""
from __future__ import annotations

from datagen import browser as B
from datagen.actions import Driver

_FIND = r"""
({css, text, tag, limit}) => {
  const norm = s => (s || '').replace(/\s+/g, ' ').trim().toLowerCase();
  let els;
  try {
    els = [...document.querySelectorAll(css || 'a,button,input,select,textarea,label,summary,option,[role],[onclick],[tabindex],h1,h2,h3,h4,h5,li,span,div,p,td,th,img')];
  } catch (e) { return 'bad css selector: ' + e.message; }
  if (tag) els = els.filter(e => e.tagName.toLowerCase() === String(tag).toLowerCase());
  const vis = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 1 && r.height > 1 && s.visibility !== 'hidden' && s.display !== 'none' && parseFloat(s.opacity || '1') > 0.05; };
  if (text) {
    const t = norm(text);
    const own = e => norm([e.innerText, e.value, e.getAttribute('aria-label'), e.getAttribute('placeholder'),
                           e.getAttribute('title'), e.getAttribute('alt'),
                           e.labels && e.labels[0] ? e.labels[0].innerText : ''].filter(Boolean).join(' '));
    let m = els.filter(e => own(e).includes(t));
    m = m.filter(e => !m.some(o => o !== e && e.contains(o)));             // deepest matches
    const score = e => (own(e) === t ? 0 : 1);
    m.sort((a, b) => score(a) - score(b) || own(a).length - own(b).length);
    els = m;
  }
  els = els.filter(vis).concat(els.filter(e => !vis(e)));
  return els.slice(0, limit || 20);
}
"""

# the text a person can read in the viewport now: rendered text nodes whose boxes intersect it,
# plus the values shown in form fields (a revealed code, a computed result in an <output>/<input>)
_VISIBLE_TEXT = r"""
() => {
  const W = innerWidth, H = innerHeight, out = [];
  const inView = r => r.width > 0 && r.height > 0 && r.bottom > 0 && r.right > 0 && r.top < H && r.left < W;
  const shown = el => { for (let e = el; e && e !== document.body; e = e.parentElement) {
      const s = getComputedStyle(e); if (s.display === 'none' || s.visibility === 'hidden' || parseFloat(s.opacity || '1') < 0.05) return false; }
    return true; };
  const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const range = document.createRange();
  let n, budget = 6000;
  while ((n = walk.nextNode()) && budget-- > 0) {
    const t = n.textContent.replace(/\s+/g, ' ').trim();
    if (!t || !n.parentElement || ['SCRIPT', 'STYLE', 'NOSCRIPT'].includes(n.parentElement.tagName)) continue;
    range.selectNodeContents(n);
    if ([...range.getClientRects()].some(inView) && shown(n.parentElement)) out.push(t);
  }
  document.querySelectorAll('input:not([type=hidden]):not([type=password]),textarea,output,select').forEach(el => {
    const v = el.tagName === 'SELECT' ? (el.selectedOptions[0] || {}).text : el.value;
    if (v && inView(el.getBoundingClientRect()) && shown(el)) out.push(String(v));
  });
  return out.join('\n').slice(0, 60000);
}
"""

_INFO = r"""
(el) => {
  if (!el || !el.isConnected) return null;
  const txt = s => (s || '').replace(/\s+/g, ' ').trim();
  const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
  const visible = r.width > 1 && r.height > 1 && s.visibility !== 'hidden' && s.display !== 'none' && parseFloat(s.opacity || '1') > 0.05;
  let label = '';
  if (el.labels && el.labels.length) { const c = el.labels[0].cloneNode(true);
    c.querySelectorAll('select, option, input, textarea, button').forEach(n => n.remove()); label = txt(c.textContent); }
  if (!label) label = txt(el.getAttribute('aria-label') || el.getAttribute('title') || '');
  const tag = el.tagName.toLowerCase();
  const out = {tag, text: txt(el.innerText || el.value || el.getAttribute('aria-label') || el.getAttribute('alt') || '').slice(0, 200),
    label, name: el.getAttribute('name') || '', id: el.id || '', type: el.getAttribute('type') || '',
    role: el.getAttribute('role') || '', placeholder: el.getAttribute('placeholder') || '',
    href: el.getAttribute('href') || '', visible, checked: !!el.checked, disabled: !!el.disabled,
    value: ('value' in el && typeof el.value === 'string') ? el.value.slice(0, 200) : '',
    box: [r.x, r.y, r.width, r.height]};
  if (tag === 'select') {
    out.options = [...el.options].map((o, i) => ({index: i, value: o.value, text: txt(o.text), selected: o.selected}));
    out.selected_text = el.selectedIndex >= 0 ? txt(el.options[el.selectedIndex].text) : '';
    out.text = out.selected_text;
  }
  return out;
}
"""

_HIT = r"""
([el, x, y]) => { const t = document.elementFromPoint(x, y);
  return !!t && (t === el || el.contains(t) || (t.tagName === 'LABEL' && t.control === el)); }
"""

_SCROLL_BOX = r"""
(el) => { let n = el.parentElement;
  while (n && n !== document.body && n !== document.documentElement) {
    const s = getComputedStyle(n);
    if (/(auto|scroll|overlay)/.test(s.overflowY) && n.scrollHeight > n.clientHeight + 4) {
      const r = n.getBoundingClientRect(); return [r.x, r.y, r.width, r.height]; }
    n = n.parentElement; }
  return null; }
"""

_OUTLINE = r"""
(limit) => {
  const txt = s => (s || '').replace(/\s+/g, ' ').trim();
  const out = []; const H = innerHeight;
  const vis = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 1 && r.height > 1 && s.visibility !== 'hidden' && s.display !== 'none'; };
  for (const el of document.querySelectorAll('h1,h2,h3,a,button,input,select,textarea,label,[role=button],[role=tab]')) {
    if (!vis(el)) continue;
    const r = el.getBoundingClientRect();
    const where = r.bottom < 0 ? 'above' : (r.top > H ? 'below' : 'on-screen');
    let t = el.tagName.toLowerCase();
    let desc = txt(el.innerText || el.value || el.getAttribute('aria-label') || el.getAttribute('placeholder') || '').slice(0, 60);
    if (t === 'select') desc = `name=${el.name || el.id || ''} selected=${txt(el.options[el.selectedIndex] ? el.options[el.selectedIndex].text : '')} (${el.options.length} options)`;
    if (t === 'input') desc = `type=${el.type} name=${el.name || el.id || ''} value=${txt(el.value).slice(0, 30)} ${desc}`;
    out.push(`${t} [${where} y=${Math.round(r.y)}] ${desc}`);
    if (out.length >= limit) break;
  }
  return out.join('\n');
}
"""

_FOCUSED = "() => { const a = document.activeElement; return (a && a !== document.body) ? a : null; }"

# A unique CSS path for an element (id, then name, then an nth-of-type chain). Read-only.
_CSS_PATH = r"""
const cssOf = el => {
  const uniq = css => { try { return document.querySelectorAll(css).length === 1; } catch (e) { return false; } };
  const tag = el.tagName.toLowerCase();
  if (el.id && uniq('#' + CSS.escape(el.id))) return '#' + CSS.escape(el.id);
  const nm = el.getAttribute('name');
  if (nm) { const c = `${tag}[name="${nm}"]`; if (uniq(c)) return c; }
  const parts = []; let n = el;
  while (n && n.nodeType === 1 && n !== document.body) {
    let p = n.tagName.toLowerCase(); const par = n.parentElement;
    if (par) { const sib = [...par.children].filter(c => c.tagName === n.tagName);
      if (sib.length > 1) p += `:nth-of-type(${sib.indexOf(n) + 1})`; }
    parts.unshift(p); if (n.id) { parts[0] = '#' + CSS.escape(n.id); break; } n = par;
  }
  return parts.join(' > ');
};
const txt = s => (s || '').replace(/\s+/g, ' ').trim();
"""

_DESCRIBE = "(el) => {" + _CSS_PATH + r"""
  if (!el || !el.isConnected) return null;
  const tag = el.tagName.toLowerCase();
  let name = '';
  const lb = el.getAttribute('aria-labelledby');
  if (lb) name = lb.split(/\s+/).map(id => { const n = document.getElementById(id); return n ? txt(n.innerText) : ''; }).join(' ');
  if (!name) name = txt(el.getAttribute('aria-label') || '');
  if (!name && el.labels && el.labels.length) { const c = el.labels[0].cloneNode(true);
    c.querySelectorAll('select, option, input, textarea, button').forEach(n => n.remove()); name = txt(c.textContent); }
  if (!name) name = txt(el.getAttribute('alt') || el.getAttribute('title') || el.getAttribute('placeholder') || '');
  if (!name && tag !== 'select') name = txt(el.innerText || el.value || '').slice(0, 120);
  const t = (el.getAttribute('type') || '').toLowerCase();
  const implicit = {a: el.hasAttribute('href') ? 'link' : '', button: 'button', select: el.multiple ? 'listbox' : 'combobox',
    textarea: 'textbox', img: 'img', h1: 'heading', h2: 'heading', h3: 'heading', h4: 'heading', option: 'option',
    input: ({checkbox: 'checkbox', radio: 'radio', range: 'slider', submit: 'button', button: 'button'}[t] || 'textbox')}[tag] || '';
  // visual label when there is no programmatic one: a short heading/label-ish sibling just before it
  let ctx = '';
  for (let n = el; n && n !== document.body && !ctx; n = n.parentElement) {
    const p = n.previousElementSibling;
    if (p && ['LABEL','SPAN','STRONG','B','P','H2','H3','H4','H5','H6','SMALL','DIV'].includes(p.tagName)
        && !p.querySelector('a,button,input,select,textarea') && txt(p.innerText) && txt(p.innerText).length < 40) ctx = txt(p.innerText);
    if (n.parentElement && n.parentElement.children.length > 3) break;
  }
  return {css_path: cssOf(el), accessible_name: name, implicit_role: implicit, context_label: ctx};
}"""

_ELEMENT_AT = "([x, y, el]) => {" + _CSS_PATH + r"""
  const t = document.elementFromPoint(x, y);
  if (!t) return null;
  const r = t.getBoundingClientRect();
  return {tag: t.tagName.toLowerCase(), id: t.id || '', text: txt(t.innerText || t.value || '').slice(0, 80),
          css_path: cssOf(t), box: [r.x, r.y, r.width, r.height].map(v => Math.round(v * 10) / 10),
          is_target: !!el && t === el, inside_target: !!el && el.contains(t)};
}"""

_SCROLL_STATE = "(el) => {" + _CSS_PATH + r"""
  const out = {window: [Math.round(window.scrollX), Math.round(window.scrollY)], container: null};
  let n = el ? el.parentElement : null;
  while (n && n !== document.body && n !== document.documentElement) {
    const s = getComputedStyle(n);
    if (/(auto|scroll|overlay)/.test(s.overflowY) && n.scrollHeight > n.clientHeight + 4) {
      out.container = {css_path: cssOf(n), scroll_top: Math.round(n.scrollTop), scroll_left: Math.round(n.scrollLeft)};
      break; }
    n = n.parentElement; }
  return out;
}"""


class PlaywrightDriver(Driver):
    def __init__(self, page, viewport):
        self.page = page
        self.pages = [page]                 # browser tabs, in the order they were opened
        self._vp = tuple(viewport)
        self.dialogs, self.downloads = [], []
        self._watch(page)

    def _watch(self, page):
        # native confirm()/alert(): accepted, as a person clicking OK would (Playwright's default
        # dismisses them, which cancels deletes); the messages are kept for the attempt record
        page.on("dialog", lambda d: (self.dialogs.append({"type": d.type, "message": d.message[:200]}), d.accept()))
        page.on("download", lambda dl: self.downloads.append({"filename": dl.suggested_filename, "url": dl.url}))

    def new_tab(self, path):
        """Open `path` (same site origin) in a new tab and make it the current one."""
        from urllib.parse import urlsplit
        u = urlsplit(self.page.url)
        tab = self.page.context.new_page()
        self._watch(tab)
        tab.goto(f"{u.scheme}://{u.netloc}{path}", wait_until="load", timeout=30000)
        self.pages.append(tab)
        self.page = tab
        tab.bring_to_front()

    def switch_tab(self, index):
        self.page = self.pages[index]
        self.page.bring_to_front()

    def choose_file(self, x, y, path, input_css=None):
        """Click at (x, y) — a file input or the control that opens one — and pick `path` in the
        file chooser (what a person does in the OS dialog). Headless Chromium does not open a
        chooser for some scripted drop zones; then the file goes to the control's own input, as
        the dialog would have done."""
        try:
            with self.page.expect_file_chooser(timeout=4000) as fc:
                self.page.mouse.click(x, y)
            fc.value.set_files(path)
        except Exception:
            if not input_css:
                raise
            self.page.set_input_files(input_css, path, timeout=5000)

    def viewport(self):
        return self._vp

    def query(self, css=None, text=None, tag=None, limit=20):
        from datagen.actions import ActionError
        h = self.page.evaluate_handle(_FIND, {"css": css, "text": text, "tag": tag, "limit": int(limit or 20)})
        try:
            err = h.json_value() if not h.evaluate("x => Array.isArray(x)") else None
        except Exception:
            err = None
        if isinstance(err, str):
            raise ActionError(err)
        props = h.get_properties()
        out = []
        for k in sorted(props, key=lambda k: int(k) if str(k).isdigit() else 1 << 30):
            el = props[k].as_element()
            if el is None:
                continue
            info = self.info(el)
            if info is not None:
                out.append((el, info))
        return out

    def info(self, key):
        try:
            return key.evaluate(_INFO)
        except Exception:
            return None

    def hit(self, key, x, y):
        try:
            return bool(self.page.evaluate(_HIT, [key, x, y]))
        except Exception:
            return False

    def scroll_box(self, key):
        try:
            return key.evaluate(_SCROLL_BOX)
        except Exception:
            return None

    def focused(self):
        h = self.page.evaluate_handle(_FOCUSED)
        el = h.as_element()
        if el is None:
            return None
        info = self.info(el)
        return (el, info) if info else None

    def describe(self, key):
        return key.evaluate(_DESCRIBE)

    def element_at(self, x, y, key=None):
        return self.page.evaluate(_ELEMENT_AT, [x, y, key])

    def scroll_state(self, key=None):
        return key.evaluate(_SCROLL_STATE) if key is not None else self.page.evaluate(_SCROLL_STATE, None)

    def screenshot(self):
        return self.page.screenshot(type="png", caret="initial")

    def click(self, x, y, button="left", clicks=1):
        self.page.mouse.click(x, y, button=button, click_count=clicks)

    def move(self, x, y, steps=1):
        self.page.mouse.move(x, y, steps=steps)

    def down(self):
        self.page.mouse.down()

    def up(self):
        self.page.mouse.up()

    def wheel(self, x, y, dx, dy):
        self.page.mouse.move(x, y)
        self.page.mouse.wheel(dx, dy)

    def press(self, key):
        self.page.keyboard.press(key)

    def type(self, text):
        self.page.keyboard.type(text, delay=35)

    def settle(self):
        B.settle(self.page)

    def url(self):
        return self.page.url

    def title(self):
        try:
            return self.page.title()
        except Exception:
            return ""

    def outline(self, limit=80):
        try:
            return self.page.evaluate(_OUTLINE, int(limit))
        except Exception:
            return ""

    def open_url(self, path):
        from urllib.parse import urlsplit
        u = urlsplit(self.page.url)
        self.page.goto(f"{u.scheme}://{u.netloc}{path}", wait_until="load", timeout=30000)

    def visible_text(self):
        try:
            return self.page.evaluate(_VISIBLE_TEXT)
        except Exception:
            return ""
