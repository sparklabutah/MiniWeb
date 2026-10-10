"""Convert the data release (scripts/build_release.py's output) to the Hugging Face dataset layout: Parquet tables,
one per entity, with screenshots as image columns, so the data loads with `datasets.load_dataset` and shows in the
Hub's viewer. It follows the convention of web-agent datasets on the Hub (e.g. Multimodal-Mind2Web): one row per task,
one row per recorded step with its screenshot.

    python scripts/build_hf_dataset.py [--release data/release/miniweb-v1] [--out data/release/miniweb-v1-hf]

Tables (configs in the dataset card):
  sites                 the 65 websites: domain, split, hub, data source, license
  primitives            the macro registry: 46 base macros and 7 reasoning operations, final-set membership
  tasks                 the 376 human tasks (splits train / test / excluded): the task and verifier as evaluated, the
                        annotator's originals, provenance, the server and input logs of the demonstration
  demonstrations        one row per recorded event of the human demonstrations (action or observation), with the
                        page's HTML snapshot, accessibility tree and screenshot where recorded
  miniwebgen_trajectories / miniwebgen_steps
                        MiniWebGen's kept single-primitive trajectories and their steps with screenshots
  training_steps        MiniWebAgent's training data: one row per step in the agent harness's format (prompt
                        messages, target, the step's screenshot), with variant and validation flags
  task_centric_tasks / task_centric_steps
                        the task-centric comparison data: every proposed task with its judged outcome, and the
                        selected episodes' steps in the same format as training_steps
  single_primitive_test_tasks   the generated single-primitive tasks of the held-out sites (evaluation only)
  guides                MiniWebGen's per-primitive guides
The site database is converted separately (scripts/export_site_db.py) into site_db/.
"""
import argparse, glob, json, os, re, shutil

import datasets
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
IMG = datasets.Image()
S, I, F, B = datasets.Value("string"), datasets.Value("int64"), datasets.Value("float64"), datasets.Value("bool")
L = datasets.Sequence


# where our runs wrote browser downloads (a cluster job's scratch folder) and the address annotators used, which the
# release's own audit misses when a page truncated it; both become neutral values
SCRUB = [(re.compile(r"/scratch/local/[^\s\"'\\]*?(?=browser-use-downloads)"), "/tmp/"),
         (re.compile(r"/scratch/local/u\d+/(?:\d+/)?"), "/tmp/"),
         (re.compile(r"https?://[a-z0-9-]+-production(?:\.[\w.-]*)?"), "http://localhost:8080")]
LEAK = re.compile(r"/scratch/local/|\.railway\.app|https?://[a-z0-9-]+-production\b")


def clean(v):
    if isinstance(v, str):
        for rx, to in SCRUB:
            v = rx.sub(to, v)
    return v


def js(v):
    """Nested values are stored as JSON text; None stays null."""
    return None if v is None else json.dumps(v, ensure_ascii=False)


def load(path, default=None):
    return json.load(open(path)) if os.path.exists(path) else default


def image(path):
    if not path or not os.path.isfile(path):
        return None
    return {"bytes": open(path, "rb").read(), "path": os.path.basename(path)}


class Writer:
    """Streams rows into Parquet shards of about `shard_mb`, with the dataset features in the schema metadata."""

    def __init__(self, out, name, features, shard_mb=400, row_group=100):
        self.dir, self.name, self.features = out, name, datasets.Features(features)
        self.schema = self.features.arrow_schema
        self.shard_mb, self.row_group = shard_mb, row_group
        self.buf, self.bytes, self.shard, self.writer, self.rows = [], 0, 0, None, 0
        os.makedirs(out, exist_ok=True)

    def add(self, row):
        self.buf.append({k: clean(row.get(k)) for k in self.features})
        self.bytes += sum(len(v["bytes"]) for v in row.values() if isinstance(v, dict) and v.get("bytes")) + \
            sum(len(v) for v in row.values() if isinstance(v, str))
        if len(self.buf) >= self.row_group:
            self.flush()

    def flush(self):
        if not self.buf:
            return
        if self.writer is None:
            self.path = os.path.join(self.dir, f"{self.name}-{self.shard:05d}.parquet")
            self.writer = pq.ParquetWriter(self.path, self.schema, compression="zstd")
        self.writer.write_table(pa.Table.from_pylist(self.buf, schema=self.schema), row_group_size=self.row_group)
        self.rows += len(self.buf)
        self.buf = []
        if self.bytes > self.shard_mb * 2 ** 20:
            self.writer.close(); self.writer = None; self.shard += 1; self.bytes = 0

    def close(self):
        self.flush()
        if self.writer:
            self.writer.close()
        return self.rows


def write_all(out, name, features, rows, **kw):
    w = Writer(out, name, features, **kw)
    for r in rows:
        w.add(r)
    n = w.close()
    print(f"{os.path.relpath(out)}/{name}: {n} rows")
    return n


