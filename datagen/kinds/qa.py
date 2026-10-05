"""Questions answered from what a page shows: report_information (with its reasoning op) and
count_entries.

A control is a RECORD SET on a page — a data table, or a group of repeated cards (search
results, listings, feeds). Its records come from the table cells directly, or, for cards, from
an LLM that copies names and field values out of the card lines verbatim (cached; every value
is checked against the card text, so nothing invented survives). Questions are built from the
records in code, one family per reasoning op, and the answer is COMPUTED here, never by an LLM:

    read      "What is the <field> of <name>?"                      -> the cell
    extremum  "Which <entity> has the highest <field>?"             -> the name
    count     "How many <entity> have <field> <value>?"             -> a number
    compute   "What is the total <field> of A and B?"               -> a number
    compare   "Which has the higher <field>, A or B?"               -> a name
    verify    "Is A's <field> above N?"                             -> Yes / No
    entries   "How many <entity> are listed?" (count_entries)       -> a number

The check is an `answer` check: the reply must match AND every fact it rests on (the evidence
strings: the names and values involved; every row for questions over the whole set) must have
been on screen in a recorded screenshot. The dry run re-reads the live page and requires the
same answer from it.
"""
from __future__ import annotations

import hashlib
import json
import random
import re

from datagen import config
from datagen import browser as B
from datagen.kinds import register
from datagen.kinds.base import Kind

MAX_SET = 25                 # questions over the whole set: at most this many records (all must be seen)
PER_OP = 4                   # arguments per op per control
CACHE = config.DATAGEN_DIR / "qa_records"
_NUM = re.compile(r"^[^\d\-−]{0,4}(-|−)?\d[\d,]*(\.\d+)?\s*(%|[a-zA-Z/°]{0,6})?$")


def number(v):
    """'$1,299.50' -> 1299.5; '72%' -> 72; '4.5 km' -> 4.5; anything else -> None."""
    s = str(v or "").strip()
    if not s or len(s) > 24 or not _NUM.match(s) or re.search(r"\d[-/:]\d", s):
        return None
    m = re.search(r"(-|−)?\d[\d,]*(\.\d+)?", s)
    try:
        return float(m.group(0).replace(",", "").replace("−", "-"))
    except (AttributeError, ValueError):
        return None


def fmt_like(x, samples):
    """A computed number written like the source values ($, %, decimals)."""
    s = str(samples[0]).strip()
    dec = max((len(m.group(1)) for v in samples for m in [re.search(r"\.(\d+)", str(v))] if m), default=0)
    body = f"{x:,.{dec}f}" if "," in "".join(map(str, samples)) else f"{x:.{dec}f}"
    pre = re.match(r"^[^\d\-−]*", s).group(0)
    post = re.search(r"[^\d]*$", s).group(0) if re.search(r"\d", s) else ""
    return f"{pre}{body}{post}".strip()


def _additive(field, samples):
    return not (re.search(r"(rate|rating|score|percent|apr|apy|avg|average|age|year|rank|grade|temp)", field, re.I)
                or any("%" in str(s) or "★" in str(s) for s in samples))


def _plain(x):
    return f"{x:.2f}".rstrip("0").rstrip(".")


# ── records ──────────────────────────────────────────────────────────────────

def table_records(tb):
    """Rows of a scanned table as [{name, fields}], the name from the first mostly-unique text column."""
    heads, rows = tb["headers"], tb["rows"]
    name_col = None
    for i, h in enumerate(heads):
        vals = [r[i] for r in rows if i < len(r)]
        texty = [v for v in vals if v and number(v) is None and re.search(r"[A-Za-z]{2}", v)]
        if len(texty) >= 0.8 * len(vals) and len(set(vals)) == len(vals) and all(len(v) <= 90 for v in vals):
            name_col = i
            break
    if name_col is None:
        return []
    out = []
    for r in rows:
        f = {_field_name(heads[i]): r[i] for i in range(len(heads)) if i != name_col and r[i] and _field_name(heads[i])}
        out.append({"name": r[name_col], "fields": f})
    return out


