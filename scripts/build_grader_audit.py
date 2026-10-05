"""Build the grader-audit sample: blind cases of RQ1 agent episodes for human labels of each required primitive.

Review round 1, item C1: the verifier and the VLM judge were validated on annotator recordings only, never against
human labels of agent episodes. This samples episodes from the ten RQ1 runs, stratified by how the two graders
judged the task (both pass, both fail, judge only, verifier only), spread over agents and oversampling episodes
with a Drag & gesture primitive, and writes

  data/grader_audit/cases/<case_id>/case.json + s01.jpg ...   the blind cases (no grader verdicts), uploaded with
                                                               scripts/upload_db_railway.py --grader-audit
  data/grader_audit/key.json                                   per case: run, agent, task, stratum, both graders'
                                                               task and per-primitive verdicts (stays local)

    python scripts/build_grader_audit.py [--n 120] [--overlap 40] [--seed 0]

Labels are scored against the key by scripts/grader_audit_report.py.
"""
import argparse, ast, json, os, random, re, shutil, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from annotation import macros as R  # noqa: E402
from datagen.viewer import FAMILIES  # noqa: E402
from webmix.rq1_analysis import RUNS  # noqa: E402

EVAL, ANN, OUT = ROOT / "data/webmix/eval", ROOT / "data/annotations", ROOT / "data/grader_audit"
FAM = {m: f for f, ms in FAMILIES.items() for m in ms}
DRAG = "Drag & gesture"
# share of each stratum in the sample; the report reweights by the strata's sizes in the full population
SHARES = {"judge_only": 0.30, "verifier_only": 0.20, "both_pass": 0.25, "both_fail": 0.25}
IMG_DIRS = ("screenshots", "screens", "fara", "fara7b")
MAX_IMGS, WIDTH = 40, 1024
STATIC = re.compile(r"\.(js|css|png|jpe?g|gif|svg|ico|woff2?|ttf|map|webp)(\?|$)|/static/|/_player/|favicon")


def _nat(s):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)]


def episodes():
    """Every judged RQ1 episode with both graders' verdicts: the population of the paper's agreement numbers."""
    eps = []
    for agent, run in RUNS.items():
        jf, rf = EVAL / run / "judge.jsonl", EVAL / run / "results.jsonl"
        if not jf.exists():
            continue
        ver = {}
        for line in rf.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                d = r.get("detail") or {}
                if isinstance(d, str):                           # some runs stored the dict's repr
                    try:
                        d = ast.literal_eval(d)
                    except (ValueError, SyntaxError):
                        d = {}
                ver[r["task_id"]] = d if isinstance(d, dict) else {}
        for line in jf.read_text().splitlines():
            r = json.loads(line) if line.strip() else {}
            if r.get("passed") is None or r.get("verifier") is None:
                continue
            j, v = bool(r["passed"]), bool(r["verifier"])
            stratum = {(True, True): "both_pass", (False, False): "both_fail",
                       (True, False): "judge_only", (False, True): "verifier_only"}[(j, v)]
            inst = {k: x for k, x in r["instances"].items() if x.get("required", True)}
            eps.append({"agent": agent, "run": run, "task_id": r["task_id"], "key": r["key"], "stratum": stratum,
                        "judge": j, "verifier": v, "instances": inst,
                        "judge_instances": {k: bool(x.get("passed")) for k, x in inst.items()},
                        "verifier_instances": {k: bool(ver.get(r["task_id"], {}).get(k)) for k in inst},
                        "drag": any(FAM.get(x["macro"]) == DRAG for x in inst.values())})
    return eps


def sample(eps, n, seed):
    """Per stratum: round-robin over agents, drag episodes first until a third of the stratum, distinct tasks."""
    rng = random.Random(seed)
    by = defaultdict(lambda: defaultdict(list))
    for e in eps:
        by[e["stratum"]][e["agent"]].append(e)
    picked = []
    for stratum, share in SHARES.items():
        want = round(n * share)
        pools = by[stratum]
        for a in pools:
            rng.shuffle(pools[a])
            pools[a].sort(key=lambda e: not e["drag"])          # stable: drag episodes first, random within
        n_drag_cap, got, used_tasks = want // 3, [], set()
        agents = sorted(pools)
        rng.shuffle(agents)
        while len(got) < want and any(pools[a] for a in agents):
            for a in agents:
                if len(got) >= want:
                    break
                n_drag = sum(e["drag"] for e in got)
                cand = [e for e in pools[a] if e["key"] not in used_tasks and (not e["drag"] or n_drag < n_drag_cap)]
                if not cand:
                    cand = [e for e in pools[a] if e["key"] not in used_tasks]
                if not cand:
                    pools[a] = []
                    continue
                e = cand[0]
                pools[a].remove(e)
                got.append(e)
                used_tasks.add(e["key"])
        picked += got
    rng.shuffle(picked)
    return picked


