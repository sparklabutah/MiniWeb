"""Free augmentations of the replay (no API calls; the memory model is the local base model).

The MiniWeb validation failures of cycle 3 (2026-09-29) had two causes the plain replay cannot teach:
every kept trajectory is a clean success (the student declared success although its own memory said the
step had failed), and 97% of the episodes are one macro long (it stopped after the first macro of a
WebArena task). Two variants of kept trajectories address them, graded by the same gates as any replay:

recovery  one kept trajectory with one mistake injected right before a correctable op of its macro, then
          the correct op:
            input (a text field)  -> a near-miss of the right text first, then the right text (cleared)
            select                -> another option of the same dropdown first
            slider (a click on an input[type=range]) -> a click a fifth of the track away first
          The mistake's row is kept out of training (row["inject"]), and so are the rows before it (a copy
          of the plain replay, row["aug_prefix"]); the next step's memory is asked to notice the mistake
          on the screen (replay.RECOVERY_HINT).
chain     two kept trajectories of one site as one episode, both macros, the instruction merged by the memory
          model (values checked, else joined), graded by both parts' gates. Two ways to reach the second
          one's start page: the same page (the first stays on it: on-page filters, sorts, reactions), or the
          site's home page (the second starts there; the student clicks the site's own home link between).
"""
from __future__ import annotations

import hashlib
import json
import random
import re
from collections import defaultdict
from urllib.parse import urlsplit

from webmix import replay as R

# ── recovery ──────────────────────────────────────────────────────────────────

NO_NEAR_MISS = {"date", "time", "datetime-local", "month", "week", "color", "range", "password"}


def near_miss(text, seed):
    """A plausible slip on `text`: another last digit of a number, two swapped letters of its longest word,
    else its last character dropped. None when no slip changes it."""
    rng = random.Random(seed)
    t = text or ""
    digits = [i for i, ch in enumerate(t) if ch.isdigit()]
    if re.fullmatch(r"\s*[-+]?[\d.,]+\s*", t) and digits:
        i = digits[-1]
        return t[:i] + str((int(t[i]) + rng.randint(1, 8)) % 10) + t[i + 1:]
    words = sorted(re.finditer(r"[A-Za-z]{4,}", t), key=lambda m: -len(m.group(0)))
    for m in words[:1]:
        w = m.group(0)
        ks = [k for k in range(1, len(w) - 2) if w[k] != w[k + 1]]
        if ks:
            k = rng.choice(ks)
            return t[:m.start()] + w[:k] + w[k + 1] + w[k] + w[k + 2:] + t[m.end():]
    return t[:-1] if len(t) > 3 else None


def _eligible(op, task):
    el = op.get("el") or {}
    ty = (el.get("type") or "").lower()
    if op["op"] == "input":
        return (R._is_text_field(el) and ty not in NO_NEAR_MISS and len(op.get("text") or "") >= 3
                and task["control"]["kind"] != "reveal")
    if op["op"] == "select":
        return bool(R._css(el))
    if op["op"] == "click":
        return (el.get("tag") or "").lower() == "input" and ty == "range" and bool(el.get("box")) and bool(op.get("point"))
    return False


def inject_mistake(plan, task, seed):
    """-> a copy of `plan` with one mistake before an eligible op of the macro's own (last) segment, the op
    itself marked as the recovery; raises R.Unsupported when the plan has no such op."""
    last = max((op["segment"] for op in plan), default=0)
    cands = [i for i, op in enumerate(plan) if op["segment"] == last and _eligible(op, task)]
    if not cands:
        raise R.Unsupported("no correctable op to inject a mistake before")
    i = cands[int(hashlib.sha1(str(seed).encode()).hexdigest(), 16) % len(cands)]
    right = dict(plan[i], recover=True)
    if right["op"] == "input":
        wrong_text = near_miss(right["text"], seed)
        if not wrong_text or wrong_text == right["text"]:
            raise R.Unsupported("no near miss for the typed text")
        wrong = dict(right, text=wrong_text, inject=True, recover=False,
                     what=f'it typed "{wrong_text}" instead of "{right["text"]}"')
        right["select_all"] = True                 # the field now holds the wrong text: replace it
    elif right["op"] == "select":
        wrong = dict(right, text="", right=right["text"], inject=True, recover=False)   # chosen live (Replayer)
    else:                                          # a slider click, a fifth of the track to the other side
        x0, y0, w = right["el"]["box"][0], right["point"][1], right["el"]["box"][2]
        fx = (right["point"][0] - x0) / (w or 1)
        fx2 = fx - 0.2 if fx > 0.5 else fx + 0.2
        wrong = dict(right, point=[x0 + fx2 * w, y0], inject=True, recover=False,
                     what="it clicked the slider's track at the wrong spot, so the slider shows a different value "
                          "than the task asks for")
    out = [dict(op, aug_prefix=True) for op in plan[:i]] + [wrong, right] + [dict(op) for op in plan[i + 1:]]
    return out


