"""Trajectory verifiers.

A trajectory is a list of dicts, each tagged with "type":

    action      {type, action, target, selector, url, value/text, option_text, ...}
    observation {type, url, title, snapshot, axtree_json, ...}
    network     {type, method, url, status, requestBody, ...}

A verifier spec is JSON: a list of checks, each scoped to a macro (or to the
whole task) and naming one check type plus its arguments.

    {
      "task_id": "remote-calls_707134",
      "checks": [
        {"macro": "select_by_dropdown", "type": "action_included",
         "action": "select", "target": "Status", "value": "completed"},

        {"macro": "extract_by_query", "type": "answer_matches",
         "expected": "Priya Sharma", "mode": "fuzzy"},

        {"macro": "extract_by_query", "type": "answer_grounded",
         "url": "/sites/remote-calls/meetings"},

        {"type": "page_visited", "url": "/meetings"},

        {"type": "request_made", "method": "POST", "url": "/event/create",
         "status": 200}
      ]
    }

Run it (per-task macro verifier — {task_id, macros: {macro: AND/OR check tree}}):

    from evaluation.verifiers import verify_task
    report = verify_task(spec, trajectory, answer="Priya Sharma")
    report["passed"]        -> bool
    report["by_macro"]      -> {macro: passed}
    report["macros"]        -> per-macro nested check results

Adding a check type = subclass Check, set `type`, implement run(). Nothing else.
"""
from __future__ import annotations

import contextvars
import re

# The task instruction (the question the agent was asked), made available to the
# fuzzy LLM judge without threading it through every check's run() signature.
# Set per-call by verify_task; a ContextVar so parallel grading stays isolated.
_QUESTION = contextvars.ContextVar("verifier_question", default="")

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _norm(s) -> str:
    """Lowercase, collapse whitespace, drop punctuation — for loose matching."""
    s = str(s or "").lower()
    s = re.sub(r"[^a-z0-9\s.]+", " ", s)
    return " ".join(s.split())


def _parse_body(raw):
    """A request body -> dict. Handles JSON objects and urlencoded form data."""
    if isinstance(raw, dict):
        return raw
    s = str(raw or "").strip()
    if not s:
        return {}
    if s[0] in "{[":
        try:
            import json as _json
            d = _json.loads(s)
            return d if isinstance(d, dict) else {}
        except ValueError:
            pass
    if "=" in s:  # a=1&b=2
        from urllib.parse import parse_qs
        return {k: (v[0] if len(v) == 1 else v) for k, v in parse_qs(s).items()}
    return {}


def _compact(s) -> str:
    """Normalized, with spaces/dashes stripped — so identifier values that differ
    only in formatting compare equal (card '4539 1337 5013 4821' == '4539133750134821',
    phone '(555) 123-4567' == '5551234567')."""
    return re.sub(r"[\s\-]+", "", _norm(s))


def _numeric_value(s):
    """Return a float if the string is essentially a single number (optionally with
    a currency symbol / short unit / thousands separators), else None. So '80',
    '$52', '388.013581', '52 mph', '1,240' parse; 'Cascade Kitchen', '2026-07-15'
    (dashes → not a bare number) and 'ORD-123' do not."""
    t = str(s or "").strip()
    if not t:
        return None
    if re.fullmatch(r"[-+$€£¥]?\s*\d{1,3}(?:,\d{3})*(?:\.\d+)?\s*[a-zA-Z%/]{0,6}", t) or \
       re.fullmatch(r"[-+$€£¥]?\s*\d+(?:\.\d+)?\s*[a-zA-Z%/]{0,6}", t):
        m = re.search(r"-?\d[\d,]*(?:\.\d+)?", t)
        if m:
            try:
                return float(m.group().replace(",", ""))
            except ValueError:
                return None
    return None


def _num_close(a, b):
    """Two numbers agree within 1% (or 0.01), or agree once rounded to int."""
    return abs(a - b) <= max(0.01, abs(a) * 0.01) or round(a) == round(b)


_NUMBER_WORDS = {
    "no": 0, "none": 0, "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12,
}