def sites(rel, out):
    rows = [json.loads(l) for l in open(os.path.join(rel, "sites.jsonl")) if l.strip()]
    feats = {k: (B if isinstance(rows[0].get(k), bool) else S) for k in rows[0]}
    return write_all(os.path.join(out, "sites"), "sites", feats,
                     ({k: (v if isinstance(v, bool) or v is None else str(v)) for k, v in r.items()} for r in rows))


def primitives(rel, out):
    reg = yaml.safe_load(open(os.path.join(rel, "primitives", "macros.yaml")))
    final = yaml.safe_load(open(os.path.join(rel, "primitives", "final_set.yaml")))
    fam = load(os.path.join(rel, "primitives", "families.json"), {})
    fam_of = {m: f for f, ms in fam.items() for m in ms} if isinstance(fam, dict) else {}
    kept = set(final.get("primitives", []))
    rows = []
    for name, e in (reg.get("macros") or {}).items():
        rows.append({"name": name, "kind": "macro", "family": fam_of.get(name), "group": e.get("group"),
                     "description": e.get("description"), "example": e.get("example"),
                     "aliases": [str(a) for a in e.get("aliases") or []], "in_final_set": name in kept,
                     "dropped": name not in kept, "entry": js(e)})
    for name, e in (reg.get("operations") or {}).items():
        e = e if isinstance(e, dict) else {"description": e}
        rows.append({"name": name, "kind": "operation", "family": None, "group": None,
                     "description": e.get("description"), "example": e.get("example"), "aliases": [],
                     "in_final_set": True, "dropped": False, "entry": js(e)})
    feats = {"name": S, "kind": S, "family": S, "group": S, "description": S, "example": S, "aliases": L(S),
             "in_final_set": B, "dropped": B, "entry": S}
    return write_all(os.path.join(out, "primitives"), "primitives", feats, rows)


TASK_FEATS = {"task_id": S, "split": S, "site": S, "sites": L(S), "instruction": S, "primitives": L(S),
              "author": S, "task": S, "verifier": S, "original_task": S, "original_verifier": S, "provenance": S,
              "index": S, "server_log": S, "beacon_log": S, "verification_walk": S, "num_events": I}
EVENT_KEYS = ["type", "action", "target", "selector", "value", "url", "title", "text", "timestamp"]
EVENT_FEATS = {"task_id": S, "split": S, "event_index": I, **{k: S for k in EVENT_KEYS}, "x": F, "y": F,
               "record": S, "html": S, "axtree": S, "screenshot": IMG}


def tasks(rel, out):
    index = {r["task_id"]: r for r in (json.loads(l) for l in open(os.path.join(rel, "tasks", "index.jsonl"))
                                       if l.strip())}
    n = 0
    for split in sorted(os.listdir(os.path.join(rel, "tasks"))):
        sd = os.path.join(rel, "tasks", split)
        if not os.path.isdir(sd):
            continue
        tw = Writer(os.path.join(out, "tasks"), split, TASK_FEATS, row_group=50)
        ew = Writer(os.path.join(out, "demonstrations"), split, EVENT_FEATS, row_group=50)
        for tid in sorted(os.listdir(sd)):
            d = os.path.join(sd, tid)
            t = load(os.path.join(d, "task.json"), {})
            traj = load(os.path.join(d, "demonstration", "trajectory.json"), []) or []
            ix = index.get(tid, {})
            tw.add({"task_id": tid, "split": split, "site": t.get("site") or ix.get("site"),
                    "sites": [str(s) for s in (t.get("sites") or ix.get("sites") or [])],
                    "instruction": t.get("instruction"), "primitives": [str(m) for m in t.get("macros") or []],
                    "author": ix.get("author"), "task": js(t), "verifier": js(load(os.path.join(d, "verifier.json"))),
                    "original_task": js(load(os.path.join(d, "original", "task.json"))),
                    "original_verifier": js(load(os.path.join(d, "original", "verifier.json"))),
                    "provenance": js(load(os.path.join(d, "provenance.json"))), "index": js(ix),
                    "server_log": js(load(os.path.join(d, "demonstration", "server_log.json"))),
                    "beacon_log": js(load(os.path.join(d, "demonstration", "beacon_log.json"))),
                    "verification_walk": js(load(os.path.join(d, "verification_walk", "walk.json"))),
                    "num_events": len(traj)})
            for i, r in enumerate(traj):
                shot = r.get("screenshot")
                ew.add({"task_id": tid, "split": split, "event_index": i,
                        **{k: (None if r.get(k) is None else str(r.get(k))) for k in EVENT_KEYS},
                        "x": float(r["x"]) if isinstance(r.get("x"), (int, float)) else None,
                        "y": float(r["y"]) if isinstance(r.get("y"), (int, float)) else None,
                        "record": js({k: v for k, v in r.items() if k not in ("snapshot", "axtree")}),
                        "html": r.get("snapshot"), "axtree": js(r.get("axtree")) if not isinstance(r.get("axtree"), str)
                        else r.get("axtree"),
                        "screenshot": image(os.path.join(d, "demonstration", shot)) if isinstance(shot, str) else None})
            ref = {r.get("screenshot") for r in traj}      # full-page captures (screenshot_full_page) become rows too
            sd_ = os.path.join(d, "demonstration", "screenshots")
            extra = sorted(f for f in (os.listdir(sd_) if os.path.isdir(sd_) else [])
                           if f"screenshots/{f}" not in ref)
            for k, fn in enumerate(extra):            # captures no recorded event points to, kept at the end
                ew.add({"task_id": tid, "split": split, "event_index": len(traj) + k, "type": "screenshot",
                        "screenshot": image(os.path.join(sd_, fn))})
            n += 1
        print(f"tasks/{split}: {tw.close()} tasks; demonstrations/{split}: {ew.close()} events")
    return n