def images(ep_dir):
    for d in IMG_DIRS:
        p = ep_dir / d
        if not p.is_dir():
            continue
        fs = sorted((f for f in os.listdir(p) if f.lower().endswith((".png", ".jpg", ".jpeg"))), key=_nat)
        if d == "fara":                                      # pre/post pairs per step: the first pre, then every post
            fs = [f for f in fs if f == "screenshot_0_pre.png" or f.endswith("_post.png")]
        if fs:
            if len(fs) > MAX_IMGS:                           # evenly spaced, always keeping the last
                idx = sorted({round(i * (len(fs) - 1) / (MAX_IMGS - 1)) for i in range(MAX_IMGS)})
                fs = [fs[i] for i in idx]
            return [p / f for f in fs]
    return []


def events(traj):
    """The recorder's log in one format for every agent: page loads, actions, and the non-static requests."""
    out, t0 = [], None
    for x in traj:
        ts = x.get("timestamp", "")
        kind = x.get("type")
        if kind == "observation":
            out.append({"ts": ts, "kind": "page", "text": f"{x.get('url', '')}  —  {x.get('title', '')}"})
        elif kind == "action":
            bits = [x.get("action", "")]
            for k in ("target", "selector"):
                if x.get(k):
                    bits.append(str(x[k])[:120])
                    break
            for k in ("text", "value", "key", "direction"):
                if x.get(k) not in (None, ""):
                    bits.append(f"{k}={str(x[k])[:160]!r}")
            if x.get("x") is not None:
                bits.append(f"@({x.get('x')},{x.get('y')})")
            out.append({"ts": ts, "kind": "action", "text": " ".join(b for b in bits if b)})
        elif kind == "network":
            url = x.get("url", "")
            if STATIC.search(url):
                continue
            body = x.get("requestBody")
            text = f"{x.get('method', '')} {url} → {x.get('status', '')}"
            if body not in (None, "", {}):
                text += f"  body: {json.dumps(body)[:300] if not isinstance(body, str) else body[:300]}"
            out.append({"ts": ts, "kind": "request", "text": text})
    out.sort(key=lambda e: e["ts"])
    return out


def build_case(cid, e, cdir):
    from PIL import Image
    task = json.loads((ANN / e["key"] / "task.json").read_text())
    ep = EVAL / e["run"] / e["task_id"]
    g = json.loads((ep / "grade_inputs.json").read_text())
    prims = []
    for k, x in e["instances"].items():
        tag = next((t for t in task.get("macro_tags", []) if (t.get("instance") or t["macro"]) == k), {})
        prims.append({"instance": k, "macro": x["macro"], "family": FAM.get(x["macro"], ""),
                      "description": R.describe(x["macro"]).get("description", ""),
                      "rubric": R.rubric(x["macro"]), "subtask": tag.get("subtask", ""),
                      "reference": x.get("reference_target", "")})
    cdir.mkdir(parents=True, exist_ok=True)
    imgs = []
    for i, src in enumerate(images(ep), 1):
        name = f"s{i:02d}.jpg"
        im = Image.open(src).convert("RGB")
        if im.width > WIDTH:
            im = im.resize((WIDTH, round(im.height * WIDTH / im.width)), Image.LANCZOS)
        im.save(cdir / name, "JPEG", quality=72, optimize=True)
        imgs.append(name)
    has_report = any(p["macro"] == "report_information" for p in prims)
    case = {"id": cid, "instruction": task.get("instruction", ""), "sites": task.get("sites") or [task.get("site")],
            "expected_answer": task.get("expected_answer") if has_report else None,
            "agent_answer": g.get("answer") or "", "primitives": prims, "images": imgs, "events": events(g["traj"])}
    (cdir / "case.json").write_text(json.dumps(case, indent=1, ensure_ascii=False))
    return len(imgs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=120, help="episodes to sample")
    ap.add_argument("--overlap", type=int, default=40, help="cases every labeler does (inter-labeler agreement)")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    eps = episodes()
    pop = Counter(e["stratum"] for e in eps)
    picked = sample(eps, args.n, args.seed)
    if (OUT / "cases").exists():
        shutil.rmtree(OUT / "cases")
    key, n_img = {}, 0
    for i, e in enumerate(picked, 1):
        cid = f"g{i:03d}"
        n_img += build_case(cid, e, OUT / "cases" / cid)
        key[cid] = {k: e[k] for k in ("agent", "run", "task_id", "key", "stratum", "judge", "verifier",
                                      "judge_instances", "verifier_instances", "drag")}
        key[cid]["overlap"] = i <= args.overlap
    order = {"order": list(key), "overlap": [c for c in key if key[c]["overlap"]]}
    (OUT / "cases" / "_index").mkdir(parents=True, exist_ok=True)
    (OUT / "cases" / "_index" / "order.json").write_text(json.dumps(order))
    (OUT / "key.json").write_text(json.dumps({"population": dict(pop), "seed": args.seed, "cases": key}, indent=1))
    s = Counter(k["stratum"] for k in key.values())
    print(f"population {sum(pop.values())} episodes {dict(pop)}")
    print(f"sample {len(key)} cases {dict(s)}; drag {sum(k['drag'] for k in key.values())}; "
          f"agents {dict(Counter(k['agent'] for k in key.values()))}")
    print(f"primitives to label {sum(len(k['judge_instances']) for k in key.values())}; images {n_img}; "
          f"overlap {args.overlap} -> {OUT / 'cases'}")


if __name__ == "__main__":
    main()