def _expected_number(expected):
    """The numeric value the EXPECTED answer denotes, if it is essentially a
    count/number — a bare number ('5', '$52', '388.01'), a LEADING number token
    ('5 spam emails' → 5), or a LEADING zero-word ('Zero spam mails', 'No results'
    → 0). Returns None for text answers and for names that merely contain a number
    word ('One Medical' → None, since 'one' isn't the leading count), so those go
    through text / fuzzy matching instead of being matched as numbers.

    Restricting word→number to LEADING zero-words is deliberate: a count of none is
    commonly written out ('zero'/'no'/'none'), whereas 1–12 as words are too often
    names or ordinals to safely treat as numbers."""
    v = _numeric_value(expected)
    if v is not None:
        return v
    toks = _norm(expected).split()
    if not toks:
        return None
    if re.fullmatch(r"-?\d[\d,]*(?:\.\d+)?", toks[0]):
        try:
            return float(toks[0].replace(",", ""))
        except ValueError:
            return None
    if _NUMBER_WORDS.get(toks[0]) == 0:  # leading zero-word only
        return 0.0
    return None


def _field_match(want, got) -> bool:
    """Match one expected body-field value against the observed one, robustly.

    - explicit form {"value": v, "mode": "equals|contains|numeric|fuzzy"} honors the mode
    - both sides numeric        → numeric-tolerant (rounding-safe)
    - multi-word text           → CONTAINS (compact substring) — so a review that
                                  embeds a mandated sentence, or a message body, passes
    - single token / id / date  → compact-equal (ids stay strict, formatting-tolerant)
    - mode "fuzzy"              → LLM judge (same mechanism as report_information's
                                  answer check): does the submitted text satisfy the
                                  expected content? For free-text form fields (messages,
                                  reviews, bios) where substring matching is too brittle.
    An OPEN value ({open:true}) always matches (not asserted).
    """
    mode = "auto"
    if isinstance(want, dict) and "value" in want and "open" not in want:
        mode, want = want.get("mode", "auto"), want["value"]
    if isinstance(want, dict) and want.get("open") is True:
        return True
    if mode == "fuzzy":
        # cheap paths first: exact/containment short-circuit the LLM call
        nw0, ng0 = _compact(want), _compact(got)
        if nw0 and (nw0 == ng0 or nw0 in ng0):
            return True
        ok, _why = _judge_alignment(str(got), str(want), "submitted form field")
        return ok
    wn, gn = _numeric_value(want), _numeric_value(got)
    if mode == "numeric" or (mode == "auto" and wn is not None and gn is not None):
        return wn is not None and gn is not None and _num_close(wn, gn)
    nw, ng = _compact(want), _compact(got)
    if mode == "equals":
        return nw == ng
    if mode == "contains":
        return nw in ng
    # auto: multi-word expected → contains; single token → equal (formatting-tolerant)
    if re.search(r"\s", str(want).strip()):
        return bool(nw) and nw in ng
    return nw == ng


def _dict_subset(want: dict, got: dict) -> bool:
    """Every field in `want` matches in `got` (see `_field_match`). Extra fields in
    `got` (csrf, timestamps, session ids) are ignored."""
    for k, v in (want or {}).items():
        if not _field_match(v, got.get(k)):
            return False
    return True


def _actions(traj):
    return [e for e in traj if e.get("type") == "action"]


def _observations(traj):
    return [e for e in traj if e.get("type") == "observation"]


def _network(traj):
    return [e for e in traj if e.get("type") == "network"]


# ---------------------------------------------------------------------------
# base
# ---------------------------------------------------------------------------


class Check:
    """One assertion over a trajectory. Subclasses set `type` and implement run()."""

    type = ""

    def __init__(self, spec: dict):
        self.spec = spec
        self.macro = spec.get("macro", "")

    def run(self, traj: list, answer: str) -> tuple[bool, str]:
        """Return (passed, reason)."""
        raise NotImplementedError

    # -- convenience -------------------------------------------------------
    def arg(self, key, default=None):
        v = self.spec.get(key, default)
        # an unfilled OPEN param ({open: true}) is treated as not-asserted
        if isinstance(v, dict) and v.get("open") is True:
            return default
        return v

    def result(self, passed, reason=""):
        return {
            "type": self.type,
            "macro": self.macro,
            "passed": bool(passed),
            "reason": reason,
            "spec": self.spec,
        }


# ---------------------------------------------------------------------------
# QA checks — did the agent produce the right answer, from the right place?
# ---------------------------------------------------------------------------