def miniwebgen(rel, out):
    g = os.path.join(rel, "generated", "trajectories")
    tf = {"trajectory_id": S, "primitive": S, "operation": S, "site": S, "instruction": S, "subtask": S,
          "start_kind": S, "history_primitive": S, "history": S, "num_steps": I, "meta": S, "elements": S,
          "final_screenshot": IMG}
    sf = {"trajectory_id": S, "phase": S, "step": I, "action_type": S, "action": S, "elements": S, "screenshot": IMG}
    tw, sw = Writer(os.path.join(out, "miniwebgen_trajectories"), "train", tf, row_group=50), \
        Writer(os.path.join(out, "miniwebgen_steps"), "train", sf)
    for tid in sorted(os.listdir(g)):
        d = os.path.join(g, tid)
        if not os.path.isdir(d):
            continue
        tr, el, meta = load(os.path.join(d, "trajectory.json"), {}), load(os.path.join(d, "elements.json"), {}), \
            load(os.path.join(d, "meta.json"), {})
        steps = tr.get("steps") or []
        est = {s.get("i"): s for s in (el or {}).get("steps") or []}
        tw.add({"trajectory_id": tid, "primitive": tr.get("macro"), "operation": tr.get("op"), "site": tr.get("site"),
                "instruction": tr.get("instruction"), "subtask": tr.get("subtask"), "start_kind": tr.get("start_kind"),
                "history_primitive": tr.get("history_macro"), "history": js(tr.get("history")),
                "num_steps": len(steps), "meta": js(meta), "elements": js({k: v for k, v in (el or {}).items() if k != "steps"}),
                "final_screenshot": image(os.path.join(d, tr["final_screenshot"])) if tr.get("final_screenshot") else None})
        # a chained trajectory first replays the steps of another primitive (history), then performs its own (target)
        hst = {s.get("i"): s for s in (el or {}).get("history") or [] if isinstance(s, dict)}
        for phase, seq, els in (("history", tr.get("history") or [], hst), ("target", steps, est)):
            for s in seq:
                a = s.get("action") or {}
                sw.add({"trajectory_id": tid, "phase": phase, "step": s.get("i"), "action_type": a.get("type"),
                        "action": js(a), "elements": js(els.get(s.get("i"))),
                        "screenshot": image(os.path.join(d, s["screenshot"])) if s.get("screenshot") else None})
    print(f"miniwebgen_trajectories: {tw.close()}; miniwebgen_steps: {sw.close()}")


STEP_FEATS = {"episode": S, "variant": S, "parts": L(S), "task_id": S, "step": I, "segment": I, "primitive": S,
              "family": S, "op": S, "resolved": S, "memory_by": S, "messages": S, "target": S, "is_target": B,
              "validation": B, "image": IMG}
IMAGE_REF = re.compile(r"step_\d+\.png")


def step_rows(d, episode, variant, parts, validation):
    for line in open(os.path.join(d, "rows.jsonl")):
        if not line.strip():
            continue
        r = json.loads(line)
        m = IMAGE_REF.search(json.dumps(r.get("messages"))[-2000:]) or IMAGE_REF.search(json.dumps(r.get("messages")))
        yield {"episode": episode, "variant": variant, "parts": [str(p) for p in parts or []], "task_id": r.get("task_id"),
               "step": int(r["step"]) if r.get("step") is not None else None,
               "segment": int(r["segment"]) if r.get("segment") is not None else None, "primitive": r.get("macro"),
               "family": r.get("family"), "op": r.get("op"), "resolved": r.get("resolved"),
               "memory_by": r.get("memory_by"), "messages": js(r.get("messages")),
               "target": r.get("target") if isinstance(r.get("target"), str) else js(r.get("target")),
               "is_target": not (r.get("inject") or r.get("aug_prefix")), "validation": bool(validation),
               "image": image(os.path.join(d, m.group(0))) if m else None}


