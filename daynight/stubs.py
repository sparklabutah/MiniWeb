"""Night-phase decisions that version 1 does not make yet: their interfaces, so a later version fills them in.

    propose_env_changes(summary, cfg) -> [EnvChange]     v1: none
    choose_method(summary, cfg) -> TrainingPlan           v1: always SFT; "rl" is refused
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EnvChange:
    """A proposed change to the environment (a site, its data, or the harness) that would make practice possible."""
    site: str
    kind: str                        # e.g. "add_control", "seed_data", "harness"
    description: str
    rationale: str = ""
    macros: list = field(default_factory=list)


@dataclass
class TrainingPlan:
    method: str                      # "sft" | "rl"
    reason: str = ""
    params: dict = field(default_factory=dict)


def propose_env_changes(summary, cfg):
    """v1: no environment changes. (The frozen dataset needs the maintainer's sign-off for any change anyway.)"""
    return []


def choose_method(summary, cfg):
    method = cfg["train"].get("method", "sft")
    if method != "sft":
        raise NotImplementedError(f"train.method {method!r}: v1 trains with SFT only (daynight/stubs.py)")
    return TrainingPlan("sft", "v1: SFT on the night's MiniWebGen trajectories, branched from the day's executor")
