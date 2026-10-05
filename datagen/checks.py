"""Expected backend checks for generated tasks.

A check is built from the control's probed backend signature (never by an LLM), so it
is exact: the request the site receives when the option is applied.

    {"kind": "request", "method": "GET", "path": "/sites/e-commerce/",
     "params": {"category": "Sports & Outdoors"},   # what the step must set
     "keep":   {"sort": "price_asc"},               # state that must survive (mid-chain / preset)
     "final":  true}                                 # the LAST request to that path still has it

`evaluate` reads a session request log (/_admin/log entries). It passes when an accepted
request carries params+keep AND (final) the last accepted request to the same endpoint
still does — so "filter applied, then cleared" fails. The same check is also emitted as
an `evaluation/verifiers.py` spec (request_made), so generated tasks can be graded by the
evaluation machinery and `verify_task` is the reused gate.

A `state` check is for steps that change data (toggles, reactions, deletes, forms). It is
recorded by the privileged dry run — the session's effective data changes after the step
(/_admin/changes: rows inserted / updated / deleted vs the base tables) — and passes when
an attempt's changes contain each expected change AND nothing else changed in those
collections (so a like-then-unlike, a different item, or extra deletes fail):

    {"kind": "state", "site": "forums",
     "expect": [{"collection": "posts", "op": "update", "item_id": "127582", "fields": {"score": "41322"}}],
     "scope": ["posts"],                       # collections where any other change fails the step
     "request": {"method": "POST", "path": "/sites/forums/api/posts/127582/vote"}}   # for verify_task

An `answer` check is for steps that end by replying to the human (report_information,
count_entries, search_by_playback, …). The expected answer is computed by the privileged
sampler, never by an LLM; the reply is graded by the evaluation harness's answer chain, and
every `evidence` string (the facts the answer rests on) must have been readable in the
viewport at one of the recorded screenshots — so the trajectory shows where the answer came
from. `requires` optionally adds a request/state check that must also hold (a 2FA reveal):

    {"kind": "answer", "value": "12", "alternatives": ["twelve"], "evidence": ["Oak Street", "$1,200"],
     "requires": null}
"""
from __future__ import annotations

import re
from urllib.parse import urlencode


def _norm(v):
    return re.sub(r"\s+", " ", str(v if v is not None else "")).strip().casefold()


def _path(p):
    return (p or "").rstrip("/") or "/"


def build_check(signature, value, keep=None, final=True):
    return {"kind": "request", "method": (signature.get("method") or "GET").upper(),
            "path": signature["path"], "params": {signature["param"]: value},
            "keep": dict(keep or {}), "final": bool(final)}


def _fields(entry):
    f = {}
    f.update(entry.get("query") or {})
    if isinstance(entry.get("body"), dict):
        f.update({k: v for k, v in entry["body"].items() if not isinstance(v, dict)})
    return f


def _same(got, want):
    """A logged field matches the wanted value; a repeated field (list) matches a wanted
    value it contains, or a wanted list with the same members; {"value": [lo, hi], "mode":
    "between"} is a numeric range (a drop position anywhere inside a region)."""
    if isinstance(want, dict) and want.get("mode") == "between":
        try:
            return float(want["value"][0]) <= float(got) <= float(want["value"][1])
        except (TypeError, ValueError, IndexError):
            return False
    if isinstance(want, (list, tuple)):
        return isinstance(got, list) and sorted(map(_norm, got)) == sorted(map(_norm, want))
    if isinstance(got, list):
        return _norm(want) in map(_norm, got)
    return _norm(got) == _norm(want)


def _carries(entry, want):
    f = _fields(entry)
    return all(k in f and _same(f[k], v) for k, v in want.items())


def _answered(resp, want):
    """A JSON response holds `want` (strings compared per line without trailing blanks)."""
    if not isinstance(resp, dict):
        return False
    norm = lambda v: "\n".join(l.rstrip() for l in str(v).rstrip().split("\n")) if isinstance(v, str) else v
    return all(k in resp and norm(resp[k]) == norm(v) for k, v in want.items())


