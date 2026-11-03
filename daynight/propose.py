"""The night's task proposal: weak macros -> MiniWebGen -> replayed training rows.

    proposals = propose(summary, cfg)                  # ranked by episodes in trouble (meta.summarize)
    plan = night_commands(cfg, day, proposals)         # the shell commands of the night (written to night_plan.sh)

Proposals skip the macros MiniWebGen cannot practice: question answering (report_information, count_entries) is not
replayed into rows (webmix/__main__.py NOT_REPLAYED: it is trained on human tasks instead), and a macro needs a control
kind (datagen.kinds).

Isolation: the frozen dataset is never written. Each experiment has its own MiniWebGen tree,
`<out>/datagen/` (MINIWEB_DATAGEN_DIR), whose split, guides, site maps and per-kind caches are links to the shared
`data/datagen/` ones (datagen writes a site map or guide only when it is missing), and its own replay dir,
`<out>/replay/` (WEBMIX_REPLAY_DIR). Night t runs one MiniWebGen run per proposed macro, `d<t>_<macro>`, with
`--target` = the macro's kept trajectories so far + tonight's target: datagen counts earlier runs toward the target and
excludes their dedup keys, so every night adds new trajectories.
"""
from __future__ import annotations

import json
import math
import os
import random
import shlex
from pathlib import Path

from daynight import config as C
from daynight.schema import Proposal

NOT_REPLAYED = {"report_information", "count_entries"}       # = webmix.__main__.NOT_REPLAYED
SHARED = ("site_split.json", "guides", "sitemap", "formvalues", "qa_records", "programs", "carry_pairs")


def propose(summary, cfg, episodes=()):
    from datagen import kinds
    mcfg, pcfg = cfg["meta"], cfg["propose"]
    ok = set(kinds.supported_macros()) - NOT_REPLAYED
    per = summary["per_macro"]
    cand = [m for m, r in per.items()
            if m in ok and r["attempts"] >= mcfg["min_attempts"] and r["trouble"] > 0]
    # most episodes in trouble first (what cost the human the most interventions), then the rate: a macro seen once
    # and failed once is not the weakest
    cand.sort(key=lambda m: (-per[m]["trouble"], -per[m]["weakness"], m))
    top = cand[:mcfg["weak_macros"]]
    total = sum(per[m]["trouble"] for m in top) or 1
    by_macro = {m: [ep.episode_id for ep in episodes if m in ep.macros and not ep.autonomous] for m in top}
    out = []
    for m in top:
        r = per[m]
        target = max(pcfg["min_per_macro"], math.ceil(pcfg["trajectories_per_night"] * r["trouble"] / total))
        why = f"{r['trouble']}/{r['attempts']} episodes in trouble" + (
            f"; errors {r['errors']}" if r["errors"] else "")
        out.append(Proposal(macro=m, target=target, weakness=r["weakness"], rationale=why, episodes=by_macro[m][:20]))
    return out


def datagen_dir(cfg):
    return C.out_dir(cfg) / "datagen"


def replay_dir(cfg):
    return C.out_dir(cfg) / "replay"


def seed_datagen_dir(cfg):
    """<out>/datagen/ with links to the shared inputs that exist on this machine. -> the linked names."""
    d = datagen_dir(cfg)
    (d / "runs").mkdir(parents=True, exist_ok=True)
    shared = C.ROOT / "data" / "datagen"
    linked = []
    for name in SHARED:
        src, dst = shared / name, d / name
        if src.exists() and not dst.exists() and not dst.is_symlink():
            dst.symlink_to(src.resolve())
            linked.append(name)
    return linked


def kept_count(cfg, macro):
    """Kept trajectories of `macro` in this experiment's MiniWebGen tree."""
    n = 0
    for kp in (datagen_dir(cfg) / "runs").glob("*/kept.jsonl"):
        n += sum(1 for line in kp.read_text().split("\n") if line.strip() and json.loads(line).get("macro") == macro)
    return n


def night_commands(cfg, day, proposals):
    """-> [(stage, shell command)] for the night's generation and replay (training: daynight.train)."""
    py = os.path.expanduser(cfg["envs"]["miniweb_python"])
    env = f"MINIWEB_DATAGEN_DIR={shlex.quote(str(datagen_dir(cfg)))}"
    cmds = []
    for p in proposals:
        target = kept_count(cfg, p.macro) + p.target
        cmds.append(("generate", f"{env} {py} -m datagen run --run-id d{day}_{p.macro} --macros {p.macro} "
                                 f"--target {target} {cfg['propose']['datagen']}"))
    if proposals:
        macros = ",".join(p.macro for p in proposals)
        cmds.append(("replay", f"{env} WEBMIX_REPLAY_DIR={shlex.quote(str(replay_dir(cfg)))} {py} -m webmix replay "
                               f"--macros {macros} {cfg['propose']['replay']}"))
    return cmds


# ── mock: what generation + replay would leave on disk ─────────────────────────────────────────────────────────────

def mock_generate(cfg, day, proposals, keep_rate=0.75, replay_rate=0.85):
    """Fake kept trajectories (<out>/datagen/runs/d<t>_<macro>/kept.jsonl) and replayed episodes
    (<out>/replay/<task>/rows.jsonl, rows without messages). -> {macro: replayed episodes}."""
    from datagen.viewer import FAMILY_OF
    rng = random.Random(f"{cfg['seed']}:gen:{day}")
    made = {}
    for p in proposals:
        run = datagen_dir(cfg) / "runs" / f"d{day}_{p.macro}"
        run.mkdir(parents=True, exist_ok=True)
        kept = [{"task_id": f"d{day}_{p.macro}_{k:03d}", "macro": p.macro, "mock": True}
                for k in range(round(p.target * keep_rate))]
        (run / "kept.jsonl").write_text("".join(json.dumps(r) + "\n" for r in kept))
        made[p.macro] = 0
        for r in kept:
            if rng.random() > replay_rate:
                continue
            ep = replay_dir(cfg) / r["task_id"]
            ep.mkdir(parents=True, exist_ok=True)
            rows = [{"task_id": r["task_id"], "step": i, "macro": p.macro, "family": FAMILY_OF.get(p.macro, "Other"),
                     "messages": [], "target": "{}", "mock": True} for i in range(2 + rng.randrange(6))]
            (ep / "rows.jsonl").write_text("".join(json.dumps(x) + "\n" for x in rows))
            (ep / "episode.json").write_text(json.dumps({"task_id": r["task_id"], "macro": p.macro, "mock": True}))
            made[p.macro] += 1
    return made
