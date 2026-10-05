"""Why drag & gesture fails, single column: every drag instance of the RQ1 agents (12 filter_by_slider + 6
sign_by_freeformdrawing tasks per agent) sorted into one outcome, as a stacked bar per agent.

Outcomes come from the macro judge's per-instance verdict (judge.jsonl: passed, why, agent_target). A failed instance's
explanation is classified once by an LLM into a fixed taxonomy (temperature 0, cached in drag_failures_cache.json, so
the figure is reproducible without new calls):
  not reached   the agent never got to the slider or canvas (an earlier step failed or it stopped)
  no action     it reached the control but never moved the slider or drew
  imprecise     it acted on the control but the value is wrong or the drawing is not a legible signature
  not committed the control holds the right value or drawing, but it was never applied or submitted
  bypassed      it avoided the gesture: typed the name, used another field or control

    python docs/figures/rq1/drag_failures.py [--config docs/figures/rq1/rq1_config.yaml]
"""
import argparse, collections, json, os, sys
import yaml
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from make_rq1_bars import ROOT, FAMILY_OF, primitive_filter  # noqa: E402  (also chdirs to the repo root)

sys.path.insert(0, os.path.join(HERE, "..", "common"))
from style import INK, MUTED, EDGE, OK, FAM, FS, rc, header, panel, tint, save  # noqa: E402  (the diagrams' look)
rc()
CACHE = os.path.join(HERE, "drag_failures_cache.json")
MODES = ["passed", "imprecise", "not committed", "bypassed", "no action", "not reached"]
COLORS = {"passed": OK, "imprecise": FAM["Drag & gesture"], "not committed": tint(FAM["Drag & gesture"], 0.6),
          "bypassed": tint(FAM["Drag & gesture"], 0.32), "no action": EDGE, "not reached": tint(EDGE, 0.35)}
PROMPT = """A web agent was asked to {what}. A grader judged that this step FAILED and explained:
"{why}"
The agent's request or action that the grader matched: {target}

Classify the failure into exactly one category:
- not_reached: the agent never got to the slider or drawing canvas (it stopped earlier, got stuck elsewhere, or an earlier step failed)
- no_action: it reached the slider or canvas but never moved the slider or never drew anything
- imprecise: it moved the slider but to a wrong value, or drew something that is not a legible signature
- not_committed: the slider holds the right value or the signature was drawn, but it was never applied, saved, or submitted
- bypassed: it avoided the gesture, e.g. typed the name instead of drawing, or used a different field or control
Answer with JSON: {{"category": "..."}}"""
WHAT = {"filter_by_slider": "set a slider to a target value and apply it as a filter",
        "sign_by_freeformdrawing": "draw a person's signature on a canvas and submit it"}


