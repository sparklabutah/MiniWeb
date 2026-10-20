"""Build the MiniWeb data release: the paper's data, consolidated, split-labelled and free of personal information.

    python scripts/build_release.py [--out data/release/miniweb-v1] [--no-generated]

Reads the working data (data/annotations, data/datagen, data/webmix, data/sites.yaml, data/macros.yaml,
data/final_set.yaml) and writes one self-contained folder (layout and field definitions in its README.md):

  sites.jsonl                      the 65 sites: domain, split, hub, data source and license
  primitives/                      the macro registry, the final 37-primitive set and the 7 skill families
  tasks/{test,train,excluded}/     the 369 human tasks by split (test: the 62 that start on a held-out site; train: the
    <task_id>/                     304 on training sites only; excluded: 3 that start on a training site and use a held-out
                                   site, in neither split), each with its current (repaired) definition and verifier, the
                                   annotator's original definition and verifier from before the review (original/), the
                                   human demonstration (demonstration/) and, where a reviewer re-walked the task, that walk
  tasks/index.jsonl                one line per task: split, primitives, author, what was repaired, recording provenance and
                                   validity (valid / stale / rejected by the current verifier, as in the paper's Supp.)
  generated/                       MiniWebGen: the 3,128 kept trajectories (training sites only), the 4,614 training
                                   episodes built from them (plain / recovery / chain), the per-primitive guides, and the
                                   generated single-primitive test tasks of the held-out sites

Personal information: annotators appear only as pseudonyms (A1..A6, in order of their first task), derived from the data
at build time so no name is written in this script; their names are replaced in every field and free-text note, and in
site content they typed (as a whole value, so synthetic full names such as a site user's stay); the deployment host the
annotators used is replaced by the local server's address. The build ends with an audit of the written files and fails
if any annotator name or the deployment host remains outside synthetic site content.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import shutil
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
DATA = ROOT / "data"
ANN = DATA / "annotations"
HOST_RE = re.compile(r"https?://[\w.-]+\.up\.railway\.app|[\w.-]+\.up\.railway\.app")
LOCAL = "http://localhost:8080"
PERSON_KEYS = re.compile(r"^(annotator|reviewer|reviewed_by|rerecorded_by|verification_walk_by|walk_by|author|actor|by|"
                         r"recorded_by|edited_by|updated_by|user)$")
# a task's content fields: an original and a current definition differ in what is graded or shown to the agent
CONTENT_KEYS = ("instruction", "sites", "macros", "macro_edges", "macro_subtasks", "macro_spans", "macro_operations",
                "macro_required", "expected_answer", "answer_type", "alternatives", "expected_outcome", "starting_url",
                "requires_login", "qa_answers")
HUMAN_FILES = ("trajectory.json", "server_log.json", "beacon_log.json")


def fold(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).casefold()


# ── personal information ─────────────────────────────────────────────────────

class Pseudonyms:
    """Annotator names (the annotation folders, and every person field of every task) -> A1..An by first task date.
    Spelling variants of one name (case, accents) share a pseudonym."""

    def __init__(self, tasks):
        first, variants = {}, collections.defaultdict(set)
        for folder, t in tasks:
            for v in [folder, t.get("annotator")] + [t.get(k) for k in ("rerecorded_by", "verification_walk_by")]:
                if isinstance(v, str) and v.strip() and not v.lower().startswith(("claude", "ai", "auto")):
                    key = fold(v.strip())
                    variants[key].add(v.strip())
                    first[key] = min(first.get(key, "9"), str(t.get("saved_at") or "9"))
        order = sorted(first, key=lambda k: (first[k], k))
        self.of = {k: f"A{i + 1}" for i, k in enumerate(order)}
        names = sorted({n for vs in variants.values() for n in vs} | {k for k in self.of}, key=len, reverse=True)
        self.name_re = re.compile(r"(?<![\w])(" + "|".join(re.escape(n) for n in names) + r")(?![\w])", re.I)

    def person(self, v):
        if not isinstance(v, str):
            return v
        if v.lower().startswith(("claude", "ai")) or v.lower().endswith("-review"):
            return "AI review"                              # an LLM reviewer (claude-review, codex-review), not a person
        return self.of.get(fold(v.strip()), v)

    @staticmethod
    def in_full_name(s, start, end):
        """Part of a longer name ('Leila Haddad'): a synthetic site user, not an annotator."""
        return bool(re.search(r"[A-Z][a-z]+ $", s[max(0, start - 30):start]) or re.match(r" [A-Z][a-z]", s[end:end + 3]))

    def text(self, s):
        """Names -> pseudonyms in free text and site content, except as part of a longer name: instructions and pages
        mention synthetic users who share a first name with an annotator."""
        return self.name_re.sub(lambda m: m.group(0) if self.in_full_name(m.string, m.start(), m.end())
                                else self.of.get(fold(m.group(0)), m.group(0)), s)

    def scrub(self, obj):
        if isinstance(obj, dict):
            return {k: (self.person(v) if PERSON_KEYS.match(k) and isinstance(v, str) else self.scrub(v)) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self.scrub(v) for v in obj]
        if isinstance(obj, str):
            return HOST_RE.sub(lambda m: LOCAL if m.group(0).startswith("http") else "localhost:8080", self.text(obj))
        return obj


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, ensure_ascii=False))


def link_tree(src, dst):
    """Images: hard links (same disk, no copy), else copies."""
    for p in Path(src).rglob("*"):
        if p.is_file():
            q = dst / p.relative_to(src)
            q.parent.mkdir(parents=True, exist_ok=True)
            if not q.exists():
                try:
                    os.link(p, q)
                except OSError:
                    shutil.copy2(p, q)


# ── human tasks ──────────────────────────────────────────────────────────────

def recording_status(tasks):
    """valid / stale / verifier_rejected per task, as the paper's grader validation decides it (Supp. graders):
    stale if tagged stale, else whether the task's current verifier passes the gold recording."""
    from miniweb.annotation.app import _load_test_trajectory
    from miniwebagent.evaluate import grade_human, human_tasks
    by_id = {t["task_id"]: t for t in human_tasks(split="all")}
    out = {}
    for folder, t in tasks:
        tid = t["task_id"]
        if ((t.get("review_tag") or {}).get("tag")) == "stale":
            out[tid] = "stale"
            continue
        traj, answer, _ = _load_test_trajectory(folder, tid, "gold")
        out[tid] = "valid" if grade_human(by_id[tid], traj or [], answer)[0] else "verifier_rejected"
    return out


