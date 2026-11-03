"""The human of the day phase: the interface every human implements, and the simulated human.

After each agent step the day runner shows the human a `View` and gets a `Decision`:

    continue                 let the agent go on
    message <text>           a corrective message; the agent continues with it in context
    takeover                 the agent is stopped; a real human finishes the task in the same browser
                             (takeover.py), a simulated one ends the episode there (it cannot act)

The simulated human knows the task's goal: the instruction, the gold macros and subtasks of the annotation and, with
`human.partial_verify`, the per-macro progress the task's verifier reports on the trace so far. It intervenes when the
agent goes off track, at most `human.max_messages` messages per episode before it takes over, and labels every
intervention with an error type (schema.ERROR_TYPES): the ground truth of RQ1.

    LLMSimulatedHuman    an LLM (helpers.llm, `human.model`) reads the view and decides
    MockSimulatedHuman   no LLM: reads the mock world's privileged `Step.oracle` (world.MockBackend)
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import random
from dataclasses import dataclass, field

from daynight.schema import ERROR_TYPES, Label


@dataclass
class View:
    """What the human sees after a step."""
    episode_id: str
    instruction: str
    macros: list                     # gold macros, in order
    subtasks: list | None            # gold [(family, subtask)] or None
    steps: list                      # schema.Step so far
    interventions: list              # schema.Intervention so far
    progress: dict | None = None     # {macro: passed} on the partial trace, when known
    done: bool = False               # the agent just called done
    answer: str | None = None


@dataclass
class Decision:
    kind: str = "continue"           # "continue" | "message" | "takeover"
    text: str = ""
    label: Label | None = None


class Human:
    """Interface. `can_act`: the human performs the rest of a takeover in the browser (only a real one)."""
    actor = "simulated"
    can_act = False

    async def decide(self, view: View) -> Decision:
        raise NotImplementedError

    async def take_over(self, view: View):
        """-> (answer or None, note, Label or None) once the human has finished the task (can_act humans only)."""
        raise NotImplementedError


def messages_sent(view):
    return sum(1 for iv in view.interventions if iv.kind == "message")


def _macro_words(m):
    return (m or "task").replace("_", " ")


# Corrective messages by error type. The mock human uses them as they are; they are also the LLM human's fallback.
MESSAGES = {
    "wrong_target": "No, that's the wrong item. Pick the one the task names for the {m} step.",
    "wrong_value": "The value is wrong for the {m} step. Use exactly the value given in the task.",
    "wrong_page": "You're on the wrong page. Go back and find where to do the {m} step.",
    "missed_step": "You skipped a step: you still need to do the {m} part.",
    "premature_done": "You're not finished yet; the {m} part isn't done.",
    "wrong_answer": "That answer is wrong. Check the page again for the {m} part before answering.",
    "looping": "You keep repeating the same thing. Try a different way to do the {m} step.",
    "other": "That's not right for the {m} step. Re-read the task.",
}
# Real people are often vague; a share of the mock human's messages carry no hint (the meta agent must still read them).
VAGUE = ("Hmm, that's not what I asked for.", "No, not like that.", "That's not right, try again.")


class MockSimulatedHuman(Human):
    """Intervenes exactly when the mock world marks the last step as a deviation (Step.oracle)."""

    def __init__(self, max_messages=2, vague_share=0.2, seed=0):
        self.max_messages, self.vague_share, self.seed = max_messages, vague_share, seed

    async def decide(self, view):
        last = view.steps[-1] if view.steps else None
        dev = (last.oracle or {}).get("deviation") if last else None
        if not dev:
            return Decision()
        label = Label(error_type=dev, macro=last.oracle.get("macro"), step=last.i)
        if messages_sent(view) >= self.max_messages:
            return Decision("takeover", "Let me do it.", label)
        rng = random.Random(int(hashlib.md5(f"{self.seed}:{view.episode_id}:{last.i}".encode()).hexdigest()[:8], 16))
        text = rng.choice(VAGUE) if rng.random() < self.vague_share else MESSAGES[dev].format(m=_macro_words(label.macro))
        return Decision("message", text, label)


SYSTEM = (
    "You are simulating a person who gave a web agent a task and is watching it work. You know exactly what the task "
    "requires. After each agent step, decide whether to let it continue, send it a short corrective message (as a "
    "person would type it: plain words, no step numbers, no mention of macros or verifiers), or take over because "
    "correcting is hopeless. Intervene only when the agent is actually going wrong or stops before the task is done. "
    "Reply with JSON only.")

PROMPT = """Task given to the agent:
{instruction}

