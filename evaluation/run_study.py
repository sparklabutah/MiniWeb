#!/usr/bin/env python3
"""Run a full MiniWeb study from one config: N models x M tasks, browser-use harness.

Usage:
    python evaluation/run_study.py --config evaluation/configs/study.yaml
    python evaluation/run_study.py --config study.yaml --dry-run

Config (YAML or JSON):

    name: august-study
    out: evaluation/results/august-study
    tasks: all                    # or ["Minh/banking_357033", "site:dating", ...]
    exclude: ["Minh/live_57395e"]
    resume: true                  # skip tasks that already have a result.json
    repeats: 1                    # episodes per model x task

    episode:
      max_steps: 30
      timeout: 600
      obs: visual                 # visual | axtree
      start_from: recorded        # recorded | starting_url
      headless: true
      port: 8099

    models:
      - label: qwen3.5-27b
        provider: ollama
        model: qwen3.5:27b
        host: http://localhost:11434      # optional
        temperature: 0.0
      - label: gemini-flash
        provider: gemini                  # GOOGLE_API_KEY / GEMINI_API_KEY
        model: gemini-3.5-flash
      - label: gpt-5
        provider: openai                  # OPENAI_API_KEY
        model: gpt-5
      - label: claude
        provider: anthropic               # ANTHROPIC_API_KEY
        model: claude-sonnet-5
      - label: my-tgi
        provider: huggingface             # any OpenAI-compatible endpoint (TGI/vLLM)
        model: tgi
        base_url: https://xyz.endpoints.huggingface.cloud/v1
        api_key_env: HF_TOKEN
"""
import argparse
import asyncio
import collections
import json
import math
import sys
import os
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evaluation"))

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from run_agent_verify import run_and_grade, _expand_tasks   # noqa: E402

from helpers.term import BOLD, DIM, RESET, GREEN, RED


# ── config ────────────────────────────────────────────────────────────────────

def load_config(path):
    text = Path(path).read_text()
    try:
        import yaml
        return yaml.safe_load(text)
    except Exception:
        return json.loads(text)


# ── LLM construction, one browser-use chat object per provider ───────────────

def _key(spec, default_envs):
    env = spec.get("api_key_env")
    envs = [env] if env else default_envs
    for e in envs:
        if os.environ.get(e):
            return os.environ[e]
    return None


def build_llm(spec):
    provider = spec["provider"].lower()
    model = spec["model"]
    kw = {}
    if spec.get("temperature") is not None:
        kw["temperature"] = float(spec["temperature"])
    if spec.get("max_tokens") is not None:
        kw["max_completion_tokens" if provider in ("openai", "huggingface") else "max_tokens"] = int(spec["max_tokens"])

    if provider in ("openai", "huggingface", "openai-compatible"):
        from browser_use.llm.openai.chat import ChatOpenAI
        key = _key(spec, ["OPENAI_API_KEY"] if provider == "openai" else ["HF_TOKEN", "OPENAI_API_KEY"])
        if spec.get("base_url"):
            kw["base_url"] = spec["base_url"]
        return ChatOpenAI(model=model, api_key=key, **kw)

    if provider in ("gemini", "google"):
        from browser_use.llm.google.chat import ChatGoogle
        key = _key(spec, ["GOOGLE_API_KEY", "GEMINI_API_KEY"])
        return ChatGoogle(model=model, api_key=key, **kw)

    if provider == "anthropic":
        from browser_use.llm.anthropic.chat import ChatAnthropic
        return ChatAnthropic(model=model, api_key=_key(spec, ["ANTHROPIC_API_KEY"]), **kw)

    if provider == "ollama":
        from browser_use.llm.ollama.chat import ChatOllama
        opts = {}
        if "temperature" in kw:
            opts["temperature"] = kw.pop("temperature")
        if "max_tokens" in kw:
            opts["num_predict"] = kw.pop("max_tokens")
        okw = {"ollama_options": opts} if opts else {}
        if spec.get("host"):
            okw["host"] = spec["host"]
        return ChatOllama(model=model, **okw)

    raise ValueError(f"unknown provider {provider!r} "
                     "(openai | anthropic | gemini | ollama | huggingface | openai-compatible)")


def build_agent_for(spec, ep):
    from agents import BrowserUseAgent
    from generate_fixtures import ensure_fixtures
    return BrowserUseAgent(
        build_llm(spec),
        use_vision=ep["obs"] == "visual",
        max_steps=ep["max_steps"],
        timeout=ep["timeout"],
        headless=ep["headless"],
        available_file_paths=ensure_fixtures(),
    )


# ── study loop ────────────────────────────────────────────────────────────────

EP_DEFAULTS = dict(max_steps=30, timeout=600, obs="visual",
                   start_from="recorded", headless=True, port=8099)


