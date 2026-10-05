"""RQ1 as a benchmark-style table (2026-10-04, replaces the bars in the paper): one row per agent, grouped by how it runs;
task success by the judge and by the verifiers, then instances passed (%) per skill family and per reasoning operation.

Models, their judge files and the primitive filter come from rq1_config.yaml (the same entries as make_rq1_bars.py, whose
collect() computes the numbers); the table layout is the config's `table` block. Bold: best per column. Red / green: each
agent's weakest / strongest skill family.

    python docs/figures/rq1/make_rq1_table.py [--config docs/figures/rq1/rq1_config.yaml]
"""
import argparse, json, os, sys
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from make_rq1_bars import collect, primitive_filter, ROOT  # noqa: E402  (also chdirs to the repo root)

SHORT = {"Navigation": "Nav.", "Text entry": "Text", "Discrete selection": "Select", "Form transaction": "Form",
         "Out-of-page I/O": "I/O", "Drag & gesture": "Drag", "Reasoning base": "Reason"}


def per_task(path, only=None):
    """[(judge pass, verifier pass, [(family, op or None, passed), ...]), ...]: one entry per task, from a judge.jsonl."""
    from make_rq1_bars import MJ, FAMILY_OF
    out = []
    for line in open(path):
        if not line.strip():
            continue
        r = json.loads(line)
        _, task, _ = MJ._load(r["key"])
        ops = task.get("macro_operations") or {}
        inst = []
        for k, v in (r.get("instances") or {}).items():
            if only is not None and v["macro"] not in only:
                continue
            f = "Reasoning base" if v["macro"] == "report_information" else FAMILY_OF.get(v["macro"], "Other")
            inst.append((f, ops.get(k), bool(v["passed"])))
        out.append((bool(r.get("passed")), bool(r.get("verifier")), inst))
    return out