# ── chains ────────────────────────────────────────────────────────────────────

# macros whose trajectory leaves the browser on the page it started from (a GET reload of the same path or
# an in-page request), so a second trajectory recorded from that page can follow
CHAIN_FIRST = {"filter_by_dropdown", "filter_by_options", "filter_by_slider", "filter_by_date_range", "sort_by_form",
               "feedback_by_react", "toggle_relationship", "feedback_by_star"}
CHAIN_SECOND = CHAIN_FIRST | {"search", "export", "copy_content", "share_by_form"}

MERGE_ASK = ("Rewrite these requests to a web assistant as ONE natural request that asks for the first and then the "
             "second, in that order. Keep every name, label, number and value exactly as written; add nothing.\n"
             "1. {a}\n2. {b}\nReply with the merged request only.")


def _path(url):
    return urlsplit(url or "").path.rstrip("/") or "/"


def _stays(traj, start):
    """Every recorded step happened on the start page (no navigation, no answer)."""
    if traj.get("history") or traj.get("history_macro"):
        return False
    for s in traj.get("steps") or []:
        a = s["action"]
        if a["type"] in ("goto", "new_tab", "switch_tab", "answer") or _path(a.get("url")) != start:
            return False
    return True


def chain_candidates(items, per_page=3, limit=None, seed=0):
    """items: [(task_id, task_dir)] of kept trajectories (their plain replays passed) -> [(dir_a, dir_b)].
    Pairs start on the same page of one site, act on different controls, and the first stays on the page."""
    groups = defaultdict(list)
    for tid, d in items:
        try:
            traj = json.loads((d / "trajectory.json").read_text())
        except OSError:
            continue
        if traj.get("start_kind") != "fresh" or traj.get("history_macro"):
            continue
        task = R.load_task(d.parent.parent.name, tid)
        if task["start"].get("keep") or task["check"].get("kind") == "answer":
            continue
        start = _path(task["start"]["url"])
        groups[(traj["site"], start)].append({"dir": d, "traj": traj, "task": task, "start": start})
    rng, out = random.Random(seed), []
    for key in sorted(groups):
        g = groups[key]
        pairs = [(a, b) for a in g for b in g
                 if a is not b and a["traj"]["macro"] in CHAIN_FIRST and b["traj"]["macro"] in CHAIN_SECOND
                 and a["task"]["control"].get("control_id") != b["task"]["control"].get("control_id")
                 and not _scope(a["task"]) & _scope(b["task"]) and _stays(a["traj"], a["start"])]
        rng.shuffle(pairs)
        # prefer pairs of two different macros, then distinct first trajectories
        pairs.sort(key=lambda p: p[0]["traj"]["macro"] == p[1]["traj"]["macro"])
        used, n = set(), 0
        for a, b in pairs:
            if n >= per_page or a["traj"]["id"] in used or b["traj"]["id"] in used:
                continue
            used |= {a["traj"]["id"], b["traj"]["id"]}
            out.append((a["dir"], b["dir"]))
            n += 1
    rng.shuffle(out)
    return out[:limit] if limit else out


# a second part that starts on the home page must not need a special session (datagen prepare flags / cart)
_FLAGGED = {"authenticate_by_form", "pay_by_form", "checkout_by_form", "book_by_form"}


def _scope(task):
    """(site, collection) pairs a part's state check watches: two parts changing one table fail each other's
    'no other changes' rule (2026-09-30: two votes on one forum page)."""
    c = task.get("check") or {}
    if c.get("kind") != "state":
        return set()
    return {(c.get("site"), x) for x in (c.get("scope") or [e.get("collection") for e in c.get("expect") or []])}


def _answers(traj):
    return any(s["action"]["type"] == "answer" for s in (traj.get("steps") or []) + (traj.get("history") or []))