class AnswerMatches(Check):
    """The agent's answer matches the expected one.

    mode: "exact" | "includes" (default) | "fuzzy"
      includes — expected appears inside the answer (normalized)
      fuzzy    — same, but also accepts any string in `alternatives`
    """

    type = "answer_matches"

    def run(self, traj, answer):
        expected = self.arg("expected", "")
        mode = self.arg("mode", "includes")
        alts = self.arg("alternatives", []) or []
        got, want = _norm(answer), _norm(expected)

        if not got:
            return False, "agent gave no answer"

        if mode == "exact":
            ok = got == want
        else:
            candidates = [want] + [_norm(a) for a in alts]
            ok = any(c and c in got for c in candidates)

        return ok, f"expected {expected!r}, got {answer!r}"


class AnswerGrounded(Check):
    """The answer was available where the agent was looking.

    Checks that the last observation before the end of the trajectory (i.e. the
    page the agent answered from) is the expected page — and, if `text` is
    given, that the text actually appears in that page's HTML.
    """

    type = "answer_grounded"

    def run(self, traj, answer):
        obs = _observations(traj)
        if not obs:
            return False, "no observations in trajectory"
        last = obs[-1]

        want_url = self.arg("url", "")
        if want_url and want_url not in (last.get("url") or ""):
            return False, f"answered from {last.get('url')!r}, expected {want_url!r}"

        text = self.arg("text", "")
        if text:
            page = last.get("snapshot", "") or ""
            if _norm(text) not in _norm(page):
                return False, f"{text!r} not present on the page the agent answered from"

        return True, f"answered from {last.get('url')!r}"


# ---------------------------------------------------------------------------
# Frontend checks — did the agent interact with the page as instructed?
# ---------------------------------------------------------------------------


class ActionIncluded(Check):
    """An action of the given kind, on the given component, is in the trajectory.

    Matches on action type + target (substring, normalized) + optional value.
    Target/selector are matched loosely on purpose: recorded selectors are often
    bare tags ("a", "select") and carry little information, while `target` is the
    human-readable description ("select 'Status' = 'Completed'").
    """

    type = "action_included"

    def run(self, traj, answer):
        want_action = self.arg("action", "")
        want_target = _norm(self.arg("target", ""))
        want_value = _norm(self.arg("value", ""))
        want_selector = self.arg("selector", "")

        for a in _actions(traj):
            if want_action and a.get("action") != want_action:
                continue
            if want_target and want_target not in _norm(a.get("target")):
                continue
            if want_selector and want_selector != a.get("selector"):
                continue
            if want_value:
                got = _norm(a.get("value") or a.get("text") or a.get("option_text"))
                if want_value not in got:
                    continue
            return True, f"found {a.get('action')} on {a.get('target', '')[:60]!r}"

        return False, (f"no {want_action or 'action'} matching "
                       f"target={self.arg('target')!r} value={self.arg('value')!r}")


class PageVisited(Check):
    """The agent was on a page whose URL contains the given fragment."""

    type = "page_visited"

    def run(self, traj, answer):
        want = self.arg("url", "")
        urls = [e.get("url", "") for e in traj if e.get("url")]
        for u in urls:
            if want in u:
                return True, f"visited {u!r}"
        return False, f"never visited a URL containing {want!r}"


# ---------------------------------------------------------------------------
# Backend check — did the agent's interaction reach the server?
# ---------------------------------------------------------------------------


class RequestMade(Check):
    """A network request matching method/url (and optionally status, body) exists."""

    type = "request_made"

    def run(self, traj, answer):
        want_method = (self.arg("method", "") or "").upper()
        want_url = self.arg("url", "")
        want_status = self.arg("status")
        want_body = self.arg("body_contains", "")
        want_fields = self.arg("body_fields")  # dict subset compare
        want_resp = self.arg("response_fields")  # dict subset compare on the RESPONSE
        # (server-emitted detector signals, e.g. {"signed_zone": "taxpayer-signature"})

        for n in _network(traj):
            nurl = n.get("url") or ""
            if want_method and (n.get("method") or "").upper() != want_method:
                continue
            if want_url:
                # 're:<pattern>' matches the URL by regex — lets the endpoint be
                # pinned while a volatile resource id (/note/2/ vs /note/1/) is not.
                if want_url.startswith("re:"):
                    if not re.search(want_url[3:], nurl):
                        continue
                elif want_url not in nurl:
                    continue
            if want_status is not None and n.get("status") != want_status:
                continue
            if want_body and _norm(want_body) not in _norm(n.get("requestBody")):
                continue
            if want_fields and not _dict_subset(want_fields, _parse_body(n.get("requestBody"))):
                continue
            if want_resp and not _dict_subset(want_resp, _parse_body(n.get("responseBody"))):
                continue
            return True, f"{n.get('method')} {n.get('url')} -> {n.get('status')}"

        return False, (f"no {want_method or 'request'} to {want_url!r}"
                       + (f" with status {want_status}" if want_status is not None else "")
                       + (f" carrying {want_fields}" if want_fields else "")
                       + (f" answering {want_resp}" if want_resp else ""))