def splits():
    from miniwebagent.evaluate import human_tasks
    test = {t["task_id"] for t in human_tasks(split="test")}
    train = {t["task_id"] for t in human_tasks(split="train")}
    return test, train


def build_tasks(out, P, tasks, status):
    test, train = splits()
    index = []
    for folder, t in tasks:
        tid = t["task_id"]
        src = ANN / folder / Path(t["_dir"]).name
        split = "test" if tid in test else "train" if tid in train else "excluded"
        d = out / "tasks" / split / tid
        cur_v = json.loads((src / "verifier.json").read_text())
        before = json.loads((src / "before_review.json").read_text()) if (src / "before_review.json").exists() else {}
        orig_t, orig_v = before.get("task") or {}, before.get("verifier") or {}
        task = {k: v for k, v in t.items() if k != "_dir"}
        write_json(d / "task.json", P.scrub(task))
        write_json(d / "verifier.json", P.scrub(cur_v))
        if orig_t:
            write_json(d / "original" / "task.json", P.scrub(orig_t))
            write_json(d / "original" / "verifier.json", P.scrub(orig_v))
        for f in HUMAN_FILES:
            if (src / f).exists():
                write_json(d / "demonstration" / f, P.scrub(json.loads((src / f).read_text())))
        if (src / "screenshots").is_dir():
            link_tree(src / "screenshots", d / "demonstration" / "screenshots")
        if (src / "verification_walk.json").exists():
            write_json(d / "verification_walk" / "walk.json",
                       P.scrub(json.loads((src / "verification_walk.json").read_text())))
        changed = [k for k in CONTENT_KEYS if orig_t and k in orig_t and orig_t.get(k) != t.get(k)]
        if t.get("instruction_original") and t.get("instruction_original") != t.get("instruction") and "instruction" not in changed:
            changed.append("instruction")
        review = t.get("ai_review") or {}
        prov = {"task_id": tid, "split": split, "author": P.person(t.get("annotator")),
                "task": {"repaired": bool(changed), "changed_fields": changed,
                         "original": "original/task.json" if orig_t else None,
                         "review": {"recommendation": review.get("recommendation"),
                                    "changes": P.scrub(review.get("changes") or [])}},
                "verifier": {"repaired": bool(orig_v) and orig_v.get("macros") != cur_v.get("macros"),
                             "original": "original/verifier.json" if orig_v else None},
                "demonstration": {"provenance": "re-recorded" if t.get("rerecorded_at") else "original",
                                  "recorded_by": P.person(t.get("rerecorded_by") or t.get("annotator")),
                                  "rerecorded_at": t.get("rerecorded_at"), "status": status[tid],
                                  "screenshots": (src / "screenshots").is_dir()},
                "verification_walk": {"present": (src / "verification_walk.json").exists(),
                                      "walked_by": P.scrub(t.get("verification_walk_by"))}}
        write_json(d / "provenance.json", prov)
        index.append({"task_id": tid, "split": split, "site": t.get("site"),
                      "sites": [s["id"] if isinstance(s, dict) else s for s in (t.get("sites") or [t.get("site")])],
                      "primitives": [m for m in (t.get("macros") or []) if m], "author": prov["author"],
                      "task_repaired": prov["task"]["repaired"], "changed_fields": changed,
                      "verifier_repaired": prov["verifier"]["repaired"],
                      "demonstration": prov["demonstration"]["provenance"], "demonstration_status": status[tid],
                      "verification_walk": prov["verification_walk"]["present"], "path": f"tasks/{split}/{tid}"})
    (out / "tasks" / "index.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in index))
    return index


# ── generated data (MiniWebGen) ──────────────────────────────────────────────

def build_generated(out, train_sites):
    pool = (ROOT / "scripts" / "pools" / "pool3k_plain_ids.txt").read_text().split()
    episodes = (ROOT / "scripts" / "pools" / "pool3k_dirs.txt").read_text().split()
    kept = {}
    for k in sorted((DATA / "datagen" / "runs").glob("*/kept.jsonl")):
        for line in k.read_text().split("\n"):
            if line.strip():
                r = json.loads(line)
                kept[r["task_id"]] = {**r, "run": k.parent.name}
    g = out / "generated"
    tindex = []
    missing = []
    for tid in pool:
        r = kept[tid]
        assert r["site"] in train_sites, (tid, r["site"])
        acc = DATA / "datagen" / "runs" / r["run"] / "accepted" / tid
        if not (acc / "trajectory.json").exists():
            missing.append(tid)
            continue
        d = g / "trajectories" / tid
        for f in ("trajectory.json", "elements.json"):
            if (acc / f).exists():
                write_json(d / f, json.loads((acc / f).read_text()))
        if (acc / "screenshots").is_dir():
            link_tree(acc / "screenshots", d / "screenshots")
        meta = {k: r.get(k) for k in ("task_id", "macro", "site", "start_kind", "instruction", "backend", "judge", "run")}
        write_json(d / "meta.json", meta)
        tindex.append({k: meta[k] for k in ("task_id", "macro", "site", "start_kind")} | {"path": f"generated/trajectories/{tid}"})
    eindex, variants = [], collections.Counter()
    for e in episodes:
        src = DATA / "webmix" / "replay_v4" / e
        ep = json.loads((src / "episode.json").read_text())
        ep.pop("response_format", None)
        variant = ep.get("variant") or "plain"
        variants[variant] += 1
        d = g / "training_episodes" / e
        write_json(d / "episode.json", {**ep, "variant": variant})
        shutil.copy2(src / "rows.jsonl", d / "rows.jsonl")
        for p in src.glob("step_*.png"):
            if not (d / p.name).exists():
                try:
                    os.link(p, d / p.name)
                except OSError:
                    shutil.copy2(p, d / p.name)
        steps = sum(1 for line in (src / "rows.jsonl").read_text().split("\n") if line.strip())
        eindex.append({"episode": e, "variant": variant, "site": ep.get("site"), "macro": ep.get("macro"),
                       "parts": ep.get("parts") or [e.split("~")[0]], "steps": steps,
                       "path": f"generated/training_episodes/{e}"})
    (g / "trajectories" / "index.jsonl").write_text("".join(json.dumps(r) + "\n" for r in tindex))
    (g / "training_episodes" / "index.jsonl").write_text("".join(json.dumps(r) + "\n" for r in eindex))
    gd = g / "guides"
    gd.mkdir(parents=True, exist_ok=True)
    for p in sorted((DATA / "datagen" / "guides").glob("*.md")):
        shutil.copy2(p, gd / p.name)
    shutil.copy2(DATA / "webmix" / "valgen" / "val_v2.jsonl", g / "single_primitive_test_tasks.jsonl")
    return {"trajectories": len(tindex), "missing_exports": missing, "episodes": len(eindex), "variants": dict(variants),
            "steps": sum(r["steps"] for r in eindex), "guides": len(list(gd.glob("*.md")))}


def build_task_centric(out, train_sites):
    """The task-centric comparison data of Tab. 3 (miniwebgen.taskgen, InSTA's pipeline on the training sites): every
    proposed task with its attempt's judged outcome, and the selected episodes in the agent harness's row format with
    the judge's verdict."""
    T = DATA / "webmix" / "taskgen"
    tasks = [json.loads(line) for line in (T / "runs" / "v1" / "tasks.jsonl").read_text().split("\n") if line.strip()]
    judged = {f.stem: json.loads(f.read_text()) for f in (T / "runs" / "v1_judge").glob("tg-*.json")}
    selected = sorted(p.name for p in (T / "rows_27k").iterdir() if p.is_dir() and p.name.startswith("tg-"))
    g = out / "generated" / "task_centric"
    rows = 0
    for e in selected:
        src, d = T / "rows_27k" / e, g / "episodes" / e
        write_json(d / "episode.json", json.loads((src / "episode.json").read_text()))
        shutil.copy2(src / "rows.jsonl", d / "rows.jsonl")
        rows += sum(1 for line in (src / "rows.jsonl").read_text().split("\n") if line.strip())
        for img in src.glob("step_*.png"):
            if not (d / img.name).exists():
                try:
                    os.link(img, d / img.name)
                except OSError:
                    shutil.copy2(img, d / img.name)
        if e in judged:
            write_json(d / "judge.json", judged[e])
    chosen = set(selected)
    index = []
    for t in tasks:
        assert t["site"] in train_sites, (t["task_id"], t["site"])
        j = judged.get(t["task_id"])
        index.append({k: t.get(k) for k in ("task_id", "site", "instruction", "start_path", "task_kind")}
                     | {"judged_success": None if j is None else bool(j.get("predicted_label")),
                        "selected": t["task_id"] in chosen})
    (g / "tasks.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in index))
    return {"proposed": len(tasks), "judged": len(judged),
            "judged_success": sum(bool(j.get("predicted_label")) for j in judged.values()),
            "episodes": len(selected), "rows": rows, "sites": len({t["site"] for t in index if t["selected"]})}


def finalize_generated(out):
    """Per training episode: its rows, the rows that are training targets (an injected mistake and the replayed prefix
    of a recovery episode are not), and whether it falls in the 5% held out for validation loss (webmix.train's rules),
    so the release reproduces the paper's 27.6K fitted steps."""
    from miniwebagent import train as T
    d = out / "generated" / "training_episodes"
    idx = [json.loads(line) for line in (d / "index.jsonl").read_text().split("\n") if line.strip()]
    for r in idx:
        ep = json.loads((d / r["episode"] / "episode.json").read_text())
        rows = [json.loads(line) for line in (d / r["episode"] / "rows.jsonl").read_text().split("\n") if line.strip()]
        tgt = [x for x in rows if not (x.get("inject") or x.get("aug_prefix"))]
        for x in tgt:
            x["parts"] = ep.get("parts")
        r.update(rows=len(rows), target_rows=len(tgt), validation=bool(tgt) and T.row_is_val(tgt[0]))
    (d / "index.jsonl").write_text("".join(json.dumps(r) + "\n" for r in idx))
    return {"rows": sum(r["rows"] for r in idx), "target_rows": sum(r["target_rows"] for r in idx),
            "fitted_rows": sum(r["target_rows"] for r in idx if not r["validation"])}


# ── audit ────────────────────────────────────────────────────────────────────

HUMAN_PARTS = ("tasks", "generated/guides")      # what annotators wrote, recorded or reviewed (the guides are distilled
                                                 # from their demonstrations); the rest is generated by code on synthetic sites


def audit(out, P):
    """The deployment host must be gone from every written text file, and annotator names from everything humans touched
    (HUMAN_PARTS and the top-level files). -> (findings, full-name contexts left in place for review: synthetic site users
    who share a first name with an annotator)."""
    bad, kept = collections.Counter(), collections.Counter()
    for p in out.rglob("*"):
        if p.suffix not in (".json", ".jsonl", ".md", ".yaml") or not p.is_file():
            continue
        s = p.read_text(errors="ignore")
        if HOST_RE.search(s):
            bad[("host", str(p.relative_to(out)))] += 1
        rel = str(p.relative_to(out))
        if "/" in rel and not rel.startswith(HUMAN_PARTS):
            continue
        for m in P.name_re.finditer(s):
            ctx = re.sub(r"\s+", " ", s[max(0, m.start() - 25):m.end() + 15])
            if P.in_full_name(s, m.start(), m.end()):
                kept[re.sub(r"\s+", " ", s[max(0, m.start() - 12):m.end() + 10]).strip()] += 1
            else:
                bad[("name", str(p.relative_to(out)), ctx)] += 1
    return bad, kept


# ── data card ─────────────────────────────────────────────────────────────────

def write_card(out, sm):
    """README.md of the release, every number from this build's summary."""
    t, d, g, rp = sm["tasks"], sm["demonstrations"], sm.get("generated") or {}, sm.get("repaired_parts", {})
    n = sum(t.values())
    v, tc = g.get("variants", {}), g.get("task_centric") or {}
    text = f"""# MiniWeb data, release v1

The data behind the MiniWeb paper: {sm['sites']} synthetic websites, {n} human-written tasks with their verifiers and
demonstrations, and the MiniWebGen training data generated on the training sites. Built by `scripts/build_release.py`
from the working data; every count below comes from `summary.json`.

## Layout

```
sites.jsonl                  {sm['sites']} sites: domain, split, hub, data source, license
primitives/                  macros.yaml (46 base macros, 7 reasoning operations), final_set.yaml (the 37 primitives
                             of the final set and the 9 dropped), families.json (7 skill families)
tasks/index.jsonl            one line per human task: split, primitives, author, what was repaired, demonstration
tasks/<split>/<task_id>/
  task.json                  the task as evaluated (after review)
  verifier.json              its verifier as evaluated
  original/task.json         the annotator's task before the review
  original/verifier.json     the annotator's verifier before the review
  demonstration/             the human recording: trajectory.json (actions and observations), server_log.json
                             (backend requests), beacon_log.json (input events), screenshots/
  verification_walk/walk.json   a second walk-through by a reviewer, where one exists
  provenance.json            split, author, repaired parts, demonstration provenance and status
generated/
  trajectories/<task_id>/    MiniWebGen's kept single-primitive trajectories: trajectory.json, elements.json,
                             screenshots/, meta.json (primitive, site, instruction, backend verdict)
  training_episodes/<id>/    the training episodes built from them: episode.json, rows.jsonl (prompt and target per
                             step, in the agent harness's format), step_*.png
  guides/                    the per-primitive guides MiniWebGen distills from human demonstrations
  single_primitive_test_tasks.jsonl   generated single-primitive tasks of the held-out sites (evaluation only)
  task_centric/              the task-centric comparison data: tasks.jsonl (every proposed task, its judged outcome,
                             whether it was selected), episodes/<task_id>/ (episode.json, rows.jsonl, step_*.png,
                             judge.json)
```

## Splits

The 13 held-out (test) sites were fixed before any data was generated; the other 52 are training sites
(`sites.jsonl`, field `split`).

- `tasks/test/`: {t.get('test', 0)} tasks that start on a held-out site. The evaluation set of the paper.
- `tasks/train/`: {t.get('train', 0)} tasks that use training sites only. Used for development and as human
  demonstrations for MiniWebGen's guides.
- `tasks/excluded/`: {t.get('excluded', 0)} tasks that start on a training site and also use a held-out site. Neither
  split uses them.
- `generated/` holds training-site data only. `single_primitive_test_tasks.jsonl` is the exception: tasks generated on
  the held-out sites for evaluation, never executed for training.

## Original and repaired

Every human task went through a review after annotation, and the release keeps both versions.

- `original/` is the annotator's task and verifier before the review; `task.json` and `verifier.json` are the
  versions the paper evaluates. `provenance.json` lists the fields that changed. Across the {n} tasks the review
  reworded {rp.get('instruction', 0)} instructions, changed the primitive chain of {rp.get('macros', 0)}, re-marked
  primitive spans in {rp.get('macro_spans', 0)}, changed the expected answer of {rp.get('expected_answer', 0)} and the
  start page of {rp.get('starting_url', 0)}, and changed {sm.get('verifier_repaired', 0)} verifiers.
- `demonstration/` is the annotator's original recording for {n - sm.get('re_recorded', 0)} tasks and a re-recording
  for {sm.get('re_recorded', 0)} (field `demonstration.provenance` is `original` or `re-recorded`; the replaced
  recordings were not kept). {sm.get('verification_walks', 0)} tasks also have a reviewer's walk-through.
- `demonstration.status` says whether the recording still stands in for a correct episode, as the paper's grader
  validation decides it: `valid` ({d.get('valid', 0)}) passes the task's current verifier; `stale` ({d.get('stale', 0)})
  predates a change to its site, data or task; `verifier_rejected` ({d.get('verifier_rejected', 0)}) fails the current
  verifier, for example an early recording whose recorder missed a form submission. Fuzzy text checks are judged by
  an LLM, so a borderline recording can pass in one run and fail in another.

## Generated data (MiniWebGen)

- {g.get('trajectories', 0)} kept trajectories, each verified by the backend change it was meant to cause.
- {g.get('episodes', 0)} training episodes (`variant` in `episode.json` and the index): {v.get('plain', 0)} `plain`
  replays of those trajectories, {v.get('recovery', 0)} `recovery` episodes that inject a mistake and then correct it,
  and {v.get('chain', 0)} `chain` episodes that join two trajectories of one site.
- {g.get('rows', 0):,} rows. In a recovery episode the injected mistake and the replayed prefix before it are marked
  (`inject`, `aug_prefix`) and are not training targets, which leaves {g.get('target_rows', 0):,}; holding out 5% of the
  trajectories for validation loss (`validation` in the index) leaves the {g.get('fitted_rows', 0):,} steps the paper's
  executor is fitted on.

## Task-centric comparison data

The paper compares MiniWebGen's skill-centric data with task-centric data of the same size, collected on the same
training sites with a reimplementation of InSTA's pipeline (`src/miniwebgen/taskgen.py`). Gemini 3.5 Flash proposed
{tc.get('proposed', 0):,} goal-level tasks; the untrained Qwen3.5-4B attempted each in the agent harness, writing every step;
Gemini 3.5 Flash judged {tc.get('judged', 0):,} episodes from their screenshots, actions, the server's request log and
data changes, and accepted {tc.get('judged_success', 0):,}. {tc.get('episodes', 0):,} of them, drawn round-robin over
{tc.get('sites', 0)} sites, make the {tc.get('rows', 0):,} training rows. The judge is not a verifier: on the human tasks of
the training sites it agrees with the task verifiers on 87.1% of episodes, with 77.5% precision, so some selected
episodes do not complete their task. `judge.json` keeps its verdict and its reasons per part of the task.

## Personal information

- Annotators appear only as pseudonyms A1 to A{sm.get('authors', 6)}, in the order of their first task, in every field,
  review note and walk-through. AI reviewers appear as `AI review`.
- Addresses of the deployment the annotators worked on are replaced with the local server's address.
- The build audits every file it writes and fails if an annotator name or that address remains. Names of site users
  (for example `Leila Haddad`) are synthetic and are kept.
- Sites seeded from public datasets show those datasets' content, including names and addresses in the Enron email
  corpus and user names from the WebArena Reddit and GitLab environments, under the licenses in `sites.jsonl`.
"""
    (out / "README.md").write_text(text)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DATA / "release" / "miniweb-v1"))
    ap.add_argument("--no-generated", action="store_true")
    ap.add_argument("--audit-only", action="store_true", help="re-run the audit on an existing build (updates summary.json)")
    ap.add_argument("--finalize", action="store_true", help="training-row counts and the data card for an existing build")
    a = ap.parse_args(argv)
    out = Path(a.out)
    if a.finalize:
        summary = json.loads((out / "summary.json").read_text())
        summary["generated"].update(finalize_generated(out))
        summary["generated"].pop("steps", None)
        write_json(out / "summary.json", summary)
        write_card(out, summary)
        print(json.dumps(summary["generated"], indent=1))
        return
    if a.audit_only:
        tasks = [(f.parent.parent.name, json.loads(f.read_text())) for f in sorted(ANN.glob("*/*/task.json"))]
        P = Pseudonyms(tasks)
        bad, kept = audit(out, P)
        summary = json.loads((out / "summary.json").read_text())
        summary.update(audit_findings=len(bad))
        summary.pop("full_names_kept", None)
        write_json(out / "summary.json", summary)
        for k, n in list(bad.items())[:20]:
            print("  AUDIT", n, k)
        print(f"audit: {len(bad)} findings; {sum(kept.values())} synthetic full names kept")
        sys.exit("personal information left in the release" if bad else 0)
    if out.exists():
        shutil.rmtree(out)                                   # a build output, rebuilt from data/ every time
    out.mkdir(parents=True)
    tasks = []
    for f in sorted(ANN.glob("*/*/task.json")):
        t = json.loads(f.read_text())
        t["_dir"] = str(f.parent)
        tasks.append((f.parent.parent.name, t))
    P = Pseudonyms(tasks)
    import yaml
    sites = yaml.safe_load((DATA / "sites.yaml").read_text())["sites"]
    (out / "sites.jsonl").write_text("".join(json.dumps(s, ensure_ascii=False) + "\n" for s in sites))
    prim = out / "primitives"
    prim.mkdir()
    for f in ("macros.yaml", "final_set.yaml"):
        shutil.copy2(DATA / f, prim / f)
    from miniwebgen.viewer import FAMILIES
    write_json(prim / "families.json", FAMILIES)
    print(f"grading the {len(tasks)} demonstrations with their current verifiers ...", flush=True)
    status = recording_status(tasks)
    index = build_tasks(out, P, tasks, status)
    gen = None if a.no_generated else build_generated(out, {s["id"] for s in sites if s["split"] == "train"})
    if gen:
        gen.pop("steps", None)
        gen.update(finalize_generated(out))
        gen["task_centric"] = build_task_centric(out, {s["id"] for s in sites if s["split"] == "train"})
    bad, kept = audit(out, P)
    summary = {"sites": len(sites), "tasks": collections.Counter(r["split"] for r in index),
               "demonstrations": collections.Counter(r["demonstration_status"] for r in index),
               "re_recorded": sum(r["demonstration"] == "re-recorded" for r in index),
               "task_repaired": sum(r["task_repaired"] for r in index),
               "repaired_parts": collections.Counter(f for r in index for f in r["changed_fields"]),
               "verifier_repaired": sum(r["verifier_repaired"] for r in index),
               "verification_walks": sum(r["verification_walk"] for r in index), "authors": len(P.of),
               "generated": gen, "audit_findings": len(bad)}
    # the kept full names go to the log only: listed in the release they would show which first names annotators have
    print("synthetic full names kept:", dict(kept.most_common(30)), flush=True)
    write_json(out / "summary.json", summary)
    write_card(out, json.loads((out / "summary.json").read_text()))
    print(json.dumps(summary, indent=1, default=dict))
    for k, n in list(bad.items())[:20]:
        print("  AUDIT", n, k)
    if bad:
        sys.exit("personal information left in the release (see above)")


if __name__ == "__main__":
    main()
