"""The episode log: what the day phase writes and the night phase reads.

One JSONL line per episode in `<out>/day_<t>/episodes.jsonl` (probe episodes, run without a human, in `probe.jsonl`).
Heavy artifacts (browser-use histories, screenshots, `grade_inputs.json`) stay in the episode's own folder and are
referenced by path.

Privileged fields: `Step.oracle` holds what only the simulator knows (the mock world's true deviation). The simulated
human may read it; the meta-train agent never does (meta.digest drops it), so RQ1 measures what the meta agent
understood from the trace and the human's feedback alone.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

SCHEMA = "daynight.episode/v1"

# What went wrong at an intervention. The simulated human labels each of its interventions with one of these, a real
# human may (takeover.py); the meta agent predicts one (RQ1).
ERROR_TYPES = (
    "wrong_target",      # acted on the wrong element (another row, button, option)
    "wrong_value",       # right control, wrong value (text, amount, slider position, date)
    "wrong_page",        # navigated to the wrong page or site
    "missed_step",       # skipped a required part of the task
    "premature_done",    # called done before the task was finished
    "wrong_answer",      # reported a wrong answer
    "looping",           # repeated the same step without progress
    "other",
)


def _build(cls, d):
    """Dataclass from a dict, ignoring unknown keys (older or newer logs)."""
    if d is None:
        return None
    names = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in d.items() if k in names})


@dataclass
class Label:
    """Ground truth of one intervention: why the human stepped in."""
    error_type: str
    macro: str | None = None         # canonical macro the error belongs to
    step: int | None = None          # index into Episode.steps of the step that went wrong


@dataclass
class Step:
    i: int
    actor: str                       # "agent" | "human"
    action: dict                     # agent: {"delegate": {family, instruction}} | {"done": {text}}; human: recorder entry
    url: str | None = None           # URL after the step
    model: str | None = None         # served model (planner turn: the specialist that ran)
    report: str | None = None        # what the agent said it did (specialist report, done text)
    n_actions: int = 0               # site actions inside the step (a delegation runs several)
    screenshots: list = field(default_factory=list)
    oracle: dict | None = None       # privileged (simulator only), see the module docstring


@dataclass
class Intervention:
    step: int                        # the step after which the human intervened (index into Episode.steps)
    kind: str                        # "message" | "takeover"
    actor: str                       # "simulated" | "real"
    text: str = ""                   # the message, or the human's note at a takeover
    label: Label | None = None       # ground truth, when known
    human_actions: list = field(default_factory=list)   # takeover: what the human did (recorder entries)
    at: float | None = None          # seconds into the episode (console takeovers: the moment the agent was stopped)


@dataclass
class Outcome:
    passed: bool                     # the task's verifier on the final state (human actions included)
    by_macro: dict = field(default_factory=dict)          # {macro: bool}
    answer: str | None = None
    human_finished: bool = False     # a takeover ended the episode
    grader: str = "verifier"
    detail: str = ""


@dataclass
class Episode:
    episode_id: str
    day: int
    task_id: str
    instruction: str
    site: str
    sites: list
    macros: list                     # gold macros, in order
    agent: dict                      # {"planner", "executor", "version", "day"}
    human: str                       # "simulated" | "real" | "none"
    steps: list = field(default_factory=list)
    interventions: list = field(default_factory=list)
    outcome: Outcome | None = None
    subtasks: list | None = None     # gold [(family, subtask)], when the annotation has them
    artifacts: dict = field(default_factory=dict)          # {"dir", "history", "grade_inputs", ...}
    error: str | None = None
    duration_s: float = 0.0
    schema: str = SCHEMA

    @property
    def takeover_step(self):
        return next((iv.step for iv in self.interventions if iv.kind == "takeover"), None)

    @property
    def autonomous(self):
        """Passed with no intervention at all."""
        return bool(self.outcome and self.outcome.passed and not self.interventions)

    def to_dict(self):
        d = asdict(self)
        d["takeover_step"] = self.takeover_step
        return d

    @classmethod
    def from_dict(cls, d):
        d = dict(d)
        d.pop("takeover_step", None)
        ep = _build(cls, d)
        ep.steps = [_build(Step, s) for s in d.get("steps") or []]
        ivs = []
        for x in d.get("interventions") or []:
            iv = _build(Intervention, x)
            iv.label = _build(Label, x.get("label"))
            ivs.append(iv)
        ep.interventions = ivs
        ep.outcome = _build(Outcome, d.get("outcome"))
        return ep


# ── night-phase records ────────────────────────────────────────────────────────────────────────────────────────────

@dataclass
class Analysis:
    """The meta-train agent's reading of one episode."""
    episode_id: str
    failure: dict | None = None      # {"step", "macro", "error_type", "explanation"}; None when nothing went wrong
    intent: dict | None = None       # {"error_type", "macro", "intended"}: what the human's correction meant
    score: float = 0.0               # 0..1, the trace against the instruction
    rationale: str = ""
    source: str = ""                 # model name, or "mock" / "rule"


@dataclass
class Proposal:
    """A night's request to MiniWebGen: more practice on one macro."""
    macro: str
    target: int                      # new kept trajectories wanted tonight
    weakness: float                  # the score it was ranked by
    rationale: str = ""
    episodes: list = field(default_factory=list)          # the day's episodes that motivated it


# ── JSONL ──────────────────────────────────────────────────────────────────────────────────────────────────────────

def _plain(x):
    return x.to_dict() if hasattr(x, "to_dict") else asdict(x) if hasattr(x, "__dataclass_fields__") else x


def write_jsonl(path, items):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(_plain(x), ensure_ascii=False, default=str) + "\n" for x in items))


def read_jsonl(path):
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().split("\n") if line.strip()]


def read_episodes(path):
    return [Episode.from_dict(d) for d in read_jsonl(path)]


def read_analyses(path):
    return [_build(Analysis, d) for d in read_jsonl(path)]