class ReasoningContains(Check):
    """The agent's FINAL reasoning arrives at the expected answer.

    Two ways to pass:
      1. the expected value appears in the final reasoning (substring), or
      2. mode 'fuzzy' (default): an LLM judges the reasoning is toward / consistent
         with the expected answer — catches equivalent phrasings (a name vs its
         email, "the maximum, 5" vs "5") that a substring test misses.

    Human trajectories carry no reasoning; by the perfect-trace assumption they
    pass. This is the default QA check: the agent's reasoning is more honest than
    a separately-reported answer, which is often absent in chained tasks.
    """

    type = "reasoning_contains"

    # reasoning fields that may appear inline on non-reasoning events; the
    # dedicated {type:"reasoning"} event is handled separately. NOT "text" —
    # that's the typed-input field on action events, not reasoning.
    _FIELDS = ("reasoning", "thought", "thinking", "memory", "next_goal",
               "evaluation_previous_goal", "model_output")

    def _final_reasoning(self, traj):
        """The last reasoning chunk in the trajectory (agent's concluding thought)."""
        chunks = []
        for e in traj:
            if e.get("type") == "reasoning" and e.get("text"):
                chunks.append(str(e["text"]))
                continue
            for k in self._FIELDS:
                if e.get(k):
                    chunks.append(str(e[k]))
        return chunks[-1] if chunks else ""

    def run(self, traj, answer):
        expected = self.arg("expected", "")
        mode = self.arg("mode", "fuzzy")
        if not expected:
            return True, "no expected value set"
        reasoning = self._final_reasoning(traj)
        if not reasoning:
            return True, "no reasoning trace (human) — assumed perfect"
        if _norm(expected) in _norm(reasoning):
            return True, "final reasoning contains the expected answer"
        if mode == "contains":
            return False, f"{expected!r} not in final reasoning"
        return _judge_alignment(reasoning, expected, "final reasoning")  # fuzzy


def _judge_alignment(text, expected, kind="output", question=None):
    """LLM judge: does `text` correctly answer the task, given the expected answer?

    The TASK (the question the agent was asked) is included when available so the
    judge can resolve context-dependent equivalence — e.g. for "how many spam
    emails?" it knows "no spam" and "0" are the same answer. Falls back to the
    plain expected-vs-answer comparison when no question is in context."""
    try:
        from app.llm import call_llm
    except Exception:
        return False, "LLM unavailable for fuzzy check"
    import json as _json
    q = (question if question is not None else _QUESTION.get()) or ""
    system = (
        f"You grade an agent's {kind} for a web task. Given the TASK the user asked, the "
        f"EXPECTED answer, and the agent's {kind}, decide whether the agent correctly "
        "answers the task — i.e. its answer arrives at, contains, or is equivalent to the "
        "expected answer. Judge equivalence IN THE CONTEXT OF THE TASK: equivalent "
        "phrasings match (a name vs its email; 'the maximum, 5' vs '5'; 'no spam' vs '0'; "
        "a rounded vs exact figure that agrees). Extra commentary is fine as long as the "
        "correct answer is present and unambiguous. "
        'Reply ONLY JSON: {"match": true|false, "why": "<short reason>"}.')
    payload = {"expected_answer": str(expected),
               "agent_" + kind.replace(" ", "_"): str(text)[:4000]}
    if q:
        payload = {"task": str(q)[:1000], **payload}
    prompt = _json.dumps(payload)
    import os as _os
    judge_model = _os.environ.get("VERIFIER_JUDGE_MODEL", "gemini-3.5-flash")
    raw = call_llm(prompt, system=system, max_tokens=300, temperature=0.0,
                   json_mode=True, model=judge_model)
    if not raw:
        return False, "LLM unavailable for fuzzy check"
    try:
        d = _json.loads(raw)
        return bool(d.get("match")), "LLM judge: " + str(d.get("why", ""))[:100]
    except (ValueError, TypeError):
        return False, "LLM judge returned malformed output"


