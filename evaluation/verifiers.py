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

import re

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


def _dict_subset(want: dict, got: dict) -> bool:
    """Every field in `want` matches (normalized) in `got`. Extra fields in
    `got` (csrf, timestamps) are ignored. Value match tolerates benign formatting
    differences (whitespace/dashes) so identifiers aren't brittle."""
    for k, v in (want or {}).items():
        gv = got.get(k)
        if _norm(gv) != _norm(v) and _compact(gv) != _compact(v):
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

        for n in _network(traj):
            if want_method and (n.get("method") or "").upper() != want_method:
                continue
            if want_url and want_url not in (n.get("url") or ""):
                continue
            if want_status is not None and n.get("status") != want_status:
                continue
            if want_body and _norm(want_body) not in _norm(n.get("requestBody")):
                continue
            if want_fields and not _dict_subset(want_fields, _parse_body(n.get("requestBody"))):
                continue
            return True, f"{n.get('method')} {n.get('url')} -> {n.get('status')}"

        return False, (f"no {want_method or 'request'} to {want_url!r}"
                       + (f" with status {want_status}" if want_status is not None else "")
                       + (f" carrying {want_fields}" if want_fields else ""))


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


def _judge_alignment(text, expected, kind="output"):
    """LLM judge: does `text` arrive at / move toward the expected answer?"""
    try:
        from app.llm import call_llm
    except Exception:
        return False, "LLM unavailable for fuzzy check"
    import json as _json
    system = (
        f"You judge whether an agent's {kind} arrives at, contains, or clearly moves "
        "toward the expected answer. Equivalent phrasings count as a match (a name vs its "
        "email; 'the maximum, 5' vs '5'; a rounded vs exact figure that agrees). "
        'Reply ONLY JSON: {"match": true|false, "why": "<short reason>"}.')
    prompt = _json.dumps({"expected_answer": str(expected), "agent_" + kind.replace(" ", "_"): str(text)[:4000]})
    raw = call_llm(prompt, system=system, max_tokens=300, temperature=0.0,
                   json_mode=True, model="gemini-3.5-flash")
    if not raw:
        return False, "LLM unavailable for fuzzy check"
    try:
        d = _json.loads(raw)
        return bool(d.get("match")), "LLM judge: " + str(d.get("why", ""))[:100]
    except (ValueError, TypeError):
        return False, "LLM judge returned malformed output"


def _match_answer(answer, expected, mode):
    """Compare a reported answer to the expected value (substring, then fuzzy)."""
    got = str(answer or "").strip()
    if not got:
        return False, "no reported answer"
    if _norm(expected) in _norm(got):
        return True, "reported answer contains the expected value"
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
    """

    type = "qa_answer"

    def run(self, traj, answer):
        expected = self.arg("expected", "")
        mode = self.arg("mode", "fuzzy")
        leaf = self.arg("leaf", None)
        if not expected:
            return True, "no expected value set"

        def reasoning():
            return ReasoningContains({"expected": expected, "mode": mode}).run(traj, answer)

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
            ok, why = _match_answer(answer, expected, mode)
            return ok, "terminal → answer: " + why

        # leaf unknown: try the reported answer; with none recorded (e.g. a human
        # gold with no saved answer) fall back to reasoning (passes humans by the
        # perfect-trace assumption, checks the agent's reasoning otherwise).
        if str(answer or "").strip():
            ok, why = _match_answer(answer, expected, mode)
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
        if op == "OR":
            passed = any(k["passed"] for k in kids) if kids else False
        else:
            passed = all(k["passed"] for k in kids) if kids else True
        res = {"op": op, "passed": passed, "checks": kids}
        if node.get("label"):
            res["label"] = node["label"]
        return res

    cls = CHECKS.get(node.get("type"))
    if cls is None:
        return {"type": node.get("type"), "label": node.get("label", ""), "passed": False,
                "reason": f"unknown check type {node.get('type')!r}", "spec": node}
    check = cls(node)
    try:
        passed, reason = check.run(traj, answer)
    except Exception as exc:  # a broken check is a failed check, not a crash
        passed, reason = False, f"check raised {type(exc).__name__}: {exc}"
    return {"type": node.get("type"), "label": node.get("label", ""),
            "passed": passed, "reason": reason, "spec": node}


def verify_task(spec: dict, trajectory: list, answer: str = "") -> dict:
    """Run a per-task verifier — {task_id, macros: {macro: tree}} — where each
    macro maps to an arbitrarily nested AND/OR tree of checks. Passes when every
    macro's tree passes.
    """
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