_LOGIN_PATH = re.compile(r"/(login|signin|sign-in|sign_in|auth)\b", re.I)


def _bounced_to_login(e, entries):
    """A request answered with a redirect straight to a login page was refused (a follow while signed out)."""
    if str(e.get("status", ""))[:1] != "3" or _LOGIN_PATH.search(e.get("path") or ""):
        return False
    try:
        i = entries.index(e)
    except ValueError:
        return False
    nxt = next((x for x in entries[i + 1:i + 3] if (x.get("method") or "GET").upper() == "GET"), None)
    return bool(nxt and _LOGIN_PATH.search(nxt.get("path") or ""))


def _status_class_ok(e, cls):
    """A request check may pin the status class its dry run succeeded with ("3xx": a form that redirects
    on success re-renders with 200 on failure, e.g. "Invalid password", "Username already taken")."""
    return not cls or str(e.get("status", ""))[:1] == str(cls)[:1]


def _accepted(e):
    return isinstance(e.get("status"), int) and 200 <= e["status"] < 400


# fields that change as a side effect of any write: ignored when comparing states
INCIDENTAL = re.compile(r"(^|_)(date|time|timestamp|created|updated|modified|last_seen|last_active|last_login|"
                        r"seen|viewed|views|view_count|visits|updated_at|created_at|modified_at|ts|at|"
                        r"read|is_read|unread|unread_count|read_at)$", re.I)   # opening a chat marks it read


def _canon(v):
    from app.db import _canon as canon
    return canon(v)


ANY = "*"          # an expected field value: present and non-empty (drawn images, generated media)


def _essential(change):
    """The fields that identify a change: for an insert its content (not its generated id or
    timestamps), for an update the changed fields (not bookkeeping ones). Drawn images and other
    data: URIs are execution-specific pixels: only their presence counts."""
    if change["op"] == "delete":
        return {}
    fields = {k: v[1] for k, v in change["changed"].items() if not INCIDENTAL.search(k)}
    if change["op"] == "insert":
        fields.pop("id", None)
    return {k: (ANY if isinstance(v, str) and v.startswith("data:image/") else _canon(_images(v))) for k, v in fields.items()}


def _images(v):
    """Nested drawn images (a signature inside a stored form) compare as present, not as pixels."""
    if isinstance(v, str) and v.startswith("data:image/"):
        return ANY
    if isinstance(v, list):
        return [_images(x) for x in v]
    if isinstance(v, dict):                           # nested records: their timestamps are incidental too
        return {k: _images(x) for k, x in v.items() if not INCIDENTAL.search(str(k))}
    return v


def _field_ok(got, want):
    want = _images(want)                               # checks recorded before images became ANY
    return bool(got) and got not in ("", "0") if want == ANY else got == want


_DATE_IN_VALUE = re.compile(r"(?<!\d)(20\d\d)-?(0[1-9]|1[0-2])-?(0[1-9]|[12]\d|3[01])(?!\d)")
_MONTHS = {m: i for i, m in enumerate(("january", "february", "march", "april", "may", "june", "july", "august",
                                        "september", "october", "november", "december"), 1)}


def _mentioned_dates(texts):
    """ISO dates a task's text asks for, in any of the usual spellings."""
    out = set()
    for t in texts:
        t = str(t or "")
        out |= {f"{y}-{m}-{d}" for y, m, d in _DATE_IN_VALUE.findall(t)}
        out |= {f"{y}-{int(m):02d}-{int(d):02d}" for m, d, y in re.findall(r"\b(\d{1,2})/(\d{1,2})/(20\d\d)\b", t)}
        for mon, d, y in re.findall(r"\b([A-Za-z]{3,9})\.? (\d{1,2})(?:st|nd|rd|th)?,? (20\d\d)\b", t):
            m = next((i for name, i in _MONTHS.items() if name.startswith(mon.lower())), None)
            if m:
                out.add(f"{y}-{m:02d}-{int(d):02d}")
        for d, mon, y in re.findall(r"\b(\d{1,2}) ([A-Za-z]{3,9}),? (20\d\d)\b", t):
            m = next((i for name, i in _MONTHS.items() if name.startswith(mon.lower())), None)
            if m:
                out.add(f"{y}-{m:02d}-{int(d):02d}")
    return out


