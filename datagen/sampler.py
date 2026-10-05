"""Stage 2 — parameter sampler. Programmatically picks (site, target element, argument,
start state) tuples; diversity is enforced HERE, not by the suggester.

  * train sites only, and only sites whose macro_locations entry lists the macro and whose
    site map has a usable (probed) control of the macro's kind;
  * stratified round-robin across those sites (seeded order), per-site cap, least-used
    control first within a site, options drawn without replacement;
  * dedup key (site, target element, argument) — element = the control's backend identity
    "METHOD path param", stable across re-crawls; keys kept in earlier runs are excluded;
  * start state: `fresh` (the control's page), `preset` (another control on the same listing
    already set via the start URL) or `mid_chain` (a preceding macro on the same page is
    executed first and its actions become the history). The target check then also
    requires that earlier state to survive (`keep`);
  * every tuple is dry-run with privileged calls in a throw-away session: the check must
    FAIL on the start state (not vacuous) and PASS after applying the target (solvable).
"""
from __future__ import annotations

import hashlib
import json
import random
import re
from urllib.parse import urlencode

from datagen import browser as B
from datagen import checks, config, kinds, sitemap

PHRASINGS = ("imperative", "goal", "conversational")


def element_key(ctrl):
    """The control's backend identity (stable across re-crawls), as its kind defines it."""
    return kinds.of(ctrl).element_key(ctrl)


def dedup_key(site, ctrl, option):
    return [site, element_key(ctrl), kinds.of(ctrl).dedup_value(option)]


def _options(ctrl, macro=None):
    return kinds.of(ctrl).arguments_for(ctrl, macro) if macro else kinds.of(ctrl).arguments(ctrl)


def _ctrl_view(ctrl):
    return kinds.of(ctrl).view(ctrl)


def candidate_sites(macro, train, sitemaps):
    from annotation.macro_locations import MACRO_LOCATIONS
    out, dropped = {}, {}
    # a macro no train site lists (its demos are all on held-out sites) may use any train site
    # whose site map has a control serving it
    unlisted = not any(macro in (MACRO_LOCATIONS.get(s) or {}) for s in train)
    for site in train:
        if not unlisted and macro not in (MACRO_LOCATIONS.get(site) or {}):
            continue
        ctrls = [c for c in sitemap.usable_for(sitemaps.get(site), macro) if kinds.of(c).has_arguments(c)]
        if ctrls:
            out[site] = ctrls
        else:
            dropped[site] = "no usable control in site map" if sitemaps.get(site) else "no site map"
    return out, dropped


def _companions(site_ctrls, ctrl):
    """Other usable controls on the same page that hit the same endpoint (for preset / mid-chain)."""
    out = []
    if not kinds.of(ctrl).chainable:
        return out
    for c in site_ctrls:
        if c is ctrl or c["page"] != ctrl["page"] or not c.get("usable") or not kinds.of(c).chainable:
            continue
        if c["signature"]["path"] != ctrl["signature"]["path"] or c["signature"].get("param") == ctrl["signature"].get("param"):
            continue
        if _options(c):
            out.append(c)
    return out


def propose(macro, n, *, train, sitemaps, seed=0, per_site_cap=2, mid_chain_share=0.3, preset_share=0.15,
            exclude_keys=(), prior_site_counts=None, fill=False):
    """Up to `n` unvalidated tuples (the sampler over-draws; the dry run filters).
    `prior_site_counts` {site: n} = trajectories already kept for this macro by earlier runs;
    they count against the per-site cap. Start kinds follow quotas: every prefix of the list
    holds ~mid_chain_share mid-chain and ~preset_share preset tuples (where the page allows)."""
    rng = random.Random(f"{seed}:{macro}")
    cands, dropped = candidate_sites(macro, train, sitemaps)
    sites = sorted(cands)
    rng.shuffle(sites)
    used_keys = {tuple(k) for k in exclude_keys}
    per_site, ctrl_use, out = dict(prior_site_counts or {}), {}, []
    kinds = {"mid_chain": 0, "preset": 0}
    all_ctrls = {s: [c for c in sitemaps[s]["controls"] if c.get("usable")] for s in sites}
    progress, cap = True, per_site_cap
    while len(out) < n and (progress or (fill and cap == per_site_cap)):
        if not progress:                   # fill: the even cap left the macro short; sites with more take it
            cap = 10 ** 6
        progress = False
        for site in sites:
            if len(out) >= n:
                break
            if per_site.get(site, 0) >= cap:
                continue
            ctrls = sorted(cands[site], key=lambda c: (ctrl_use.get(c["control_id"], 0), rng.random()))
            pick = None
            for ctrl in ctrls:
                opts = [o for o in _options(ctrl, macro) if tuple(dedup_key(site, ctrl, o)) not in used_keys]
                if opts:
                    pick = (ctrl, rng.choice(opts))
                    break
            if not pick:
                continue
            ctrl, opt = pick
            used_keys.add(tuple(dedup_key(site, ctrl, opt)))
            per_site[site] = per_site.get(site, 0) + 1
            ctrl_use[ctrl["control_id"]] = ctrl_use.get(ctrl["control_id"], 0) + 1
            i = len(out) + 1
            want = ("mid_chain" if kinds["mid_chain"] < mid_chain_share * i else
                    "preset" if kinds["preset"] < preset_share * i else "fresh")
            t = _make(macro, site, ctrl, opt, all_ctrls[site], rng, want)
            if t["start"]["kind"] != "mid_chain" and want == "mid_chain" and kinds["preset"] < preset_share * i:
                t = _make(macro, site, ctrl, opt, all_ctrls[site], rng, "preset")
            kinds[t["start"]["kind"]] = kinds.get(t["start"]["kind"], 0) + 1
            out.append(t)
            progress = True
    return out, dropped