def bootstrap_se(tasks, fams, ops, n=1000, seed=0):
    """Standard error (percentage points) of every table cell over `n` resamples of the tasks (instances stay with their
    task, so the error reflects that a task's instances are not independent)."""
    import random, statistics
    rng = random.Random(seed)
    keys = ["judge", "verifier"] + [("fam", f) for f in fams] + [("op", o) for o in ops]
    draws = {k: [] for k in keys}
    for _ in range(n):
        smp = [tasks[rng.randrange(len(tasks))] for _ in tasks]
        draws["judge"].append(100 * sum(t[0] for t in smp) / len(smp))
        draws["verifier"].append(100 * sum(t[1] for t in smp) / len(smp))
        for f in fams:
            xs = [p for t in smp for (ff, _, p) in t[2] if ff == f]
            if xs:
                draws[("fam", f)].append(100 * sum(xs) / len(xs))
        for o in ops:
            xs = [p for t in smp for (_, oo, p) in t[2] if oo == o]
            if xs:
                draws[("op", o)].append(100 * sum(xs) / len(xs))
    return {k: statistics.pstdev(v) for k, v in draws.items() if len(v) > 1}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(HERE, "rq1_config.yaml"))
    ap.add_argument("--out", help="write here instead of the config's table.out")
    ap.add_argument("--no-size", action="store_true", help="drop the Size column (every agent name states its size)")
    ap.add_argument("--minipage", action="store_true",
                    help="no table* float: the tabular scaled to \\linewidth and a \\captionof{table}, for a minipage next to a figure")
    ap.add_argument("--natural", action="store_true",
                    help="no \\resizebox: the tabular at its natural size, centred, with wider column spacing (full-width float)")
    ap.add_argument("--clean", action="store_true",
                    help="no per-cell standard errors (their range goes in the caption) and no red/green cells: the drag & "
                         "gesture column is shaded instead, since it is every agent's weakest family")
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config))
    size_col = not args.no_size
    t = cfg["table"]
    by = {m["label"]: m for m in cfg["models"]}
    only = primitive_filter(cfg.get("primitives"))
    rows = []
    for g in t["groups"]:
        for lab in g["models"]:
            r = collect(by[lab]["judge"], only)
            fam = {f: 100 * r["family"][f][0] / r["family"][f][1] for f in t["families"] if r["family"].get(f, [0, 0])[1]}
            op = {o: 100 * r["op"][o][0] / r["op"][o][1] for o in t["ops"] if r["op"].get(o, [0, 0])[1]}
            rows.append({"group": g["name"], "label": lab, "size": t["sizes"].get(lab, ""), "judge": 100 * r["task_judge"],
                         "verifier": 100 * r["task_verifier"], "fam": fam, "op": op, "n": r["episodes"],
                         "nfam": {f: r["family"][f][1] for f in fam}, "nop": {o: r["op"][o][1] for o in op},
                         "se": bootstrap_se(per_task(by[lab]["judge"], only), list(fam), list(op))})
    cols = [("judge", None)] + [("fam", f) for f in t["families"]] + [("op", o) for o in t["ops"]]
    val = lambda row, c: row[c[0]] if c[1] is None else row[c[0]].get(c[1])
    best = {c: max(val(r, c) for r in rows if val(r, c) is not None) for c in cols}
    n0 = rows[0]
    ses = [v for r in rows for k, v in r["se"].items() if isinstance(k, tuple) and v is not None]   # family and op cells
    se_lo, se_hi = min(ses), max(ses)
    sej = [r["se"]["judge"] for r in rows if r["se"].get("judge") is not None]                    # task success
    sed = [r["se"][("fam", "Drag & gesture")] for r in rows if r["se"].get(("fam", "Drag & gesture")) is not None]
    se_drag_lo, se_drag_hi = (min(sed), max(sed)) if sed else (0, 0)
    head2 = ["success"] + [f"{SHORT[f]}" for f in t["families"]] + [o for o in t["ops"]]
    head3 = [f"\\scriptsize({n0['n']})"] + [f"\\scriptsize({n0['nfam'][f]})" for f in t["families"]] + [f"\\scriptsize({n0['nop'][o]})" for o in t["ops"]]
    nf, no = len(t["families"]), len(t["ops"])
    L = ["% generated by docs/figures/rq1/make_rq1_table.py from rq1_config.yaml; do not edit by hand",
         "\\providecommand{\\se}[1]{\\,{\\scriptsize(#1)}}",
         "\\definecolor{mwbad}{HTML}{B3261E}\\definecolor{mwok}{HTML}{2E7D32}\\definecolor{mwdrag}{HTML}{6B4C9A}",   # the diagrams' red, green, drag purple
         *(["\\centering"] if args.minipage else ["\\begin{table*}[t]", "\\centering"]),
         "\\footnotesize", "\\setlength{\\tabcolsep}{%s}" % ("5pt" if args.natural else "3pt"),
         "{%" if args.natural else ("\\resizebox{\\linewidth}{!}{%" if args.minipage else "\\resizebox{\\textwidth}{!}{%"),
         "\\begin{tabular}{@{}l" + ("l" if size_col else "") + "c" + "c" * nf + "c" * no + "@{}}", "\\toprule",
         f" & {'& ' if size_col else ''}Task & \\multicolumn{{{nf}}}{{c}}{{Skill family: instances passed}} & "
         f"\\multicolumn{{{no}}}{{c}}{{Reasoning operation}} \\\\",
         f"\\cmidrule(lr){{{3 + size_col}-{2 + size_col + nf}}}\\cmidrule(lr){{{3 + size_col + nf}-{2 + size_col + nf + no}}}",
         "Agent & " + ("Size & " if size_col else "") + " & ".join(head2) + " \\\\",
         " & " + ("& " if size_col else "") + " & ".join(head3) + " \\\\", "\\midrule"]
    group = None
    for r in rows:
        if r["group"] != group:
            if group is not None:
                L.append("\\midrule")
            L.append(f"\\multicolumn{{{2 + size_col + nf + no}}}{{@{{}}l}}{{\\textit{{{r['group']}}}}} \\\\")
            group = r["group"]
        weakest, strongest = min(r["fam"], key=r["fam"].get), max(r["fam"], key=r["fam"].get)
        cells = []
        for c in cols:
            v = val(r, c)
            if v is None:
                cells.append("--"); continue
            key = c[0] if c[1] is None else c
            se = r["se"].get(key)
            s = f"{v:.1f}" if c[1] is None else f"{v:.0f}"
            sd = (f"\\se{{{se:.1f}}}" if c[1] is None else f"\\se{{{se:.0f}}}") if se is not None else ""
            if args.clean:
                sd = ""
            if round(v, 1) == round(best[c], 1):
                s = f"\\textbf{{{s}}}"
            if args.clean:
                if c[0] == "fam" and c[1] == "Drag & gesture":
                    s = f"\\cellcolor{{mwdrag!13}}{s}"
            else:
                if c[0] == "fam" and c[1] == weakest:
                    s = f"\\cellcolor{{mwbad!14}}{s}"
                if c[0] == "fam" and c[1] == strongest:
                    s = f"\\cellcolor{{mwok!14}}{s}"
            cells.append(s + sd)
        L.append(f"{r['label']} & " + (f"{r['size']} & " if size_col else "") + " & ".join(cells) + " \\\\")
    L += ["\\bottomrule", "\\end{tabular}}",
          ("\\captionof{table}{" if args.minipage else "\\caption{") + "\\textbf{Main results: drag \\& gesture is the weakest skill family of every agent, and task success hides where agents differ.} Skill profiles of ten untrained agents on all 376 \\miniweb{} tasks: task success, then the share of primitive instances passed (\\%) " +
          ("per skill family and reasoning operation, all judged by the VLM judge (Gemini 3.5 Flash); the number of tasks or instances is under each column. One run per agent; "
           + (f"standard errors over 1,000 bootstrap resamples of the tasks are {min(sej):.0f}--{max(sej):.0f} points for task success and at most {se_hi:.0f} for skill families and operations. Shaded: drag \\& gesture, the weakest family of every agent. "
              if args.clean else "in brackets: standard error over 1,000 bootstrap resamples of the tasks. Red: each agent's weakest skill family; green: its strongest. ")) +
          "Bold: best per column. Compute, compare, and spatial (14 instances in total) are omitted. "
          "\\textbf{Takeaway:} no agent, whatever its size or web training, has mastered drag \\& gesture.}",
          f"\\label{{{t['label']}}}", *([] if args.minipage else ["\\end{table*}"]), ""]
    out = args.out or os.path.join(ROOT, t["out"])
    open(out, "w").write("\n".join(L))
    print("wrote", out)
    for r in rows:
        print(f"  {r['label']:15s} judge {r['judge']:.1f} verifier {r['verifier']:.1f} weakest {min(r['fam'], key=r['fam'].get)}")


if __name__ == "__main__":
    main()