def relax_recorded_dates(check, texts):
    """A state check written on day D expects the server's "today" where the site stamps one (last_used,
    date_submitted, ids like AV-20260928-00001, PMT-20260928-027) and so fails on any later day. An expected
    value carrying a date the task never mentions becomes ANY; dates the task asks for stay exact."""
    if check.get("kind") != "state":
        return check
    asked = _mentioned_dates(texts)

    def fix(v):
        if isinstance(v, dict):
            return {k: fix(x) for k, x in v.items()}
        if isinstance(v, list):
            return [fix(x) for x in v]
        if isinstance(v, str) and any(f"{y}-{m}-{d}" not in asked for y, m, d in _DATE_IN_VALUE.findall(v)):
            return ANY
        return v
    return {**check, "expect": [{**e, "fields": fix(e.get("fields") or {})} for e in check.get("expect") or []]}


def state_check(changes, site, requests=()):
    """A state check from the dry run's observed changes (None when nothing changed)."""
    expect = []
    for c in changes:
        if c["site"] != site:
            continue
        ess = _essential(c)
        if c["op"] != "delete" and not ess:
            continue                                   # only bookkeeping changed
        expect.append({"collection": c["collection"], "op": c["op"],
                       "item_id": None if c["op"] == "insert" else c["item_id"], "fields": ess})
    if not expect:
        return None
    muts = [e for e in requests if (e.get("method") or "GET").upper() != "GET"
            and isinstance(e.get("status"), int) and 200 <= e["status"] < 400]
    req = {"method": muts[-1]["method"], "path": muts[-1]["path"]} if muts else None
    return {"kind": "state", "site": site, "expect": expect, "scope": sorted({x["collection"] for x in expect}),
            "request": req}


def _evaluate_state(check, changes):
    if changes is None:
        return False, "no data-change log for this session"
    mine = [c for c in changes if c["site"] == check["site"] and c["collection"] in check["scope"]]
    mine = [c for c in mine if c["op"] == "delete" or _essential(c)]
    unmatched = list(mine)
    for want in check["expect"]:
        hit = next((c for c in unmatched if c["collection"] == want["collection"] and c["op"] == want["op"]
                    and (want["item_id"] is None or str(c["item_id"]) == str(want["item_id"]))
                    and all(_field_ok(_essential(c).get(k), v) for k, v in want["fields"].items()
                            if not INCIDENTAL.search(k))), None)
        if hit is None:
            seen = [(c["collection"], c["item_id"], c["op"], _essential(c)) for c in mine][:4]
            return False, (f"expected {want['op']} in {want['collection']}"
                           f"{' #' + str(want['item_id']) if want['item_id'] else ''} with {want['fields']}; "
                           f"changes there: {seen or 'none'}")
        unmatched.remove(hit)
    if unmatched:
        extra = [(c["collection"], c["item_id"], c["op"]) for c in unmatched][:4]
        return False, f"other changes in {check['scope']} as well: {extra}"
    return True, "data changes match: " + "; ".join(f"{w['op']} {w['collection']}" for w in check["expect"])


def describe(check):
    """One line for the executor prompt: what expect.backend() will look for."""
    if check.get("kind") == "answer":
        need = f" (after: {describe(check['requires'])})" if check.get("requires") else ""
        return (f"act.answer({check['value']!r}) — and each of {check.get('evidence') or []} readable on screen "
                f"in at least one screenshot before or at the answer{need}")
    if check.get("kind") == "clipboard":
        return f"the page's copy control put {check['value'][:80]!r} on the clipboard"
    if check.get("kind") == "state":
        parts = [f"{w['op']} {w['collection']}{' #' + str(w['item_id']) if w['item_id'] else ''} {w['fields'] or ''}"
                 for w in check["expect"]]
        return "the site's data changes exactly as: " + "; ".join(parts) + " (and nothing else there)"
    want = {**check.get("params", {}), **check.get("keep", {})}
    return f"{check['method']} {check['path']} carrying {want}"