async def run_study(cfg, dry_run=False):
    ep = {**EP_DEFAULTS, **(cfg.get("episode") or {})}
    models = cfg["models"]
    tasks = _expand_tasks(cfg.get("tasks", "all"))
    exclude = set(cfg.get("exclude") or [])
    tasks = [t for t in tasks if t not in exclude]
    resume = cfg.get("resume", True)
    repeats = int(cfg.get("repeats", 1))
    out_root = Path(cfg.get("out") or ROOT / "evaluation" / "results" /
                    (cfg.get("name") or f"study_{datetime.now():%Y%m%d_%H%M%S}"))
    out_root.mkdir(parents=True, exist_ok=True)

    total = len(models) * len(tasks) * repeats
    print(f"{BOLD}study{RESET}: {len(models)} model(s) x {len(tasks)} task(s) x {repeats} repeat(s) "
          f"= {total} episodes  ->  {out_root}\n")
    if dry_run:
        for m in models:
            print(f"  {m.get('label', m['model'])}: {m['provider']}/{m['model']}")
        print(f"  first tasks: {tasks[:5]}{' ...' if len(tasks) > 5 else ''}")
        return []

    results = []
    for spec in models:
        label = spec.get("label") or spec["model"].replace("/", "-")
        for rep in range(1, repeats + 1):
            suffix = f"__r{rep}" if repeats > 1 else ""
            for i, task_id in enumerate(tasks):
                out = out_root / f"{label}__{task_id.replace('/', '-')}{suffix}"
                tag = f"{DIM}[{label}{suffix} · {task_id} · {i+1}/{len(tasks)}]{RESET}"
                if resume and (out / "result.json").exists():
                    print(f"  {tag} SKIP (done)")
                    continue
                try:
                    agent = build_agent_for(spec, ep)
                    res = await run_and_grade(
                        task_id=task_id, model=f"{spec['provider']}/{spec['model']}",
                        obs=ep["obs"],
                        max_steps=ep["max_steps"], timeout=ep["timeout"],
                        headless=ep["headless"], start_from=ep["start_from"],
                        port=ep["port"], out=out, verbose=False, agent=agent)
                    res["label"], res["repeat"] = label, rep
                    results.append(res)
                    mark = f"{GREEN}PASS{RESET}" if res["passed"] else f"{RED}FAIL{RESET}"
                    print(f"  {tag} {mark}  {DIM}{res['elapsed_s']:.0f}s{RESET}")
                except Exception as exc:
                    print(f"  {tag} {RED}ERROR{RESET} {exc}")
                    results.append({"label": label, "repeat": rep, "task_id": task_id,
                                    "passed": False, "error": str(exc)})

    (out_root / "study_results.json").write_text(json.dumps(results, indent=1, default=str))
    summarize(out_root)
    return results


# ── summary: overall / per chain length / per macro, per model ───────────────

def summarize(out_root):
    out_root = Path(out_root)
    rows = []
    for rj in out_root.glob("*/result.json"):
        r = json.loads(rj.read_text())
        r.setdefault("label", rj.parent.name.split("__")[0])
        rows.append(r)
    if not rows:
        print("no results to summarize")
        return

    by_label = collections.defaultdict(list)
    for r in rows:
        by_label[r["label"]].append(r)
    labels = sorted(by_label)

    def rate(rs):
        n = len(rs)
        p = sum(1 for r in rs if r.get("passed"))
        return p, n, (100 * p / n if n else 0)

    print(f"\n{BOLD}=== {out_root.name} ==={RESET}")
    print(f"\n{BOLD}overall{RESET}")
    for l in labels:
        p, n, pct = rate(by_label[l])
        se = math.sqrt(pct / 100 * (1 - pct / 100) / n) * 100 if n else 0
        print(f"  {l:<22} {p}/{n} = {pct:5.1f}%  (±{se:.1f})")

    print(f"\n{BOLD}by chain length{RESET}")
    lens = sorted({len(r.get("by_macro") or {}) for r in rows})
    for L in lens:
        cells = []
        for l in labels:
            p, n, pct = rate([r for r in by_label[l] if len(r.get("by_macro") or {}) == L])
            cells.append(f"{l}: {p}/{n} ({pct:.0f}%)" if n else f"{l}: —")
        print(f"  len {L}:  " + "   ".join(cells))

    print(f"\n{BOLD}by macro{RESET} (check-level)")
    macros = collections.Counter()
    per = {l: collections.defaultdict(lambda: [0, 0]) for l in labels}
    for l in labels:
        for r in by_label[l]:
            for m, ok in (r.get("by_macro") or {}).items():
                base = m.split("+")[0].split(":")[0].strip()
                macros[base] += 1
                per[l][base][0] += 1
                per[l][base][1] += bool(ok)
    header = f"  {'macro':<26}" + "".join(f"{l[:14]:>16}" for l in labels)
    print(header)
    for m, _ in macros.most_common():
        cells = []
        for l in labels:
            n, p = per[l][m]
            cells.append(f"{100*p/n:5.0f}% ({n})" if n else "      —")
        print(f"  {m:<26}" + "".join(f"{c:>16}" for c in cells))

    summary_path = out_root / "study_summary.json"
    summary_path.write_text(json.dumps({
        "overall": {l: dict(zip(("pass", "n", "rate"), rate(by_label[l]))) for l in labels},
        "by_macro": {l: {m: per[l][m] for m in per[l]} for l in labels},
    }, indent=1, default=str))
    print(f"\nsummary -> {summary_path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config")
    ap.add_argument("--dry-run", action="store_true", help="print the plan, run nothing")
    ap.add_argument("--summarize-only", metavar="DIR", help="just re-summarize an existing study dir")
    args = ap.parse_args()

    if args.summarize_only:
        summarize(args.summarize_only)
        return
    if not args.config:
        ap.error("--config is required (or use --summarize-only DIR)")
    cfg = load_config(args.config)
    asyncio.run(run_study(cfg, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
