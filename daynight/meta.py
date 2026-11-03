"""The night's meta-train agent: read every episode of the day, then summarize the day.

Per episode (`analyze`), from the trace and the human's feedback only (`digest` drops the privileged Step.oracle and
the interventions' ground-truth labels):

    failure   where it went wrong: the step, the macro, the error type (schema.ERROR_TYPES)
    intent    what the human's correction meant: error type, macro, the intended behaviour
    score     0..1, how well the trace did the instruction (the verifier's per-macro result is part of the trace)

Per day (`summarize`): per macro, how often it was attempted, failed and drew an intervention, and its weakness
(trouble / attempts) that propose.py ranks by.

    LLMMetaAgent     one LLM call per episode that needed help or failed (helpers.llm, `meta.model`); an episode that
                     passed with no intervention is scored 1 without a call
    RuleMetaAgent    no LLM: keyword rules over the messages and the verifier result (the mock loop, and the LLM
                     agent's fallback when a reply is unusable)
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict

from daynight.schema import ERROR_TYPES, Analysis
from daynight.world import FAMILY_ERROR, family_of


def digest(ep, max_steps=30, max_human=20):
    """What the meta agent may see of an episode: no Step.oracle, no Intervention.label."""
    steps = [{"i": s.i, "actor": s.actor, "action": s.action, "url": s.url, "report": s.report,
              "n_actions": s.n_actions} for s in ep.steps[-max_steps:]]
    ivs = [{"step": iv.step, "kind": iv.kind, "text": iv.text, "n_human_actions": len(iv.human_actions),
            "human_actions": [{k: a.get(k) for k in ("action", "target", "value", "url") if a.get(k) is not None}
                              for a in iv.human_actions[:max_human]]} for iv in ep.interventions]
    o = ep.outcome
    return {"instruction": ep.instruction, "macros": ep.macros, "steps": steps, "interventions": ivs,
            "outcome": {"passed": o.passed, "by_macro": o.by_macro, "answer": o.answer,
                        "human_finished": o.human_finished} if o else None}


# ── rules ──────────────────────────────────────────────────────────────────────────────────────────────────────────

KEYWORDS = (       # first match wins
    ("premature_done", r"not (?:finished|done)|isn't done|aren't done|still more"),
    ("missed_step", r"skipp|forgot|still need|missing"),
    ("wrong_page", r"wrong page|wrong site|go back|wrong place"),
    ("wrong_answer", r"answer"),
    ("wrong_value", r"value|amount|number|date|wrong text"),
    ("wrong_target", r"wrong (?:item|one|button|row|option|link)|not that one|other one"),
    ("looping", r"repeat|again and again|same thing|stuck"),
)


def keyword_type(text):
    t = (text or "").lower()
    return next((et for et, rx in KEYWORDS if re.search(rx, t)), None)


def macro_in_text(text, macros):
    t = (text or "").lower()
    return next((m for m in macros if m.replace("_", " ") in t or m in t), None)


def _step_family(ep, i):
    s = next((s for s in ep.steps if s.i == i), None)
    return ((s.action or {}).get("delegate") or {}).get("family") if s else None


def _failed(ep):
    bm = (ep.outcome.by_macro if ep.outcome else {}) or {}
    return [m for m in ep.macros if bm.get(m) is False]


def score_of(ep):
    bm = (ep.outcome.by_macro if ep.outcome else {}) or {}
    frac = sum(bool(bm.get(m)) for m in ep.macros) / max(1, len(ep.macros))
    return round(max(0.0, min(1.0, frac - 0.1 * len(ep.interventions))), 3)


class RuleMetaAgent:
    source = "rule"

    def analyze(self, ep):
        if ep.outcome and ep.outcome.passed and not ep.interventions:
            return Analysis(ep.episode_id, score=1.0, rationale="passed with no intervention", source=self.source)
        failed = _failed(ep)
        if not ep.interventions:
            m = failed[0] if failed else None
            return Analysis(ep.episode_id, failure={"step": None, "macro": m, "error_type": None,
                                                    "explanation": "verifier failed; no human feedback"},
                            score=score_of(ep), rationale="no intervention", source=self.source)
        iv = ep.interventions[0]
        fam = _step_family(ep, iv.step)
        macro = macro_in_text(iv.text, ep.macros) or next((m for m in failed if family_of(m) == fam), None) or (
            next((m for m in ep.macros if family_of(m) == fam), None)) or (failed[0] if failed else None)
        # no hint in the words (a vague message, a silent takeover): the family's most common error
        et = keyword_type(iv.text) or (FAMILY_ERROR.get(family_of(macro)) if macro else None) or "other"
        failure = {"step": iv.step, "macro": macro, "error_type": et, "explanation": f"human {iv.kind}: {iv.text}"}
        intent = {"error_type": et, "macro": macro, "intended": iv.text or f"the human finished the {macro} part"}
        return Analysis(ep.episode_id, failure=failure, intent=intent, score=score_of(ep),
                        rationale=f"{len(ep.interventions)} intervention(s)", source=self.source)


# ── LLM ────────────────────────────────────────────────────────────────────────────────────────────────────────────

SYSTEM = ("You review one episode of a web agent that a person supervised. The person may have sent corrective "
          "messages or taken over. Find where the agent first went wrong, explain what the person's feedback meant, "
          "and score the episode against the task. Reply with JSON only.")

PROMPT = """Episode (the agent's steps, the person's interventions, and the task checker's result per required part):
{digest}

Error types: {types}
Required parts (macros): {macros}

Reply with JSON:
{{"failure": {{"step": index of the first wrong step or null, "macro": one of the required parts or null,
              "error_type": one of the error types or null, "explanation": one sentence}} or null if nothing went wrong,
  "intent": {{"error_type": what the person's first correction says went wrong (one of the error types),
             "macro": the part it is about, "intended": what the person wanted the agent to do instead}}
            or null if the person never intervened,
  "score": 0.0 to 1.0, how much of the task the agent itself got right,
  "rationale": one sentence}}"""


class LLMMetaAgent:
    def __init__(self, model):
        self.model, self.source, self.rules = model, model, RuleMetaAgent()

    def analyze(self, ep):
        if ep.outcome and ep.outcome.passed and not ep.interventions:
            return self.rules.analyze(ep)
        from helpers.llm import call_llm
        raw = call_llm(PROMPT.format(digest=json.dumps(digest(ep), ensure_ascii=False, default=str)[:24000],
                                     types=list(ERROR_TYPES), macros=ep.macros),
                       system=SYSTEM, max_tokens=700, temperature=0.0, json_mode=True, model=self.model)
        return self.parse(raw, ep)

    def parse(self, raw, ep):
        try:
            d = json.loads(raw or "")
        except ValueError:
            return self.rules.analyze(ep)

        def clean(x):
            if not isinstance(x, dict):
                return None
            x = dict(x)
            if x.get("error_type") not in ERROR_TYPES:
                x["error_type"] = None if x.get("error_type") is None else "other"
            if x.get("macro") not in ep.macros:
                x["macro"] = None
            return x
        try:
            score = max(0.0, min(1.0, float(d.get("score", 0.0))))
        except (TypeError, ValueError):
            score = score_of(ep)
        return Analysis(ep.episode_id, failure=clean(d.get("failure")),
                        intent=clean(d.get("intent")) if ep.interventions else None,
                        score=round(score, 3), rationale=str(d.get("rationale") or "")[:400], source=self.source)


def make_meta(cfg):
    return RuleMetaAgent() if cfg["backend"] == "mock" or cfg["meta"]["model"] == "mock" else LLMMetaAgent(
        cfg["meta"]["model"])


# ── the day as a whole ─────────────────────────────────────────────────────────────────────────────────────────────

def summarize(episodes, analyses):
    """-> {"n", "per_macro": {macro: {attempts, failed, intervened, trouble, weakness, errors}}, "notes"}."""
    an = {a.episode_id: a for a in analyses}
    per = defaultdict(lambda: {"attempts": 0, "failed": 0, "intervened": 0, "trouble": 0, "errors": Counter()})
    for ep in episodes:
        a = an.get(ep.episode_id)
        blamed = {x.get("macro") for x in ((a.failure if a else None), (a.intent if a else None)) if x} - {None}
        bm = (ep.outcome.by_macro if ep.outcome else {}) or {}
        for m in set(ep.macros):
            r = per[m]
            r["attempts"] += 1
            failed = bm.get(m) is False
            r["failed"] += failed
            r["intervened"] += m in blamed and bool(ep.interventions)
            r["trouble"] += failed or m in blamed
            for x in ((a.failure if a else None), (a.intent if a else None)):
                if x and x.get("macro") == m and x.get("error_type"):
                    r["errors"][x["error_type"]] += 1
                    break
    out = {}
    for m, r in per.items():
        out[m] = {**r, "errors": dict(r["errors"]), "weakness": round(r["trouble"] / r["attempts"], 3)}
    worst = sorted(out, key=lambda m: (-out[m]["trouble"], -out[m]["weakness"], m))[:5]
    notes = "; ".join(f"{m}: {out[m]['trouble']}/{out[m]['attempts']} in trouble"
                      + (f" (mostly {max(out[m]['errors'], key=out[m]['errors'].get)})" if out[m]["errors"] else "")
                      for m in worst if out[m]["trouble"])
    return {"n": len(episodes), "per_macro": dict(sorted(out.items())), "notes": notes or "no failures"}
