"""One experiment's settings: a YAML file deep-merged over DEFAULTS.

    cfg = load("daynight/configs/v1_sim.yaml", model="mock")     # --model mock: every model-backed part mocked

`model: mock` (or `--model mock`) switches the backend to the mock world and every model (agent, simulated human,
meta agent) to its rule-based stand-in, so the loop runs with no browser, GPU, server or API key.
"""
from __future__ import annotations

import copy
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

DEFAULTS = {
    "name": "daynight",
    "out": None,                      # default data/daynight/<name>
    "model": None,                    # "mock" = the whole loop mocked
    "backend": "miniweb",             # "miniweb" (real sites, browser, vLLM) | "mock"
    "seed": 0,
    "days": 3,
    "tasks_per_day": 20,
    "workers": 2,                     # parallel episodes (a real human always runs one at a time)
    # day tasks: the annotated human tasks of these sites; "train" = every training site of the fixed split.
    # Night data comes from MiniWebGen, which only ever touches training sites.
    "sites": "train",
    # fixed probe set, run with no human by each day's agent: success over days without help (RQ2/RQ3)
    "probe": {"enabled": True, "split": "test", "limit": 0},
    "agent": {
        "planner": "qwen35-4b",       # untrained planner (served name)
        "executor": "pooled_v4",      # day-0 executor: served LoRA name ...
        "executor_path": "data/webmix/adapters/pooled_v4",   # ... and its weights (the first --init-adapter)
        "version": "v6",              # webmix.planner_agent version
        "vllm": "http://127.0.0.1:8400/v1",
        "sub_cap": 15,
        "planner_turns": 25,
        "timeout": 2400,
        "temperature": 0.0,
        "ports": [8316, 8317],        # MiniWeb servers (datagen.browser.Servers allows 8300-8320 only)
        "headless": True,
    },
    "human": {
        "kind": "simulated",          # "simulated" | "real" | "none"
        "model": "gemini-3.5-flash",  # simulated human's LLM (helpers.llm)
        "max_messages": 2,            # corrective messages before a takeover
        "partial_verify": True,       # the simulated human sees per-macro progress (verifier on the partial trace)
    },
    "console": {                      # the day console (console.py): a person prompts the agent and takes over
        "host": "127.0.0.1",          # on a lab machine, reach it through an ssh tunnel
        "port": 8390,
        "fps": 4,                     # live view frames per second
        "save_every": 1.0,            # seconds between frames saved to the episode's frames/
        "mock_step_delay": 1.5,       # mock world: seconds per agent step, so a person can watch and interrupt
        "max_messages": 20,           # corrections per episode (each `done` waits for the person's verdict)
    },
    "meta": {
        "model": "gemini-3.5-flash",  # meta-train agent's LLM
        "weak_macros": 3,             # proposals per night
        "min_attempts": 1,
    },
    "propose": {
        "trajectories_per_night": 60, # new kept trajectories wanted per night, split over the weak macros
        "min_per_macro": 10,
        "datagen": "--no-judge --workers 12 --servers 6 --attempts 3",
        "replay": "--workers 6 --ports 8310,8311 --memory-model qwen35-4b",
    },
    "train": {
        "method": "sft",              # "rl" is a stub (stubs.choose_method)
        "gpus": "0",
        # branch from yesterday's adapter and KL-anchor to it (the *_v5b recipe, webmix/README.md)
        "recipe": "--adapter pooled --epochs 1 --lr 5e-5 --beta 0.1 --anchor-ratio 0.25 --rank 64 --alpha 128",
        "replay_mix": 1.0,            # replay_v4 episodes mixed in per new episode (against forgetting)
        "replay_pool": "data/webmix/replay_v4",
        "served_prefix": "dn",        # day t's adapter is served as <prefix><t>
    },
    "envs": {
        "miniweb_python": "~/.conda/envs/miniweb/bin/python",
        "webmix_env": "~/.conda/envs/webmix",
    },
}


def _merge(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def load(path=None, **overrides):
    """-> config dict. `overrides` (from the CLI) win over the file; None values are ignored."""
    raw = yaml.safe_load(Path(path).read_text()) if path else {}
    cfg = _merge(DEFAULTS, raw)
    for k, v in overrides.items():
        if v is not None:
            cfg[k] = v
    if cfg["model"] == "mock":
        cfg["backend"] = "mock"
    if cfg["backend"] not in ("miniweb", "mock"):
        raise ValueError(f"backend must be miniweb or mock, not {cfg['backend']!r}")
    if cfg["human"]["kind"] not in ("simulated", "real", "none"):
        raise ValueError(f"human.kind must be simulated, real or none, not {cfg['human']['kind']!r}")
    bad = [p for p in cfg["agent"]["ports"] if not 8300 <= int(p) <= 8320]
    if bad:
        raise ValueError(f"agent.ports {bad}: MiniWeb servers for harnesses must be on 8300-8320")
    cfg["out"] = str(Path(cfg["out"] or ROOT / "data" / "daynight" / cfg["name"]))
    return cfg


def is_mock(cfg):
    return cfg["backend"] == "mock"


def out_dir(cfg):
    p = Path(cfg["out"])
    return p if p.is_absolute() else ROOT / p


def day_dir(cfg, day):
    return out_dir(cfg) / f"day_{day}"