_LO = re.compile(r"\b(min|minimum|from|low|lower|start)|\bat least\b")
_HI = re.compile(r"\b(max|maximum|high|upper|end|until)|\b(to|at most|up to)\b")


def _bound(ctrl):
    """'lo' / 'hi' for one end of a numeric range pair (Min Price / Max Price, price_from / price_to), else None."""
    s = re.sub(r"[_\-\[\]]", " ", f"{ctrl.get('name') or ''} {ctrl.get('label') or ''}").lower()
    lo, hi = bool(_LO.search(s)), bool(_HI.search(s))
    return "lo" if lo and not hi else "hi" if hi and not lo else None


def _consistent(ctrl, opt, other, o2):
    """A preset / prefix on the other end of the same range must leave it non-empty: min < max. 2026-09-29: a
    preset Min Price above the task's Max Price gave an empty listing and a self-contradicting task."""
    a, b = _bound(ctrl), _bound(other)
    if not a or not b or a == b:
        return True
    try:
        v, w = float(opt["value"]), float(o2["value"])
    except (TypeError, ValueError, KeyError):
        return True
    return v < w if a == "lo" else w < v


def _make(macro, site, ctrl, opt, site_ctrls, rng, want="fresh"):
    start = {"kind": "fresh", "url": ctrl["page"], "keep": {}}
    comps = [c for c in _companions(site_ctrls, ctrl) if any(_consistent(ctrl, opt, c, o) for o in _options(c))]
    if comps and want == "mid_chain":
        other = rng.choice(comps)
        o2 = rng.choice([o for o in _options(other) if _consistent(ctrl, opt, other, o)])
        start = {"kind": "mid_chain", "url": ctrl["page"], "keep": {other["signature"]["param"]: o2["value"]},
                 "prefix": {"macro": kinds.macro_of(other), "control": _ctrl_view(other),
                            "option": o2}}
    elif comps and want == "preset" and ctrl["page"].rstrip("/") == ctrl["signature"]["path"].rstrip("/"):
        other = rng.choice([c for c in comps if c["signature"]["method"] == "GET"] or comps)
        o2 = rng.choice([o for o in _options(other) if _consistent(ctrl, opt, other, o)])
        if other["signature"]["method"] == "GET":
            q = {other["signature"]["param"]: o2["value"]}
            start = {"kind": "preset", "url": ctrl["page"] + "?" + urlencode(q), "keep": q,
                     "preset": {"control": _ctrl_view(other), "option": o2}}
    key = dedup_key(site, ctrl, opt)
    pid = "p-" + hashlib.sha1(json.dumps([macro, key, start["kind"], start.get("keep")]).encode()).hexdigest()[:10]
    return {"param_id": pid, "macro": macro, "site": site, "control": _ctrl_view(ctrl), "option": opt,
            **({"op": opt["op"]} if opt.get("op") else {}),
            "start": start, "phrasing": rng.choice(PHRASINGS), "dedup_key": key,
            "check": kinds.of(ctrl).check(ctrl, opt, keep=start["keep"])}


# ── feasibility dry run (privileged) ──────────────────────────────────────────

def _pin_status(chk, entries):
    """Record the status class the successful request had (see checks._status_class_ok)."""
    if chk.get("kind") != "request":
        return
    ok = [e for e in entries if checks._accepted(e) and (e.get("method") or "GET").upper() == chk["method"]
          and checks._path(e.get("path")) == checks._path(chk["path"])
          and checks._carries(e, {**chk.get("params", {}), **chk.get("keep", {})})]
    if ok and str(ok[-1].get("status", ""))[:1] == "3":
        chk["status"] = "3xx"


