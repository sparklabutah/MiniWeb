"""Train/test SITE split — decided once, before anything is generated, and persisted
(data/datagen/site_split.json, tracked). Every later stage only touches train sites.

Greedy, deterministic (seeded) set cover over a test budget (~20% of sites):
  * every slice/target macro gets >= `min_human_test` test sites where humans
    recorded it (so transfer is measured on real annotated tasks there);
  * every macro supported on >= 4 sites (data/macro_locations.yaml) gets >= 1 test site;
  * no pick may leave a macro with fewer than max(3, 60%) of its sites in train.
Leftover budget is filled with sites that have human tasks (evaluable), seeded order.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from collections import defaultdict

from datagen import config


def all_sites():
    return sorted(p.parent.name for p in (config.ROOT / "sites").glob("*/site.json"))


def support_map():
    """{macro: set(site)} from data/macro_locations.yaml (canonical keys)."""
    from annotation.macro_locations import MACRO_LOCATIONS
    from annotation.macros import canon
    out = defaultdict(set)
    for site, macros in MACRO_LOCATIONS.items():
        for m in macros or {}:
            out[canon(m)].add(site)
    return out


def human_map():
    """{macro: set(site)} — sites where a human recording performs the macro. The site is
    read from the URLs of the span's actions (multi-site tasks name several sites)."""
    import re
    from annotation.macro_browser import index, task_detail
    from annotation.macros import canon
    out = defaultdict(set)
    details = {}
    for macro, occs in index()["macros"].items():
        for o in occs:
            if not o.get("span"):
                continue
            if o["key"] not in details:
                a, t = o["key"].split("/", 1)
                details[o["key"]] = task_detail(a, t) or {"actions": []}
            lo, hi = o["span"]
            for act in details[o["key"]]["actions"][lo - 1:hi]:
                m = re.search(r"/sites/([^/?#]+)", act.get("url") or "")
                if m:
                    out[canon(macro)].add(m.group(1))
    return out


def _h(seed, s):
    return hashlib.sha256(f"{seed}:{s}".encode()).hexdigest()


def build_split(seed=7, test_fraction=0.2, target_macros=config.SLICE_MACROS, min_human_test=3,
                sites=None, support=None, human=None):
    sites = sorted(sites or all_sites())
    support = {m: set(s) & set(sites) for m, s in (support if support is not None else support_map()).items()}
    human = {m: set(s) & set(sites) for m, s in (human if human is not None else human_map()).items()}
    budget = max(1, round(test_fraction * len(sites)))

    need = {}                                        # (kind, macro) -> (required count, candidate sites)
    for m in target_macros:
        need[("human", m)] = (min_human_test, human.get(m, set()) & support.get(m, set()) or human.get(m, set()))
    for m, s in support.items():
        if len(s) >= 4:
            need[("support", m)] = (1, s)

    def train_floor(m):
        n = len(support.get(m, ()))
        return max(3, math.ceil(0.6 * n)) if n else 0

    test = []

    def ok(site):
        for m, s in support.items():
            if site in s and len(s - set(test) - {site}) < min(train_floor(m), len(s)):
                return False
        return True

    def deficit(key):
        req, cands = need[key]
        return max(0, req - len(set(test) & cands))

    order = sorted(sites, key=lambda s: _h(seed, s))
    while len(test) < budget:
        best, best_score = None, 0.0
        for s in order:
            if s in test or not ok(s):
                continue
            score = sum((3.0 if k[0] == "human" else 1.0) for k in need if deficit(k) and s in need[k][1])
            if score > best_score:
                best, best_score = s, score
        if best is None:
            break
        test.append(best)
    humans_any = set().union(*human.values()) if human else set()
    for s in sorted(order, key=lambda s: (s not in humans_any, _h(seed, s))):
        if len(test) >= budget:
            break
        if s not in test and ok(s):
            test.append(s)
    train = [s for s in sites if s not in test]
    coverage = {}
    for m in sorted(set(support) | set(human)):
        coverage[m] = {"train_sites": len(support.get(m, set()) - set(test)),
                       "test_sites": len(support.get(m, set()) & set(test)),
                       "test_sites_with_human_tasks": len(human.get(m, set()) & set(test))}
    unmet = {f"{k[0]}:{k[1]}": deficit(k) for k in need if deficit(k)}
    return {"version": 1, "created": time.strftime("%Y-%m-%d"), "seed": seed, "test_fraction": test_fraction,
            "method": __doc__.strip().splitlines()[0], "target_macros": list(target_macros),
            "min_human_test": min_human_test, "train": train, "test": sorted(test),
            "target_detail": {m: {"train_sites": sorted(support.get(m, set()) - set(test)),
                                  "test_sites": sorted(support.get(m, set()) & set(test)),
                                  "test_sites_with_human_tasks": sorted(human.get(m, set()) & set(test))}
                              for m in target_macros},
            "unmet_requirements": unmet, "coverage": coverage}


def load_split():
    if not config.SPLIT_PATH.exists():
        raise FileNotFoundError(f"{config.SPLIT_PATH} missing — run `python -m datagen split` first")
    return json.loads(config.SPLIT_PATH.read_text())


def ensure_split(force=False, **kw):
    """Load the persisted split; build it only when missing (or --force)."""
    if config.SPLIT_PATH.exists() and not force:
        return load_split()
    split = build_split(**kw)
    config.SPLIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.SPLIT_PATH.write_text(json.dumps(split, indent=1))
    return split


def train_sites():
    return list(load_split()["train"])


def assert_train(site):
    """Guard used by every stage that touches a site."""
    if site in set(load_split()["test"]):
        raise ValueError(f"{site} is a TEST site — the pipeline only touches train sites")