def _evaluate_clipboard(check, clip):
    if clip is None:
        return False, "no clipboard log for this session"
    strip = lambda v: re.sub(r"^https?://[^/\s]+", "", _norm(v))      # the server's origin differs per run
    want = strip(check["value"])
    if any(strip(v) == want for v in clip):
        return True, "clipboard holds the expected text"
    return False, f"clipboard writes: {[str(v)[:40] for v in clip[-3:]] or 'none'}; expected {check['value'][:60]!r}"


def seen_all(evidence, seen):
    """(ok, missing): every evidence string appears in the text of some recorded viewport."""
    views = [_norm(v) for v in seen or ()]
    missing = [e for e in evidence or () if not any(_norm(e) in v for v in views)]
    return not missing, missing


def _evaluate_answer(check, entries, changes, answer, seen):
    if answer is None:
        return False, "no answer was given (act.answer)"
    from evaluation.verifiers import _grade_answer
    ok, why = _grade_answer(answer, [check["value"], *check.get("alternatives", [])], check.get("pattern"))
    if not ok:
        return False, f"answer {str(answer)[:80]!r} rejected ({why}); expected {check['value']!r}"
    ok, missing = seen_all(check.get("evidence"), seen)
    if not ok:
        return False, f"answer right but never shown on screen: {missing[:4]}"
    if check.get("requires"):
        ok, detail = evaluate(check["requires"], entries, changes)
        if not ok:
            return False, "answer right but the required step is missing: " + detail
    return True, f"answer {str(answer)[:60]!r} ({why}); evidence seen"


def evaluate(check, entries, changes=None, clip=None, answer=None, seen=None):
    """(passed, detail) over a session request log (state checks: its data changes; clipboard
    checks: the texts the page wrote to the clipboard; answer checks: the reply and the
    viewport texts of the recorded screenshots)."""
    if check and check.get("kind") == "answer":
        return _evaluate_answer(check, entries, changes, answer, seen)
    if check and check.get("evidence") and seen is not None:     # the step must also have SHOWN these
        ok, detail = evaluate({k: v for k, v in check.items() if k != "evidence"}, entries, changes, clip, answer, seen)
        if ok:
            shown, missing = seen_all(check["evidence"], seen)
            if not shown:
                return False, f"{detail}; but never on screen before: {missing[:4]}"
        return ok, detail
    if check and check.get("kind") == "state":
        return _evaluate_state(check, changes)
    if check and check.get("kind") == "clipboard":
        return _evaluate_clipboard(check, clip)
    if not check or check.get("kind") != "request":
        return False, "no check"
    method, path = check["method"], _path(check["path"])
    want = {**check.get("params", {}), **check.get("keep", {})}
    hits = [e for e in entries if _accepted(e) and (e.get("method") or "GET").upper() == method
            and _path(e.get("path")) == path and _status_class_ok(e, check.get("status"))]
    carriers = [e for e in hits if _carries(e, want) and not _bounced_to_login(e, entries)]
    if check.get("response"):                         # what the server answered (a program's output)
        carriers = [e for e in carriers if _answered(e.get("response"), check["response"])]
    if not carriers:
        seen = [f"{e.get('method')} {e.get('path')}?{urlencode(e.get('query') or {}, doseq=True)}" for e in hits[-3:]]
        return False, f"no {method} {path} carrying {want}; last requests there: {seen or 'none'}"
    if check.get("final", True) and not _carries(hits[-1], want):
        return False, (f"{want} was applied but the last {method} {path} no longer carries it "
                       f"(query={hits[-1].get('query')})")
    e = carriers[-1]
    return True, f"{e.get('method')} {e.get('path')}?{urlencode(e.get('query') or {}, doseq=True)} [{e.get('status')}]"