def home_chain_candidates(items, per_second=3, limit=None, seed=0):
    """items as for chain_candidates -> [(dir_a, dir_b)]: b starts fresh on its site's home page, a is any
    other trajectory of that site that does not answer a question (it may end anywhere on the site)."""
    firsts, seconds = defaultdict(list), []
    for tid, d in items:
        try:
            traj = json.loads((d / "trajectory.json").read_text())
        except OSError:
            continue
        task = R.load_task(d.parent.parent.name, tid)
        if _answers(traj) or task["check"].get("kind") == "answer" or task["start"]["kind"] == "mid_chain":
            continue
        rec = {"dir": d, "traj": traj, "task": task}
        firsts[traj["site"]].append(rec)
        ctrl = task["control"]
        if (task["start"]["kind"] == "fresh" and _path(task["start"]["url"]) == f"/sites/{traj['site']}"
                and not task["start"].get("keep") and ctrl.get("role") not in _FLAGGED and not (ctrl.get("prep") or {})):
            seconds.append(rec)
    rng, out = random.Random(seed), []
    for b in sorted(seconds, key=lambda r: r["traj"]["id"]):
        pool = [a for a in firsts[b["traj"]["site"]]
                if a is not b and a["task"]["control"].get("control_id") != b["task"]["control"].get("control_id")
                and not _scope(a["task"]) & _scope(b["task"])]
        rng.shuffle(pool)
        pool.sort(key=lambda a: a["traj"]["macro"] == b["traj"]["macro"])      # other macros first
        out += [(a["dir"], b["dir"]) for a in pool[:per_second]]
    rng.shuffle(out)
    return out[:limit] if limit else out


def task_chain_candidates(items, lengths=(2, 3, 4), n_chains=2400, max_uses=2, seed=0):
    """Review round 1, A2 (2026-10-05, user-approved): TASK-CENTRIC episodes built from the same kept trajectories as
    the skill-centric set, to compare skill- and task-centric data with the sites, pipeline and states held fixed.
    One episode = k (2-4) trajectories of one site under one merged instruction. A part may follow the previous one
    when, as in the two-part chains, either (same page) both start on the same page, the previous one stays on it
    and is an on-page change (CHAIN_FIRST) and this one is a CHAIN_SECOND macro, or (home) this one starts fresh on
    the site's home page with no special session (the student clicks the site's own home link first, see
    replay_chain(always_home=True)). No part answers a question; parts act on different controls and watch disjoint
    (site, collection) scopes, differing in macro where possible. A trajectory joins at most `max_uses` episodes.
    items as for chain_candidates -> [tuple of dirs]."""
    recs = defaultdict(list)
    for tid, d in items:
        try:
            traj = json.loads((d / "trajectory.json").read_text())
        except OSError:
            continue
        task = R.load_task(d.parent.parent.name, tid)
        if _answers(traj) or task["check"].get("kind") == "answer" or task["start"]["kind"] == "mid_chain":
            continue
        start = _path(task["start"]["url"])
        ctrl = task["control"]
        home = (task["start"]["kind"] == "fresh" and start == f"/sites/{traj['site']}" and not task["start"].get("keep")
                and ctrl.get("role") not in _FLAGGED and not (ctrl.get("prep") or {}))
        page = (task["start"]["kind"] == "fresh" and not task["start"].get("keep") and not traj.get("history_macro"))
        query = bool(urlsplit(task["start"]["url"] or "").query)
        linkable = (page and not home and not query and ctrl.get("role") not in _FLAGGED and not (ctrl.get("prep") or {}))
        recs[traj["site"]].append({"dir": d, "traj": traj, "task": task, "start": start, "home": home,
                                   "page": page, "stays": page and _stays(traj, start), "linkable": linkable})

    def can_follow(a, b):
        if b["home"]:
            return True
        if (b["page"] and a["stays"] and a["start"] == b["start"] and a["traj"]["macro"] in CHAIN_FIRST
                and b["traj"]["macro"] in CHAIN_SECOND):
            return True
        # (link) b starts fresh on another page of the site: the student clicks the home link, then the home page's
        # own link to b's page (replay_chain; an episode whose page has no such link fails its replay and is dropped)
        return b["linkable"]

    rng, uses, out, seen = random.Random(seed), defaultdict(int), [], set()
    sites = sorted(recs)
    fails = 0
    while len(out) < n_chains and fails < 50000:
        site = rng.choice(sites)
        k = rng.choice(lengths)
        pool = [a for a in recs[site] if uses[a["traj"]["id"]] < max_uses]
        if len(pool) < k:
            fails += 1
            continue
        chain = [rng.choice(pool)]
        for _ in range(k - 1):
            cand = [b for b in pool if can_follow(chain[-1], b)
                    and all(b["traj"]["id"] != c["traj"]["id"]
                            and b["task"]["control"].get("control_id") != c["task"]["control"].get("control_id")
                            and not _scope(b["task"]) & _scope(c["task"]) for c in chain)]
            if not cand:
                break
            other = [b for b in cand if b["traj"]["macro"] not in {c["traj"]["macro"] for c in chain}]
            chain.append(rng.choice(other or cand))
        key = tuple(c["traj"]["id"] for c in chain)
        if len(chain) < k or key in seen:
            fails += 1
            continue
        seen.add(key)
        for c in chain:
            uses[c["traj"]["id"]] += 1
        out.append(tuple(c["dir"] for c in chain))
    return out