def _match_answer(answer, expected, mode):
    """Compare a reported answer to the expected value.

    Order: template-placeholder pattern → substring → numeric-tolerant (so a
    correctly-rounded '388' matches an expected '388.013581') → fuzzy (LLM).
    """
    got = str(answer or "").strip()
    if not got:
        return False, "no reported answer"
    # expected carries a placeholder like '#ORD-{YYYYMMDD}-001' → match as a pattern,
    # ignoring punctuation/spacing so '#ORD-{YYYYMMDD}-001' matches 'ORD-20260810-001'
    if "{" in str(expected) and "}" in str(expected):
        marker = "\x00"
        e = re.sub(r"\{[^}]*\}", marker, str(expected))
        e = re.sub(r"[^a-z0-9\x00]+", "", e.lower())
        g = re.sub(r"[^a-z0-9]+", "", got.lower())
        pat = re.escape(e).replace(re.escape(marker), ".+")
        if e and re.search(pat, g):
            return True, "reported answer matches the expected pattern"
    ng, ne = _norm(got), _norm(expected)

    # 1) WHOLE-WORD containment — the answer restates the expected value/phrase.
    # Anchored on alphanumeric boundaries (lookarounds, robust to trailing
    # punctuation) so it is precise: '5' can't match '15', 'SkyLine' can't match
    # 'SkyLiner', 'cat' can't match 'category' — yet 'Zero spam mails' matches
    # 'Zero spam mails' and 'Priya Sharma' matches 'contact Priya Sharma.'.
    core = re.sub(r"^[^a-z0-9]+|[^a-z0-9]+$", "", ne)
    if core and re.search(r"(?<![a-z0-9])" + re.escape(core) + r"(?![a-z0-9])", ng):
        return True, "answer contains the expected value"

    # 2) NUMERIC (tolerant) — the answer expresses the number differently: rounding
    # ('388' for '388.013581'), separators ('1240' for '1,240'), units ('$52' → 52),
    # or a digit for a word count ('0' for 'Zero spam mails'). Match digit tokens
    # only (never a loose substring); a word-only answer is left to the task-aware
    # judge so a stray 'no'/'one' in prose can't false-match.
    en = _expected_number(expected)
    if en is not None:
        for m in re.findall(r"-?\d[\d,]*(?:\.\d+)?", got):
            try:
                if _num_close(en, float(m.replace(",", ""))):
                    return True, "answer's number matches the expected value"
            except ValueError:
                pass
        if mode == "contains":
            return False, f"no number equal to {expected!r} in the answer"
        return _judge_alignment(got, expected, "reported answer")

    if mode == "contains":
        return False, f"{expected!r} not in reported answer"
    return _judge_alignment(got, expected, "reported answer")


