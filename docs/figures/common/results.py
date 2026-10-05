"""Read evaluation results from the run directories, for the figure scripts. All paths are relative to the repo root.

MiniWeb runs (webmix.evaluate): results.jsonl, one record per task with `ok` (task verifier) and `macro`.
WebArena-Lite runs (webmix.wa): results.jsonl with `score` per task.
WebVoyager judge dirs (webmix.om2w_judge): one <task>.json per task with `predicted_label`.
Online-Mind2Web judge dirs: WebJudge*auto_eval_results.json, one JSON record per line.
A task missing from a judge dir counts as failed, as in the paper's protocol.
"""
import collections, glob, json, os, statistics as st

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
# The paper reports only well-covered primitives: those with at least this many required instances in the human
# tasks. The rest (too site-specific to recur) were dropped as the final refinement after annotation.
MIN_INSTANCES = 3


def _p(path):
    return path if os.path.isabs(path) else os.path.join(ROOT, path)


def _jl(path):
    return [json.loads(l) for l in open(path) if l.strip()]


def _records(run):
    """{task_id: last record} of one run. Runs graded on granite (no LLM key there, so free-text answers fail the QA
    tier) are re-graded locally into results_regraded.jsonl (`webmix.evaluate --regrade`); that file wins when present."""
    regraded = os.path.join(_p(run), "results_regraded.jsonl")
    path = regraded if os.path.exists(regraded) else os.path.join(_p(run), "results.jsonl")
    return {r["task_id"]: r for r in _jl(path)}


def human_tasks():
    return [json.load(open(f)) for f in glob.glob(os.path.join(ROOT, "data", "annotations", "*", "*", "task.json"))]


def well_covered(min_instances=MIN_INSTANCES):
    """The primitives with at least `min_instances` required instances in the human tasks."""
    n = collections.Counter(g["macro"] for t in human_tasks() for g in t["macro_tags"] if g.get("required", True))
    return {m for m, c in n.items() if c >= min_instances}


def primitive_filter(spec):
    """A task-set option `primitives:` -> the set of primitives to keep (None keeps every task)."""
    if spec in (None, "all"):
        return None
    if spec == "well_covered":
        return well_covered()
    return set(spec)


def task_outcomes(kind, run, tasks=None, only=None):
    """{task_id: success in [0, 1]} of one run. Live-web tasks missing from a judge dir count as failed."""
    if kind in ("miniweb", "webarena"):
        rs = _records(run)
        if only is not None:
            rs = {k: r for k, r in rs.items() if r.get("macro") in only}
        return {k: float(bool(r.get("ok"))) if kind == "miniweb" else float(r["score"]) for k, r in rs.items()}
    if kind == "webvoyager":
        ids = [json.loads(l)["id"] for l in open(_p(tasks))]
        lab = {}
        for f in glob.glob(os.path.join(_p(run), "*--*.json")):
            d = json.load(open(f))
            lab[d["task_id"]] = str(d.get("predicted_label")) == "1"
        return {i: float(lab.get(i, False)) for i in ids}
    if kind == "om2w":
        ids = [t["task_id"] for t in json.load(open(_p(tasks)))]
        lab = {}
        for f in glob.glob(os.path.join(_p(run), "WebJudge*auto_eval_results.json")):
            for r in _jl(f):
                lab[r.get("task_id")] = int(r.get("predicted_label", 0)) == 1
        return {i: float(lab.get(i, False)) for i in ids}
    raise ValueError(kind)


def task_rates(kind, runs, tasks=None, only=None):
    """Success rate (%) of each run, by benchmark kind: miniweb | webarena | webvoyager | om2w. `only`: for
    single-primitive MiniWeb sets, keep the tasks whose primitive is in this set."""
    out = []
    for run in runs:
        if kind == "miniweb":
            rs = _records(run)
            if only is not None:
                rs = {k: r for k, r in rs.items() if r.get("macro") in only}
            out.append(100 * sum(bool(r.get("ok")) for r in rs.values()) / len(rs))
        elif kind == "webarena":
            rs = _records(run)
            out.append(100 * st.mean(float(r["score"]) for r in rs.values()))
        elif kind == "webvoyager":
            ids = [json.loads(l)["id"] for l in open(_p(tasks))]
            lab = {}
            for f in glob.glob(os.path.join(_p(run), "*--*.json")):
                d = json.load(open(f))
                lab[d["task_id"]] = str(d.get("predicted_label")) == "1"
            out.append(100 * sum(lab.get(i, False) for i in ids) / len(ids))
        elif kind == "om2w":
            ids = [t["task_id"] for t in json.load(open(_p(tasks)))]
            lab = {}
            for f in glob.glob(os.path.join(_p(run), "WebJudge*auto_eval_results.json")):
                for r in _jl(f):
                    lab[r.get("task_id")] = int(r.get("predicted_label", 0)) == 1
            out.append(100 * sum(lab.get(i, False) for i in ids) / len(ids))
        else:
            raise ValueError(kind)
    return out


def instance_family_counts(runs, family_of, only=None):
    """{family: [passed, total]} over the primitive instances inside multi-step MiniWeb tasks: each record's `detail`
    holds the task verifier's verdict per primitive ({primitive: bool})."""
    import ast
    fam = {}
    for run in runs:
        for r in _records(run).values():
            try:
                d = ast.literal_eval(r.get("detail") or "")
            except (ValueError, SyntaxError):
                continue
            if not isinstance(d, dict):
                continue
            for m, ok in d.items():
                if only is not None and m not in only:
                    continue
                for f in (family_of.get(m, "Other"), "All"):
                    c = fam.setdefault(f, [0, 0])
                    c[0] += bool(ok)
                    c[1] += 1
    return fam


def family_counts(runs, family_of, only=None):
    """{family: [passed, total]} over the tasks of MiniWeb runs whose records carry `macro` (single-primitive sets)."""
    fam = {}
    for run in runs:
        for r in _records(run).values():
            if only is not None and r.get("macro") not in only:
                continue
            f = family_of.get(r.get("macro"), "Other")
            c = fam.setdefault(f, [0, 0])
            c[0] += bool(r.get("ok"))
            c[1] += 1
    return fam