def _field_name(h):
    h = re.sub(r"[↑↓▲▼⇅]+", "", str(h or "")).strip()
    return h.lower() if h.isupper() or h.istitle() else h


def _cards_key(ctrl):
    return hashlib.sha1(json.dumps([ctrl["page"], ctrl["cards"]], sort_keys=True).encode()).hexdigest()[:16]


EXTRACT_SYSTEM = ("You turn repeated cards of a web page into records. Each card is given as its lines of text. "
                  "For every card return its name (the line that names the item — a title, a person, a product; "
                  "copied EXACTLY) and its fields: short attribute values that appear in the card (price, date, "
                  "rating, status, location, author, count …), each keyed by a short lower-case field name and "
                  "copied EXACTLY from the card (a whole line or an exact part of one; drop a leading label like "
                  "'Price:'). Use the same field names across cards. Skip long descriptions. Return one record for "
                  "EVERY card, in order, each with its card index. Reply ONLY JSON.")


def card_records(ctrl, model=None, force=False):
    """[{name, fields}] for a card group (LLM, cached, verbatim-validated) + the entity noun."""
    path = CACHE / ctrl["site_id"] / f"{_cards_key(ctrl)}.json"
    if path.exists() and not force:
        return json.loads(path.read_text())
    from helpers.llm import call_llm
    prompt = json.dumps({"page": ctrl.get("page_title"), "section": ctrl.get("heading"),
                         "cards": ctrl["cards"][:30],
                         "output": {"entity": "plural noun for these items (e.g. 'job listings')",
                                    "records": [{"card": 0, "name": "…", "fields": {"price": "$12.99"}}]}},
                        ensure_ascii=False)
    try:
        raw = call_llm(prompt, system=EXTRACT_SYSTEM, json_mode=True, model=model or config.MODEL_SUGGEST,
                       max_tokens=8000, temperature=0.2)
        got = json.loads(raw or "")
    except Exception:
        got = {}
    if isinstance(got, list):                         # a bare list of records
        got = {"records": got}
    recs = []
    for r in got.get("records") or []:
        name = str(r.get("name") or "").strip()
        try:
            lines = ctrl["cards"][int(r.get("card"))]
        except (TypeError, ValueError, IndexError):
            lines = None
        if not lines or name not in "\n".join(lines):     # no index, or counted from 1
            lines = next((c for c in ctrl["cards"] if name in "\n".join(c)), None)
        blob = "\n".join(lines or [])
        if not lines or len(name) < 3 or name not in blob or len(name) > 120:
            continue
        fields = {str(k).strip().lower()[:30]: str(v).strip() for k, v in (r.get("fields") or {}).items()
                  if str(v).strip() and str(v).strip() in blob and str(v).strip() != name and len(str(v)) <= 60}
        recs.append({"name": name, "fields": fields})
    names = [r["name"] for r in recs]
    recs = [r for r in recs if names.count(r["name"]) == 1]
    out = {"entity": str(got.get("entity") or "items")[:40], "records": recs}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    return out


# ── questions ────────────────────────────────────────────────────────────────