def _weak_check(t, before, after=(), changes=None):
    """A check that can pass without the task being done (the flash judge caught these, 2026-09-28):
    None when the check is sound, else the reason to drop the task."""
    chk = t["check"]
    if chk.get("kind") != "request":
        return None
    want = {**chk.get("params", {}), **chk.get("keep", {})}
    # a rejected login / registration re-renders the form (200) and changes nothing; other POSTs (tools,
    # joins, shares, uploads) legitimately answer 200 without a data change
    if chk["method"] == "POST" and not chk.get("response") and \
            (t.get("macro") in ("sign_by_text", "authenticate_by_form", "create_by_form", "toggle_relationship")
             or re.search(r"/(login|signin|sign-in|register|signup|sign-up)\b", chk["path"])):
        hits = [e for e in after if checks._accepted(e) and (e.get("method") or "").upper() == "POST"
                and checks._path(e.get("path")) == checks._path(chk["path"]) and checks._carries(e, want)]
        redirected = any(str(e.get("status", ""))[:1] == "3" for e in hits)
        if hits and not redirected and changes is not None and not changes:
            return ("weak check: the submission shows no success (no redirect, no data change): a rejected "
                    "form re-renders the same way (invalid login, username taken)")
    if chk["method"] == "GET" and not want and "/api/" in chk["path"]:
        return "weak check: a parameterless background API request (polling happens without the action)"
    if chk["method"] == "GET" and not want and any(checks._path(e.get("path")) == checks._path(chk["path"]) for e in before):
        return "weak check: the start state already makes this request"
    from datagen import formvalues as FV
    typed = {FV.field_key(f) for f in (t["control"].get("fields") or [])
             if (f.get("type") or "text") in ("text", "textarea", "search", "email", "")}
    texts = [v for k, v in ((t.get("option") or {}).get("values") or {}).items()
             if k in typed and isinstance(v, str) and len(v.strip()) > 12 and " " in v.strip()]
    carried = json.dumps(want, ensure_ascii=False)
    missing = [v for v in texts if v.strip() not in carried]
    if missing:
        return f"weak check: typed text never reaches the checked request ({missing[0][:40]!r})"
    return None




def _oracle_once(t, base, b):
    """One privileged run of an oracle step in a fresh session: its evidence
    {entry, requests, changes, clipboard, downloads}."""
    ctx = B.new_context(b)
    page = ctx.new_page()
    downloads = []
    page.on("download", lambda dl: downloads.append({"filename": dl.suggested_filename, "url": dl.url}))
    try:
        kinds.of(t["control"]).setup(ctx, base, t["control"], t["option"])
        B.goto_start(page, base + t["start"]["url"])
        before = B.session_log(ctx, base)
        where = kinds.of(t["control"]).changes_site(t)
        ch0 = B.session_changes(ctx, base, where) or []
        ctrl = t["control"] | {"form": {"submit": t["control"].get("apply_button")}} if t["control"]["kind"] != "form" else dict(t["control"])
        e, _k, _m, _new = sitemap.apply_privileged(page, ctrl, t["option"], base, ctx, len(before))
        after = B.session_log(ctx, base)
        ch1 = B.session_changes(ctx, base, where) or []
        return {"entry": e, "requests": after[len(before):], "changes": [c for c in ch1 if c not in ch0],
                "clipboard": B.clipboard_writes(ctx, base), "downloads": downloads}
    finally:
        ctx.close()


def _stabilize(chk, changes2):
    """Keep only the expected fields a second, independent run reproduces (drops per-request
    values such as confirmation codes). None if an expected change did not recur at all."""
    out = []
    for want in chk["expect"]:
        same = [c for c in changes2 if c["collection"] == want["collection"] and c["op"] == want["op"]
                and (want["item_id"] is None or str(c["item_id"]) == str(want["item_id"]))]
        if not same:
            return None
        best = max(same, key=lambda c: sum(checks._essential(c).get(k) == v for k, v in want["fields"].items()))
        ess = checks._essential(best)
        out.append(dict(want, fields={k: v for k, v in want["fields"].items() if ess.get(k) == v}))
    return dict(chk, expect=out)