def _values(text):
    """Names and values an instruction must keep: numbers, quoted strings, Capitalized word runs."""
    vals = set(re.findall(r"\d[\d,.:/-]*\d|\d", text))
    vals |= {m.strip() for m in re.findall(r"[\"'“‘]([^\"'”’]{2,60})[\"'”’]", text)}
    return {v for v in vals if v}


async def merge_instructions(a, b):
    """-> one instruction asking for a then b: the memory model's rewrite when it keeps every value of both,
    else the two joined."""
    joined = a.rstrip() + (" " if a.rstrip().endswith((".", "?", "!")) else ". ") + "After that: " + b.strip()
    if not R.MEMORY_LLM:
        return joined, "joined"
    try:
        r = await R.MEMORY_LLM["client"].chat.completions.create(
            model=R.MEMORY_LLM["model"], temperature=0, max_completion_tokens=200,
            messages=[{"role": "user", "content": MERGE_ASK.format(a=a, b=b)}])
        text = R._clean((r.choices[0].message.content or "").strip().strip('"'))
    except Exception:
        return joined, "joined"
    need = _values(a) | _values(b)
    if text and all(v in text for v in need) and len(text) <= len(a) + len(b) + 80:
        return text, "merged"
    return joined, "joined"


def chain_id(dirs, prefix="chain"):
    """accepted/<task id> dirs -> the chain episode's id ("tchain-..." for the task-centric episodes of round 1 A2)."""
    ids = [d.name for d in dirs]
    site = json.loads((dirs[0] / "trajectory.json").read_text())["site"]
    return f"{prefix}-{site}-" + hashlib.sha1("+".join(ids).encode()).hexdigest()[:10]


async def replay_chain(dirs, base, out_root=R.OUT_DIR, headless=True, log=print, always_home=False, variant="chain"):
    """Replay kept trajectories one after another as one episode (see chain_candidates). always_home (task-centric
    chains): the student clicks the site's home link before every later part that starts on the home page, even when
    the part before also started there (it may end anywhere); a part on the previous one's page needs no link."""
    parts = [R.load_part(d, base) for d in dirs]
    ids = [p["traj"]["id"] for p in parts]
    eid = chain_id(dirs, "tchain" if variant == "taskchain" else "chain")
    plan, seg0 = [], 0
    try:
        for k, p in enumerate(parts):
            ops = R.build_plan(p["traj"], p["elements"])
            if k < len(parts) - 1:
                ops = [op for op in ops if op["op"] != "done"]
            ops = [dict(op, segment=op["segment"] + seg0) for op in ops]
            start, prev = _path(p["task"]["start"]["url"]), parts[k - 1] if k else None
            starts_home = start == f"/sites/{p['traj']['site']}"
            same_page = prev is not None and start == _path(prev["task"]["start"]["url"]) and _stays(prev["traj"], start)
            if k and always_home and not starts_home and not same_page:
                # task-centric chains: back to the home page, then the site's own link to this part's page
                ops = [{"op": "home", "segment": ops[0]["segment"], "macro": ops[0]["macro"], "site": p["traj"]["site"]},
                       {"op": "link", "segment": ops[0]["segment"], "macro": ops[0]["macro"], "path": start}] + ops
            elif k and ((always_home and starts_home) or (not always_home and start
                                                          != _path(parts[k - 1]["task"]["start"]["url"]))):
                # the next part starts on the site's home page: its own home link gets there
                ops.insert(0, {"op": "home", "segment": ops[0]["segment"], "macro": ops[0]["macro"],
                               "site": p["traj"]["site"]})
            plan += ops
            seg0 = max(op["segment"] for op in plan) + 1
    except R.Unsupported as e:
        return {"task_id": eid, "variant": variant, "parts": ids, "ok": False, "error": f"unsupported: {e}", "steps": 0}
    instruction = parts[0]["task"]["instruction"]
    for p in parts[1:]:
        instruction, how = await merge_instructions(instruction, p["task"]["instruction"])
    spec = {"id": eid, "variant": variant, "parts": parts, "instruction": instruction, "plan": plan}
    res = await R.replay_episode(spec, base, out_root, headless, log)
    res["instruction_by"] = how
    return res