What the task requires, in order (privileged, the agent does not see this):
{plan}

Progress so far by required part (privileged; from a checker on the trace, true = done correctly; reasoning parts are
not checked until the end): {progress}

The agent's steps so far (most recent last):
{steps}

Your earlier messages to the agent: {sent}
{done_note}
Reply with JSON:
{{"decision": "continue" | "message" | "takeover",
  "error_type": one of {types} (or null when continuing),
  "macro": the required part that went wrong, one of {macros} (or null),
  "step": index of the step that went wrong (or null),
  "message": the message to send (only for "message")}}"""


def _step_line(s):
    act = s.action or {}
    (name, p), = act.items() if len(act) == 1 else (("?", act),)
    what = (p or {}).get("instruction") or (p or {}).get("text") or ""
    fam = (p or {}).get("family")
    head = f"[{s.i}] {s.actor} {name}" + (f" ({fam})" if fam else "") + (f": {what}" if what else "")
    tail = []
    if s.report:
        tail.append(f"reported: {str(s.report)[:300]}")
    if s.url:
        tail.append(f"now at {s.url}")
    return head + ("\n     " + " | ".join(tail) if tail else "")


class LLMSimulatedHuman(Human):
    def __init__(self, model, max_messages=2):
        self.model, self.max_messages = model, max_messages

    def prompt(self, view):
        plan = "\n".join(f"- {m}" + (f": {view.subtasks[i][1]}" if view.subtasks and i < len(view.subtasks) else "")
                         for i, m in enumerate(view.macros))
        sent = [iv.text for iv in view.interventions if iv.kind == "message"] or "none"
        done = ("\nThe agent has just called done" + (f" with the answer: {view.answer}" if view.answer else "") +
                ". If the task is not complete or the answer is wrong, intervene now; otherwise continue.\n"
                if view.done else "")
        return PROMPT.format(instruction=view.instruction, plan=plan,
                             progress=json.dumps(view.progress) if view.progress is not None else "unknown",
                             steps="\n".join(_step_line(s) for s in view.steps[-12:]) or "none", sent=sent,
                             done_note=done, types=list(ERROR_TYPES), macros=view.macros)

    async def decide(self, view):
        from helpers.llm import call_llm
        raw = await asyncio.to_thread(call_llm, self.prompt(view), system=SYSTEM, max_tokens=400, temperature=0.0,
                                      json_mode=True, model=self.model)
        return self.parse(raw, view)

    def parse(self, raw, view):
        try:
            d = json.loads(raw or "")
        except ValueError:
            return Decision()                   # an unusable reply never interrupts the agent
        kind = d.get("decision")
        if kind not in ("message", "takeover"):
            return Decision()
        et = d.get("error_type") if d.get("error_type") in ERROR_TYPES else "other"
        macro = d.get("macro") if d.get("macro") in view.macros else None
        step = d.get("step") if isinstance(d.get("step"), int) else (view.steps[-1].i if view.steps else None)
        label = Label(error_type=et, macro=macro, step=step)
        if kind == "message" and messages_sent(view) >= self.max_messages:
            kind = "takeover"
        text = (d.get("message") or MESSAGES[et].format(m=_macro_words(macro))) if kind == "message" else "Let me do it."
        return Decision(kind, text, label)


def make_human(cfg):
    """The configured human: None (probe / no human), a simulated one, or the terminal takeover interface."""
    h = cfg["human"]
    if h["kind"] == "none":
        return None
    if h["kind"] == "real":
        from daynight.takeover import TerminalHuman
        return TerminalHuman()
    if cfg["backend"] == "mock" or h["model"] == "mock":
        return MockSimulatedHuman(max_messages=h["max_messages"], seed=cfg["seed"])
    return LLMSimulatedHuman(h["model"], max_messages=h["max_messages"])