def dry_run_oracle(t, base, b):
    """(feasible, detail) for kinds whose check is recorded: run the step twice (fresh sessions),
    record what it changed (else the request it sent), keep what both runs agree on."""
    kind = kinds.of(t["control"])
    ev1 = _oracle_once(t, base, b)
    req1, ch1 = ev1["requests"], ev1["changes"]
    chk = kind.observed_check(ev1, t["site"], t["control"])
    if chk is None:
        return False, "the step changed nothing observable (no data change, request, clipboard or download)"
    if chk["kind"] != "state":
        t["check"] = chk
        ok, detail = checks.evaluate(chk, req1, ch1, ev1["clipboard"])
        return (True, detail) if ok else (False, "the recorded check does not pass its own run: " + detail)
    ch2 = _oracle_once(t, base, b)["changes"]
    stable = _stabilize(chk, ch2)
    if stable is None:
        return False, "the step's data change did not recur in a second run (unstable)"
    t["check"] = stable
    ok1, detail = checks.evaluate(stable, req1, ch1)
    ok2, detail2 = checks.evaluate(stable, [], ch2)
    if ok1 and ok2:
        return True, detail
    return False, "the recorded check does not pass its own runs: " + (detail if not ok1 else detail2)


def dry_run(t, base, b):
    """(feasible, detail). Privileged select_option/clicks in a throw-away session."""
    try:
        own = kinds.of(t["control"]).dry_run(t, base, b)
    except Exception as exc:
        return False, f"dry-run error {type(exc).__name__}: {str(exc)[:160]}"
    if own is not None:
        return own
    if getattr(kinds.of(t["control"]), "oracle", False):
        try:
            return dry_run_oracle(t, base, b)
        except Exception as exc:
            return False, f"dry-run error {type(exc).__name__}: {str(exc)[:160]}"
    ctx = B.new_context(b)
    page = ctx.new_page()
    try:
        kinds.of(t["control"]).setup(ctx, base, t["control"], t["option"])
        B.goto_start(page, base + t["start"]["url"])
        if t["start"]["kind"] == "mid_chain":
            pre = t["start"]["prefix"]
            n0 = len(B.session_log(ctx, base))
            e, _k, _m, _new = sitemap.apply_privileged(page, pre["control"] | {"form": {"submit": pre["control"].get("apply_button")}},
                                                       pre["option"], base, ctx, n0)
            if not e:
                return False, "prefix step produced no request"
        before = B.session_log(ctx, base)
        ok0, _ = checks.evaluate(t["check"], before)
        if ok0:
            return False, "vacuous: the start state already satisfies the check"
        ctrl = t["control"] | {"form": {"submit": t["control"].get("apply_button")}}
        if ctrl["kind"] in ("link", "chips"):
            ctrl["key"] = ctrl["signature"]["param"]
        e, _k, _m, _new = sitemap.apply_privileged(page, ctrl, t["option"], base, ctx, len(before))
        after = B.session_log(ctx, base)
        ok1, detail = checks.evaluate(t["check"], after)
        if not ok1:
            return False, "not solvable by applying the control: " + detail
        weak = _weak_check(t, before, after, B.session_changes(ctx, base))
        if weak:
            return False, weak
        _pin_status(t["check"], after)
        return True, detail
    except Exception as exc:
        return False, f"dry-run error {type(exc).__name__}: {str(exc)[:160]}"
    finally:
        ctx.close()


def sample(macro, n, *, train, sitemaps, bases, workers=4, seed=0, overdraw=3, log=print, **kw):
    """(feasible[:n], infeasible, dropped sites, spare feasible) — fewer than n if candidates run out."""
    import queue
    import threading
    proposed, dropped = propose(macro, n * overdraw, train=train, sitemaps=sitemaps, seed=seed, **kw)
    # keep the stratified order: validate in order, stop once n are feasible
    results = [None] * len(proposed)
    todo = queue.Queue()
    for i, t in enumerate(proposed):
        todo.put(i)
    lock = threading.Lock()
    state = {"ok": 0}

    def worker(wi):
        with B.browser() as b:
            while True:
                with lock:
                    if state["ok"] >= n:
                        return
                try:
                    i = todo.get_nowait()
                except queue.Empty:
                    return
                ok, detail = dry_run(proposed[i], bases[wi % len(bases)], b)
                results[i] = (ok, detail)
                with lock:
                    state["ok"] += ok
    threads = [threading.Thread(target=worker, args=(w,), daemon=True) for w in range(max(1, workers))]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    feasible, infeasible = [], []
    for t, r in zip(proposed, results):
        if r is None:
            continue
        t["feasibility"] = r[1]
        (feasible if r[0] else infeasible).append(t)
    # workers validate in parallel, so a few extra feasible tuples may exist: keep the first n
    # in stratified order, the rest are returned as `spare` (feasible, unused)
    feasible, spare = feasible[:n], feasible[n:]
    log(f"sample {macro}: validated {len(feasible) + len(spare) + len(infeasible)}, feasible "
        f"{len(feasible) + len(spare)} (using {len(feasible)}), infeasible {len(infeasible)}, "
        f"sites dropped {len(dropped)}")
    return feasible, infeasible, dropped, spare