def training(rel, out):
    d0 = os.path.join(rel, "generated", "training_episodes")
    idx = [json.loads(l) for l in open(os.path.join(d0, "index.jsonl")) if l.strip()]
    w = Writer(os.path.join(out, "training_steps"), "train", STEP_FEATS)
    for r in idx:
        for row in step_rows(os.path.join(d0, r["episode"]), r["episode"], r.get("variant"), r.get("parts"),
                             r.get("validation")):
            w.add(row)
    print(f"training_steps: {w.close()} rows")


def task_centric(rel, out):
    tc = os.path.join(rel, "generated", "task_centric")
    rows = [json.loads(l) for l in open(os.path.join(tc, "tasks.jsonl")) if l.strip()]
    keys = sorted({k for r in rows for k in r})
    feats = {k: (B if all(isinstance(r.get(k), bool) or r.get(k) is None for r in rows) else S) for k in keys}
    feats.update({"episode": S, "judge": S})
    ep = os.path.join(tc, "episodes")
    have = set(os.listdir(ep))
    write_all(os.path.join(out, "task_centric_tasks"), "train", feats,
              ({**{k: (r.get(k) if feats[k] == B else (None if r.get(k) is None else
                                                         (r[k] if isinstance(r[k], str) else js(r[k])))) for k in keys},
                "episode": js(load(os.path.join(ep, r["task_id"], "episode.json"))) if r["task_id"] in have else None,
                "judge": js(load(os.path.join(ep, r["task_id"], "judge.json"))) if r["task_id"] in have else None}
               for r in rows), row_group=500)
    w = Writer(os.path.join(out, "task_centric_steps"), "train", STEP_FEATS)
    for e in sorted(have):
        for row in step_rows(os.path.join(ep, e), e, "task_centric", [e], False):
            w.add(row)
    print(f"task_centric_steps: {w.close()} rows")


def small_tables(rel, out):
    g = os.path.join(rel, "generated")
    rows = [json.loads(l) for l in open(os.path.join(g, "single_primitive_test_tasks.jsonl")) if l.strip()]
    keys = sorted({k for r in rows for k in r})
    write_all(os.path.join(out, "single_primitive_test_tasks"), "test", {k: S for k in keys},
              ({k: (None if r.get(k) is None else (r[k] if isinstance(r[k], str) else js(r[k]))) for k in keys}
               for r in rows), row_group=500)
    write_all(os.path.join(out, "guides"), "guides", {"primitive": S, "guide": S},
              ({"primitive": os.path.splitext(os.path.basename(f))[0], "guide": open(f).read()}
               for f in sorted(glob.glob(os.path.join(g, "guides", "*.md")))), row_group=500)


def audit(out):
    """Fail if a private path or the deployment's address is left in any text column."""
    import pyarrow.compute as pc
    bad = []
    for f in sorted(glob.glob(os.path.join(out, "**", "*.parquet"), recursive=True)):
        pf = pq.ParquetFile(f)
        cols = [n for n, t in zip(pf.schema_arrow.names, pf.schema_arrow.types) if pa.types.is_string(t)]
        for b in pf.iter_batches(batch_size=2000, columns=cols):
            for c in cols:
                n = pc.sum(pc.match_substring_regex(b.column(c), LEAK.pattern)).as_py() or 0
                if n:
                    bad.append((os.path.relpath(f, out), c, n))
    if bad:
        raise SystemExit(f"private strings left: {bad[:10]}")
    print("audit: no private paths or deployment addresses")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--release", default=os.path.join(ROOT, "data", "release", "miniweb-v1"))
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "release", "miniweb-v1-hf"))
    ap.add_argument("--only", nargs="*", help="build only these tables")
    a = ap.parse_args()
    out = os.path.join(a.out, "data")
    steps = {"sites": sites, "primitives": primitives, "tasks": tasks, "miniwebgen": miniwebgen, "training": training,
             "task_centric": task_centric, "small": small_tables}
    for name, fn in steps.items():
        if a.only and name not in a.only:
            continue
        for sub in {"tasks": ["tasks", "demonstrations"], "miniwebgen": ["miniwebgen_trajectories", "miniwebgen_steps"],
                    "training": ["training_steps"], "task_centric": ["task_centric_tasks", "task_centric_steps"],
                    "small": ["single_primitive_test_tasks", "guides"]}.get(name, [name]):
            shutil.rmtree(os.path.join(out, sub), ignore_errors=True)
        fn(a.release, out)
    audit(out)
    for f in ("summary.json",):
        shutil.copy(os.path.join(a.release, f), os.path.join(a.out, f))


if __name__ == "__main__":
    main()