class QAAnswer(Check):
    """Conditional QA check, resolved per task by the macro graph:

      * LEAF (terminal) macro — its output is the deliverable, so check the
        REPORTED answer against expected.
      * chained macro (feeds a downstream macro) — the value isn't reported, so
        check the agent's REASONING trace instead.

    `leaf` is injected per task from macro_edges (a macro with no outgoing edge is
    a leaf). If unset, tries the reported answer, then falls back to reasoning.

    `alternatives` (list, or comma/newline-separated string) are equally valid
    answers — e.g. a threshold question where two values both satisfy the
    condition; matching ANY candidate passes.
    """

    type = "qa_answer"

    def run(self, traj, answer):
        expected = self.arg("expected", "")
        mode = self.arg("mode", "fuzzy")
        leaf = self.arg("leaf", None)
        alts = self.arg("alternatives", []) or []
        if isinstance(alts, str):
            alts = [a.strip() for a in re.split(r"[,;\n]", alts) if a.strip()]
        candidates = [c for c in [expected, *alts] if c]
        if not candidates:
            return True, "no expected value set"

        def match_any(fn):
            ok, why = False, "no candidates"
            for cand in candidates:
                ok, why = fn(cand)
                if ok:
                    return ok, why
            return ok, why

        def reasoning():
            return match_any(lambda c: ReasoningContains(
                {"expected": c, "mode": mode}).run(traj, answer))

        # chained: the value is never reported — check the reasoning trace.
        if leaf is False:
            ok, why = reasoning()
            return ok, "chained → reasoning: " + why

        # leaf (terminal): the reported answer IS the deliverable — check it, and
        # a MISSING answer is a failure (an agent that reports nothing must not
        # pass). Do NOT fall back to reasoning here, or an empty answer would pass
        # vacuously via the human perfect-trace assumption.
        if leaf is True:
            if not str(answer or "").strip():
                return False, "terminal → no reported answer"
            ok, why = match_any(lambda c: _match_answer(answer, c, mode))
            return ok, "terminal → answer: " + why

        # leaf unknown: try the reported answer; with none recorded (e.g. a human
        # gold with no saved answer) fall back to reasoning (passes humans by the
        # perfect-trace assumption, checks the agent's reasoning otherwise).
        if str(answer or "").strip():
            ok, why = match_any(lambda c: _match_answer(answer, c, mode))
            return ok, "terminal? → answer: " + why
        ok, why = reasoning()
        return ok, "unknown-leaf, no answer → reasoning: " + why


# ---------------------------------------------------------------------------
# registry + entry point
# ---------------------------------------------------------------------------

CHECKS = {c.type: c for c in (
    AnswerMatches,
    AnswerGrounded,
    ActionIncluded,
    PageVisited,
    RequestMade,
    ReasoningContains,
    QAAnswer,
)}


def _run_node(node: dict, traj: list, answer: str) -> dict:
    """Evaluate a template node: a group {op, checks:[...]} (arbitrarily nested)
    or a leaf {type, ...}. Returns a nested result dict."""
    if isinstance(node, dict) and "op" in node:
        op = (node.get("op") or "AND").upper()
        kids = [_run_node(c, traj, answer) for c in (node.get("checks") or [])]
        # advisory children are evaluated + reported but do NOT gate the verdict
        # (frontend affordance confirms the right solution was used; the backend
        # gate decides pass/fail). If EVERY child is advisory, fall back to all so
        # the group can't pass vacuously.
        gating = [k for k in kids if not k.get("advisory")] or kids
        if op == "OR":
            passed = any(k["passed"] for k in gating) if gating else False
        else:
            passed = all(k["passed"] for k in gating) if gating else True
        res = {"op": op, "passed": passed, "checks": kids, "advisory": bool(node.get("advisory"))}
        if node.get("label"):
            res["label"] = node["label"]
        return res

    cls = CHECKS.get(node.get("type"))
    if cls is None:
        return {"type": node.get("type"), "label": node.get("label", ""), "passed": False,
                "advisory": bool(node.get("advisory")),
                "reason": f"unknown check type {node.get('type')!r}", "spec": node}
    check = cls(node)
    try:
        passed, reason = check.run(traj, answer)
    except Exception as exc:  # a broken check is a failed check, not a crash
        passed, reason = False, f"check raised {type(exc).__name__}: {exc}"
    return {"type": node.get("type"), "label": node.get("label", ""),
            "advisory": bool(node.get("advisory")),
            "passed": passed, "reason": reason, "spec": node}


def verify_task(spec: dict, trajectory: list, answer: str = "", question: str = "") -> dict:
    """Run a per-task verifier — {task_id, macros: {macro: tree}} — where each
    macro maps to an arbitrarily nested AND/OR tree of checks. Passes when every
    macro's tree passes.

    `question` is the task instruction; when given it is made available to the
    fuzzy answer judge so it can resolve context-dependent equivalence.
    """
    token = _QUESTION.set(question or "")
    try:
        macros = spec.get("macros") or {}
        results, by_macro = {}, {}
        for macro, tree in macros.items():
            res = _run_node(tree, trajectory, answer)
            results[macro] = res
            by_macro[macro] = res["passed"]
        return {
            "task_id": spec.get("task_id", ""),
            "passed": all(by_macro.values()) if by_macro else False,
            "by_macro": by_macro,
            "macros": results,
        }
    finally:
        _QUESTION.reset(token)