def verifier_spec(task_id, macro, check):
    """The same expectation as an evaluation/verifiers.py task verifier. A state check becomes
    the mutating request that produced the change (verify_task has no data-change view)."""
    if check.get("kind") == "clipboard":
        # a copied link carries the server's origin, which differs per run: compare its route
        value = re.sub(r"^https?://[^/\s]+(?=/)", "", check["value"])
        leaf = {"type": "action_included", "action": "clipboard_write", "value": value, "label": "copied"}
        return {"task_id": task_id, "macros": {macro: {"op": "AND", "checks": [leaf]}}}
    if check.get("kind") == "answer":
        leaf = {"type": "answer_matches", "expected": check["value"], "label": "answer"}
        if check.get("alternatives"):
            leaf["alternatives"] = list(check["alternatives"])
        leaves = [leaf] + [{"type": "action_included", "action": a, "label": f"{a} performed"} for a in check.get("actions") or []]
        if check.get("requires"):
            leaves += verifier_spec(task_id, macro, check["requires"])["macros"][macro]["checks"]
        return {"task_id": task_id, "macros": {macro: {"op": "AND", "checks": leaves}}}
    if check.get("kind") == "state" and check.get("typed"):
        # data outside the sites' request log (the simulated file system): the value the agent typed
        leaf = {"type": "action_included", "action": "type", "value": check["typed"], "label": "typed"}
        return {"task_id": task_id, "macros": {macro: {"op": "AND", "checks": [leaf]}}}
    if check.get("kind") == "state":
        req = check.get("request")
        leaf = ({"type": "request_made", "method": req["method"], "url": req["path"], "label": "backend gate"} if req
                else {"type": "request_made", "url": "re:^/sites/" + re.escape(check["site"]) + r"(/|$|\?)",
                      "label": "site reached"})     # any page of the site (an exact root visit is not required)
        return {"task_id": task_id, "macros": {macro: {"op": "AND", "checks": [leaf]}}}
    want = {**check.get("params", {}), **check.get("keep", {})}
    if (check.get("multi") or any(isinstance(v, dict) for v in want.values())) and check["method"] == "GET" and want:
        # a numeric band ({"mode": "between"}) is not a URL value: the pattern pins the path and the other
        # params; checks.evaluate enforces the band itself
        url = "re:" + re.escape(check["path"]) + r"/?\?" + "".join(
            _param_lookahead(k, v) for k, v in want.items() if not isinstance(v, (list, tuple, dict)))
    else:
        url = check["path"] + ("?" + urlencode(want, doseq=True) if check["method"] == "GET" else "")
    leaf = {"type": "request_made", "method": check["method"], "url": url, "label": "backend gate"}
    if check["method"] != "GET" and want:
        leaf["body_fields"] = want
    if check.get("response"):
        leaf["response_fields"] = check["response"]
    return {"task_id": task_id, "macros": {macro: {"op": "AND", "checks": [leaf]}}}


def _param_lookahead(key, value):
    """Regex lookahead: `key` carries `value` in the query — alone, repeated, or comma-joined."""
    from urllib.parse import quote_plus
    v = re.escape(quote_plus(str(value))).replace(r"\+", r"(\+|%20)")
    return rf"(?=(.*&)?{re.escape(key)}=([^&]*(,|%2C))?{v}(&|,|%2C|$))"          # placed right after the "?"


def run_verifier(spec, entries, action_events=(), answer=""):
    """verify_task over (recorded actions + the server log as network events)."""
    from evaluation.trajectory import merge_server_log
    from evaluation.verifiers import verify_task
    traj = merge_server_log(list(action_events), entries)
    return verify_task(spec, traj, answer=answer or "")


def gate(check, spec, entries, action_events=(), changes=None, clip=None, answer=None, seen=None):
    """The backend gate used by the filter: our final-state check AND the reused verifier."""
    ok1, detail = evaluate(check, entries, changes, clip, answer, seen)
    report = run_verifier(spec, entries, action_events, answer)
    ok = ok1 and report["passed"]
    if ok1 and not report["passed"]:
        detail = "verify_task disagreed: " + str(report.get("by_macro"))
    return ok, detail, report