def classify(macro, why, target, cache):
    key = f"{macro}|{why}|{target}"
    if key not in cache:
        from helpers.llm import call_llm
        txt = call_llm(PROMPT.format(what=WHAT[macro], why=why, target=target), temperature=0.0, max_tokens=2000,
                       json_mode=True, model="gemini-3.5-flash") or "{}"
        try:
            cat = json.loads(txt[txt.index("{"):txt.rindex("}") + 1]).get("category", "")
        except ValueError:
            cat = ""
        cache[key] = cat.replace("_", " ") if cat.replace("_", " ") in MODES else "not reached"
    return cache[key]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(HERE, "rq1_config.yaml"))
    cfg = yaml.safe_load(open(ap.parse_args().config))
    only = primitive_filter(cfg.get("primitives"))
    drag = {m for m in only if FAMILY_OF.get(m) == "Drag & gesture"}
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    rows = []
    for m in cfg["models"]:
        c = collections.Counter()
        for line in open(m["judge"]):
            if not line.strip():
                continue
            for v in (json.loads(line).get("instances") or {}).values():
                if v["macro"] in drag:
                    c["passed" if v["passed"] else classify(v["macro"], v.get("why", ""), v.get("agent_target", ""),
                                                            cache)] += 1
        rows.append((m["label"], c, m["logo"]))
        json.dump(cache, open(CACHE, "w"), indent=0)
    rows.sort(key=lambda r: -r[1]["passed"])

    W, rh = 3.25, 0.165                                  # width, row pitch per agent (inches)
    lg = 0.22 + 0.36 + 0.14                              # legend panel (two rows of three) ends here, then a gap
    top, bot = lg, 0.4
    H = top + rh * len(rows) + bot
    fig = plt.figure(figsize=(W, H))
    A = fig.add_axes([0, 0, 1, 1]); A.set_xlim(0, W); A.set_ylim(H, 0); A.axis("off")
    header(fig, A, 0.04, 0.1, "Where drag fails", "drag & gesture instances, ten untrained agents")
    panel(A, 0.04, 0.22, W - 0.08, 0.36)                 # legend in a light panel, as the diagrams group things
    for k, mo in enumerate(MODES):
        x, y = 0.12 + (k % 3) * 1.02, 0.31 + (k // 3) * 0.17
        A.add_patch(Rectangle((x, y - 0.05), 0.15, 0.1, fc=COLORS[mo], ec="none", zorder=3))
        A.text(x + 0.2, y, mo, fontsize=FS["legend"], color=INK, va="center")
    ax = fig.add_axes([0.27, bot / H, 0.675, rh * len(rows) / H])
    for i, (lab, c, _) in enumerate(rows):
        n, x = sum(c.values()), 0
        for mo in MODES:
            w = 100 * c[mo] / n
            if w:
                ax.add_patch(Rectangle((x, i - 0.39), w, 0.78, fc=COLORS[mo], ec="white", lw=0.6))
                if w >= 8:
                    ax.text(x + w / 2, i, f"{c[mo]}", fontsize=FS["small"], ha="center", va="center",
                            color="white" if mo in ("passed", "imprecise", "not committed") else INK)
            x += w
    ax.set_xlim(0, 100); ax.set_ylim(len(rows) - 0.5, -0.5)
    to_fig = lambda y: fig.transFigure.inverted().transform(ax.transData.transform((0, y)))[1]
    for i, (lab, _, logo) in enumerate(rows):            # logo, then name, as in the RQ1 figure legend
        yf, sz = to_fig(i), 0.135
        la = fig.add_axes([0.03 / W, yf - sz / 2 / H, sz / W, sz / H])
        la.imshow(Image.open(os.path.join(ROOT, logo)).convert("RGBA"), interpolation="lanczos"); la.axis("off")
        fig.text((0.03 + sz + 0.05) / W, yf, lab, fontsize=FS["value"], color=INK, ha="left", va="center")
    ax.set_xticks([0, 25, 50, 75, 100]); ax.set_xticklabels(["0", "25", "50", "75", "100%"])
    ax.set_yticks([]); ax.tick_params(labelsize=FS["tick"], length=2.5, width=0.8, pad=2, colors=MUTED)
    ax.set_xlabel("drag & gesture instances (12 slider + 6 signature tasks per agent)", fontsize=FS["small"], color=MUTED,
                  labelpad=2)
    for sp in ("top", "right", "left"): ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_linewidth(0.8); ax.spines["bottom"].set_color(MUTED)

    out = os.path.join(ROOT, "docs", "figures", "rq1", "drag_failures")
    save(fig, out)                                        # style.save: trims the heading strip
    print("wrote", out)
    tot = collections.Counter()
    for lab, c, _ in rows:
        tot.update(c); print(f"  {lab:15s}", {mo: c[mo] for mo in MODES})
    fails = sum(v for k, v in tot.items() if k != "passed")
    print("  all failures:", {mo: f"{tot[mo]} ({100 * tot[mo] / fails:.0f}%)" for mo in MODES[1:]})


if __name__ == "__main__":
    main()