def _types(recs):
    """field -> 'num' | 'cat' | 'text' (over records that have it)."""
    out = {}
    fields = sorted({f for r in recs for f in r["fields"]})         # stable order: reproducible sampling
    for f in fields:
        vals = [r["fields"][f] for r in recs if f in r["fields"]]
        if len(vals) < max(3, 0.7 * len(recs)):
            continue
        nums = [number(v) for v in vals]
        if sum(n is not None for n in nums) >= 0.9 * len(vals):
            out[f] = "num"
        elif len(set(vals)) <= max(2, len(vals) // 2) and all(len(v) <= 30 for v in vals):
            out[f] = "cat"
        else:
            out[f] = "text"
    return out


def _arg(op, question, answer, evidence, mention, forbid=(), alternatives=(), **extra):
    h = hashlib.sha1(json.dumps([op, question, answer]).encode()).hexdigest()[:10]
    return {"value": h, "text": question, "op": op, "question": question, "answer": str(answer),
            "alternatives": [str(a) for a in alternatives if str(a) != str(answer)],
            "evidence": list(dict.fromkeys(e for e in evidence if e)), "mention": [m for m in mention if m],
            "forbid": [f for f in forbid if f], **extra}


def questions(recs, entity, *, whole_set, seed, count_entries=False):
    """Candidate questions [arg] over records; `whole_set`: the page shows the complete set
    (no pagination) so questions over all records are well-defined."""
    rng = random.Random(seed)
    types = _types(recs)
    num = [f for f, t in types.items() if t == "num"]
    cat = [f for f, t in types.items() if t == "cat"]
    names = [r["name"] for r in recs]
    small = whole_set and len(recs) <= MAX_SET
    if count_entries:
        return [_arg("count", f"How many {entity} are listed on the page?", len(recs), names, [],
                     alternatives=[_plain(len(recs))])] if small else []
    out = {op: [] for op in ("read", "extremum", "count", "compute", "compare", "verify")}
    for r in rng.sample(recs, min(len(recs), 8)):
        for f, v in rng.sample(sorted(r["fields"].items()), min(2, len(r["fields"]))):
            if f in types and v != r["name"]:
                out["read"].append(_arg("read", f"What is the {f} of {r['name']}?", v, [r["name"], v],
                                        [r["name"]], forbid=[v] if len(v) > 2 else []))
    for f in num:
        rows = [(r, number(r["fields"][f])) for r in recs if number(r["fields"].get(f)) is not None]
        if small and len(rows) == len(recs):
            for word, pick in (("highest", max), ("lowest", min)):
                best = pick(x for _, x in rows)
                win = [r for r, x in rows if x == best]
                if len(win) == 1:
                    out["extremum"].append(_arg("extremum", f"Which of the {entity} has the {word} {f}?", win[0]["name"],
                                                names + [win[0]["fields"][f]], [f], forbid=[win[0]["name"]]))
        if len(rows) >= 2:
            (a, x), (b, y) = rng.sample(rows, 2)
            if x != y:
                big = a if x > y else b
                out["compare"].append(_arg("compare", f"Which has the higher {f}: {a['name']} or {b['name']}?", big["name"],
                                           [a["name"], a["fields"][f], b["name"], b["fields"][f]], [a["name"], b["name"]]))
                samples = [a["fields"][f], b["fields"][f]]
                if _additive(f, samples):
                    q, val = f"What is the combined {f} of {a['name']} and {b['name']}?", x + y
                else:                                   # rates, ratings, scores: a difference, not a sum
                    hi, lo = (a, b) if x > y else (b, a)
                    q, val = f"By how much is the {f} of {hi['name']} higher than that of {lo['name']}?", abs(x - y)
                out["compute"].append(_arg("compute", q, fmt_like(val, samples),
                                           [a["name"], samples[0], b["name"], samples[1]], [a["name"], b["name"]],
                                           alternatives=[_plain(val)]))
            r, x = rng.choice(rows)
            n = number(r["fields"][f])
            thr = round(n * rng.choice((0.8, 0.9, 1.1, 1.25)), 0 if abs(n) >= 10 else 1)
            if thr != n:
                t_txt = fmt_like(thr, [r["fields"][f]])
                out["verify"].append(_arg("verify", f"Is the {f} of {r['name']} above {t_txt}?", "Yes" if n > thr else "No",
                                          [r["name"], r["fields"][f]], [r["name"], t_txt]))
    for f in cat:
        vals = [r["fields"].get(f) for r in recs]
        for v in sorted({x for x in vals if x}):
            k = vals.count(v)
            if small and 1 <= k < len(recs) and all(x is not None for x in vals):
                out["count"].append(_arg("count", f"How many of the {entity} have {f} {v!r}?", k, names, [v],
                                         alternatives=[_plain(k)]))
        r = rng.choice([r for r in recs if r["fields"].get(f)])
        other = rng.choice(sorted({x for x in vals if x}))
        out["verify"].append(_arg("verify", f"Is the {f} of {r['name']} {other!r}?",
                                  "Yes" if r["fields"][f] == other else "No", [r["name"], r["fields"][f]], [r["name"], other]))
    picked = []
    for op, args in out.items():
        rng.shuffle(args)
        seen = set()
        for a in args:
            if a["question"] not in seen and len(seen) < PER_OP:
                seen.add(a["question"])
                picked.append(a)
    for i, a in enumerate(picked):
        a["index"] = i
    return picked


@register
class QAKind(Kind):
    name = "qa"
    macros = {"report_information": "report", "count_entries": "entries"}
    needs_probe = False
    example = '''# example: bring every fact the answer rests on into view, then reply
for text in task["evidence"]:
    el = dom.one(text=text)
    if not el.in_viewport:
        el = act.scroll_into_view(el)
act.answer(task["answer"])
expect.backend()'''

    def discover(self, scan, page, site):
        out = []
        for i, tb in enumerate(scan.get("tables") or []):
            recs = table_records(tb)
            if len(recs) >= 3:
                out.append(self._ctrl("table", i, page, scan, site, css=tb["css"], heading=tb.get("caption") or "",
                                      records=recs, n=tb["n_rows"], headers=tb["headers"],
                                      fingerprint=fingerprint("table", tb)))
        for i, g in enumerate(scan.get("cards") or []):
            if g["n"] >= 3:
                out.append(self._ctrl("cards", i, page, scan, site, css=g["css"], heading=g.get("heading") or "",
                                      cards=g["cards"], n=g["n"], fingerprint=fingerprint("cards", g)))
        return out

    def _ctrl(self, source, i, page, scan, site, **kw):
        ctrl = {"kind": "qa", "role": source, "source": source, "page": page, "page_title": scan["title"],
                "label": kw.get("heading") or scan.get("h1") or scan["title"], "name": source, "id": "",
                "site_id": site, "whole_set": not scan.get("pager") and kw["n"] <= 60, **kw}
        return (("qa", source, _sm()._pattern(page), i), ctrl)

    def static_probe(self, ctrl):
        super().static_probe(ctrl)
        ctrl["usable"] = bool(ctrl.get("records") or ctrl.get("cards"))

    def _records(self, ctrl):
        if ctrl["source"] == "table":
            return ctrl["records"], (ctrl.get("heading") or "rows").strip().lower() or "rows"
        got = card_records(ctrl)
        return got["records"], got["entity"]

    def serves(self, ctrl, macro):
        return macro in self.macros

    def arguments_for(self, ctrl, macro):
        return self.arguments(ctrl, macro)

    def arguments(self, ctrl, macro=None):
        recs, entity = self._records(ctrl)
        if len(recs) < 3:
            return []
        entity = _entity(entity, ctrl)
        seed = f"{ctrl['page']}:{ctrl['css']}"
        both = questions(recs, entity, whole_set=ctrl["whole_set"], seed=seed) + \
            [dict(a, macro="count_entries") for a in questions(recs, entity, whole_set=ctrl["whole_set"], seed=seed,
                                                               count_entries=True)]
        if macro:
            both = [a for a in both if a.get("macro", "report_information") == macro]
        for i, a in enumerate(both):
            a["index"] = i
        return both

    def has_arguments(self, ctrl):
        return bool(ctrl.get("records") or ctrl.get("cards"))

    def element_key(self, ctrl):
        return f"QA {_sm()._pattern(ctrl['page'])} {ctrl['source']} {ctrl['css']}"

    def dedup_value(self, arg):
        return arg["question"]

    def view(self, ctrl):
        v = super().view(ctrl)
        v.pop("options", None)
        v.update({k: ctrl.get(k) for k in ("source", "heading", "whole_set", "site_id", "headers", "n")})
        v["fingerprint"] = ctrl.get("fingerprint")
        return v

    def check(self, ctrl, arg, keep=None):
        return {"kind": "answer", "value": arg["answer"], "alternatives": arg.get("alternatives", []),
                "evidence": arg["evidence"], "requires": None}

    def dry_run(self, t, base, b):
        """Re-read the live page in a fresh session: the record set is the one the questions were
        built from (same fingerprint — so the computed answer still holds) and every evidence
        string is on the page."""
        from datagen import checks
        ctx = B.new_context(b)
        page = ctx.new_page()
        try:
            B.goto_start(page, base + t["start"]["url"])
            B.settle(page)
            c = t["control"]
            scan = page.evaluate(_sm()._SCAN_JS, t["site"])
            group = next((x for x in scan.get("tables" if c["source"] == "table" else "cards") or []
                          if x["css"] == c["css"]), None)
            if group is None:
                return False, f"the {c['source']} is not on the live page"
            if fingerprint(c["source"], group) != c.get("fingerprint"):
                return False, f"the {c['source']} differs from the crawl (live / changing data)"
            text = checks._norm(page.inner_text("body"))
            missing = [e for e in t["option"]["evidence"] if checks._norm(e) not in text]
            if missing:
                return False, f"evidence not on the live page: {missing[:3]}"
            return True, f"answer {t['option']['answer']!r}; {len(t['option']['evidence'])} evidence strings on the page"
        finally:
            ctx.close()

    def describe(self, ctrl):
        return {"type": f"a question answered from the page's {'table' if ctrl['source'] == 'table' else 'list'}"
                        f" {ctrl.get('heading') or ''}".rstrip(),
                "label": ctrl.get("label") or "",
                "note": "ask the question in natural words; keep every name and value it contains exactly; the "
                        "person wants the answer back, so ask for it (do not state it)"}

    def say(self, ctrl, arg):
        return {"question": arg["question"], "reasoning": arg["op"], "reply": "ask the assistant to tell the answer"}

    def mentions(self, arg):
        return arg.get("mention") or []

    def forbidden(self, arg):
        return arg.get("forbid") or ([arg["answer"]] if arg["op"] in ("read", "extremum") else [])

    def step_spec(self, step):
        o = step["option"]
        return [f"QUESTION: {o['question']}",
                f"ANSWER: act.answer({o['answer']!r}) as the LAST action",
                f"EVIDENCE: before answering, make each of these visible on screen (scroll through the "
                f"{'table' if step['control']['source'] == 'table' else 'list'} as needed): {o['evidence'][:30]}"]

    def script_task(self, step):
        o = step["option"]
        return {"subtask": step["subtask"], "question": o["question"], "answer": o["answer"],
                "evidence": o["evidence"], "container_css": step["control"]["css"]}

    def locate(self, driver, step):
        return driver.query(css=step["control"]["css"], limit=1)


def fingerprint(source, group):
    """Identity of a record set's content (table rows / card lines) for the live re-check."""
    body = group.get("rows") if source == "table" else group.get("cards")
    return hashlib.sha1(json.dumps(body, ensure_ascii=False).encode()).hexdigest()[:16]


def _entity(entity, ctrl):
    e = re.sub(r"\s+", " ", str(entity or "")).strip().lower()
    e = re.sub(r"^(your|my|the|all|recent|latest|our)\s+", "", e)
    return e if 2 < len(e) <= 40 and not re.search(r"\d", e) else "items"


def _sm():
    from datagen import sitemap
    return sitemap
