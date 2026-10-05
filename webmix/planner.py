"""The macro planner: instruction + current screen -> the families of the macros still to do.

    python -m webmix.planner build            # data/webmix/planner/rows.jsonl (+ rendered start pages)

Design doc "Routing": the planner writes the task's family sequence up front from the instruction and
the first screenshot, and replans at each macro boundary (the executor's macro_done) from the current
screen and the families already done. Its output picks the family adapter for the next steps.

Rows use the same chat format as the policy rows (webmix.train trains them as the `planner` adapter):
system = the family catalogue + output format; user = task, families done so far, one screenshot;
target = {"plan": [family, ...]} (the remaining families, one per macro, in order).

Supervision (pilot): the 310 train-site human tasks, at their start page (rendered here in the harness
viewport, 1280x800, UTC) -> the families of their annotated macro spans in span order; synthetic
trajectories (webmix.replay episodes) at their start (one family, or prefix + target for mid-chain)
and at the mid-chain boundary (the replayed screen right after the prefix's macro_done).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path

from datagen.viewer import FAMILIES, FAMILY_OF
from webmix import REPLAY_DIR

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "webmix" / "planner"
REPLAY = REPLAY_DIR

FAMILY_HINTS = {
    "Drag & gesture": "dragging, sliders, drawing or signing on a canvas, reordering by drag, panning/zooming a map, scrubbing media",
    "Discrete selection": "clicking choices: filters, dropdowns, sorting, date ranges, ratings, reactions, toggles (follow, save), deleting rows, playing media",
    "Text entry": "typing free text: search, messages, comments, spreadsheet cells, calculators, translation, code, typed signatures",
    "Form transaction": "filling and submitting a multi-field form: create, edit, book, pay, check out, sign in, share, cancel, configure, compare",
    "Navigation": "moving to a page: following menus or links, routes/directions, joining a meeting, carrying information to another site",
    "Out-of-page I/O": "moving data in or out of the page: upload, export/download, copy to clipboard, save a file, image editing, a code from another app",
    "Reasoning base": "reading the page to report an answer: find, count, compare or compute values",
}

SYSTEM = ("You plan web tasks. A task is a sequence of steps; each step is one interaction of a kind (a family):\n"
          + "\n".join(f"- {f}: {h}" for f, h in FAMILY_HINTS.items())
          + "\n\nGiven the task, the steps already finished and the current screen, list the families of the steps "
            "still to do, in order, one entry per step. Answer with JSON only: {\"plan\": [\"<family>\", ...]}")


def prompt_messages(instruction, done, image_ref):
    """OpenAI-format messages for one planning call (image_ref: a data URL, or a file name for rows)."""
    done_txt = ", ".join(done) if done else "none"
    return [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": [
                {"type": "text", "text": f"Task: {instruction}\nSteps finished: {done_txt}\nCurrent screen:"},
                {"type": "image_url", "image_url": {"url": image_ref}}]}]


def parse_plan(text):
    """The model's answer -> [family, ...] (unknown names dropped); [] when unparseable."""
    try:
        plan = json.loads(text).get("plan") or []
    except (ValueError, AttributeError):
        return []
    return [p for p in plan if p in FAMILY_HINTS]


# ── subtask planner (planner_v5) ─────────────────────────────────────────────
# The plan hands each specialist its subtask (user, 2026-09-30: "the planner has to output the subtask for the
# specialist, else there is no point in planning"): every remaining step is a family AND a one-sentence
# instruction, which the router runs as its own episode (webmix.evaluate.run_subtasks).

SYSTEM_SUB = ("You plan web tasks. A task is a sequence of steps; each step is one interaction of a kind (a family):\n"
              + "\n".join(f"- {f}: {h}" for f, h in FAMILY_HINTS.items())
              + "\n\nGiven the task, the steps already finished and the current screen, list the steps still to do, in "
                "order. For each step give its family and a short instruction that says exactly what to do in that step "
                "(with the names and values it needs, since it is carried out on its own). A step that reports an "
                "answer comes last. Answer with JSON only: {\"steps\": [{\"family\": \"<family>\", \"do\": \"<instruction>\"}, ...]}")


def prompt_messages_sub(instruction, done_texts, image_ref):
    done_txt = "; ".join(done_texts) if done_texts else "none"
    return [{"role": "system", "content": SYSTEM_SUB},
            {"role": "user", "content": [
                {"type": "text", "text": f"Task: {instruction}\nSteps finished: {done_txt}\nCurrent screen:"},
                {"type": "image_url", "image_url": {"url": image_ref}}]}]


def parse_steps(text):
    """The subtask planner's answer -> [(family, instruction), ...] (unknown families dropped); [] if unparseable."""
    try:
        steps = json.loads(text).get("steps") or []
    except (ValueError, AttributeError):
        return []
    return [(x["family"], str(x.get("do") or "").strip()) for x in steps
            if isinstance(x, dict) and x.get("family") in FAMILY_HINTS and str(x.get("do") or "").strip()]


STEPS_SCHEMA = {"type": "object", "properties": {"steps": {"type": "array", "items": {
    "type": "object", "properties": {"family": {"type": "string", "enum": list(FAMILY_HINTS)}, "do": {"type": "string"}},
    "required": ["family", "do"]}}}, "required": ["steps"]}


def fewshot_examples(k=4, seed=0):
    """A few train-site human tasks with their gold steps, as worked examples for the prompted planner (text only)."""
    hum = [t for t in human_tasks_sub() if 2 <= len(t["steps"]) <= 4]
    random.Random(seed).shuffle(hum)
    return hum[:k]


# The defined prompt (user, 2026-09-30: "a prompted planner ... explain and define each family in the prompt"). Written
# once, before any WebArena run with it, and not tuned on WebArena: the base model plans with these definitions and
# the same MiniWeb worked examples as the plain prompted planner.
FAMILY_DEFS = {
    "Navigation": "getting to the page where the work happens: opening a menu, tab, section or link, opening an item's "
                  "own page from a list, going back. The step is finished when that page is open.",
    "Text entry": "typing into one text field and submitting it: a search box, a message or comment, a cell, a calculator. "
                  "Searching for an item by name, number or keyword is Text entry.",
    "Discrete selection": "choosing among options already on the page: dropdowns, checkboxes, radio buttons, sort orders, "
                          "filter chips, date ranges, ratings, reactions, toggles (follow, save, like), deleting a row, "
                          "playing media.",
    "Form transaction": "filling in several fields of one form and submitting it to create or change something: posting, "
                        "creating, editing, booking, paying, checking out, signing in, sharing, configuring.",
    "Drag & gesture": "an action that needs the pointer dragged: a slider handle, drag-and-drop, reordering by drag, "
                      "drawing or signing, panning or zooming a map by drag. Only when the task needs a drag.",
    "Out-of-page I/O": "moving data into or out of the page: exporting or downloading a file, uploading a file, copying to "
                       "the clipboard, saving or printing.",
    "Reasoning base": "reading what is on the screen and answering: finding, counting, comparing or computing values and "
                      "reporting the result. It does not change anything on the site; it may scroll to read.",
}

SYSTEM_DEF = (
    "You plan web tasks for a team of specialists. Each specialist does one kind of step (a family):\n"
    + "\n".join(f"- {f}: {d}" for f, d in FAMILY_DEFS.items())
    + "\n\nGiven the task, the steps already finished and the current screen, list the steps still to do, in order. "
      "Rules:\n"
      "1. A task may state only a goal (\"Tell me ...\", \"How many ...\", \"Find ...\"). Work out the steps a person "
      "would take on this website to reach it: which page to open, what to search or filter, what to read.\n"
      "2. Each step belongs to exactly one family. Split a step that mixes families: \"open Companies and filter to "
      "SaaS\" is Navigation (open Companies) then Discrete selection (filter the industry to SaaS).\n"
      "3. Each step is one short instruction that says exactly what to do, with the names and values it needs; a "
      "separate specialist carries it out, seeing the whole task as background.\n"
      "4. If the task asks for information, the last step is Reasoning base: report the answer.\n"
      "5. Use as few steps as the task needs, starting from the current screen.\n"
      "Answer with JSON only: {\"steps\": [{\"family\": \"<family>\", \"do\": \"<instruction>\"}, ...]}")


# Closed-loop planning (2026-09-30 19:40): the WebArena failure analysis (13 base-solved tasks the defined-prompt
# router lost) found open-loop planning, not the specialists: steps for controls that do not exist (7), answers
# written into steps (3), wandering (2). The planner saw only the instructions already issued, never their results,
# so it re-issued impossible steps. Here each finished step comes with its result, plus three generic rules.
SYSTEM_DEF_CLOSED = SYSTEM_DEF.replace(
    "Answer with JSON only:",
    "6. \"Steps finished\" gives each step with its result. If a result says a step could not be done (no such option, "
    "field or page), do not repeat it: reach the goal another way.\n"
    "7. Never write an answer, name or value into a step unless it is in the task; the Reasoning base step reads it "
    "from the page.\n"
    "8. Plan only steps whose controls are on the current screen or reached through the site's menus and links; if "
    "you are unsure where something is, plan a Navigation step to the most likely section, and re-plan from there.\n"
    "Answer with JSON only:")


def defined_messages(instruction, done_texts, image_ref, examples, closed=False):
    """The defined-prompt planner: SYSTEM_DEF (or SYSTEM_DEF_CLOSED, whose done_texts carry results) plus the MiniWeb
    worked examples."""
    msgs = prompted_messages(instruction, done_texts, image_ref, examples)
    ex = msgs[0]["content"].split("\n\nExamples (other websites):", 1)[1]
    msgs[0] = {"role": "system", "content": (SYSTEM_DEF_CLOSED if closed else SYSTEM_DEF)
               + "\n\nExamples (other websites):" + ex}
    return msgs


def prompted_messages(instruction, done_texts, image_ref, examples):
    """The subtask prompt for an untrained model: SYSTEM_SUB plus worked examples."""
    ex = "\n\n".join(f"Task: {e['instruction']}\nSteps finished: none\nAnswer: {_steps_target(e['steps'])}" for e in examples)
    msgs = prompt_messages_sub(instruction, done_texts, image_ref)
    msgs[0] = {"role": "system", "content": SYSTEM_SUB + "\n\nExamples (other websites):\n\n" + ex}
    return msgs


async def plan_steps(client, model, instruction, done_texts, image_url, examples=None, defined=False, closed=False):
    """-> [(family, instruction), ...] still to do, from the current screen: a trained subtask planner (no examples)
    or a prompted one (examples; `defined`: the family-definitions prompt), decoding constrained to STEPS_SCHEMA."""
    if examples:
        msgs = (defined_messages(instruction, done_texts, image_url, examples, closed=closed) if defined or closed
                else prompted_messages(instruction, done_texts, image_url, examples))
    else:
        msgs = prompt_messages_sub(instruction, done_texts, image_url)
    r = await client.chat.completions.create(
        model=model, messages=msgs, temperature=0, max_tokens=400,
        response_format={"type": "json_schema", "json_schema": {"name": "plan", "schema": STEPS_SCHEMA}})
    return parse_steps(r.choices[0].message.content or "")


def accuracy_sub(base, vllm_url, model, out_path, prompted=True, defined=False):
    """Subtask-planner accuracy on the held-out human tasks at their start page: the families (adapter level, repeats
    merged: what routing uses) plus the subtask texts next to the gold ones for reading."""
    import asyncio
    import base64
    import itertools
    from openai import AsyncOpenAI
    from webmix.evaluate import ADAPTER_OF_FAMILY
    from webmix.evaluate import human_tasks as eval_tasks
    tasks = [t for t in eval_tasks() if t.get("subtasks")]
    img_dir = OUT / "start_pages_heldout"
    render_starts([{"task_id": t["task_id"], "start_path": _start_path(t)} for t in tasks], base, img_dir)
    client, ex = AsyncOpenAI(base_url=vllm_url, api_key="EMPTY"), (fewshot_examples() if prompted else None)
    ad = lambda fams: [k for k, _ in itertools.groupby(ADAPTER_OF_FAMILY.get(f, "?") for f in fams)]   # noqa: E731

    async def one(t):
        p = img_dir / f"{t['task_id']}.png"
        url = "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()
        steps = await plan_steps(client, model, t["instruction"], [], url, ex, defined=defined)
        return {"task_id": t["task_id"], "instruction": t["instruction"], "gold": t["subtasks"], "plan": steps}

    async def run():
        sem = asyncio.Semaphore(8)

        async def lim(t):
            async with sem:
                return await one(t)
        return await asyncio.gather(*(lim(t) for t in tasks if (img_dir / f"{t['task_id']}.png").exists()))
    rows = asyncio.run(run())
    g = lambda r: [f for f, _ in r["gold"]]                                 # noqa: E731
    p = lambda r: [f for f, _ in r["plan"]]                                 # noqa: E731
    multi = [r for r in rows if len(ad(g(r))) > 1]
    summary = {"tasks": len(rows), "parsed": sum(bool(r["plan"]) for r in rows),
               "adapter_exact": sum(ad(p(r)) == ad(g(r)) for r in rows),
               "first_adapter": sum(bool(r["plan"]) and ad(p(r))[0] == ad(g(r))[0] for r in rows),
               "multi_planned_multi": f"{sum(len(ad(p(r))) > 1 for r in multi)}/{len(multi)}",
               "steps_per_task": round(sum(len(r["plan"]) for r in rows) / max(1, len(rows)), 2),
               "gold_steps_per_task": round(sum(len(r["gold"]) for r in rows) / max(1, len(rows)), 2)}
    Path(out_path).write_text(json.dumps({"summary": summary, "rows": rows}, indent=1, ensure_ascii=False))
    print(json.dumps(summary), flush=True)
    return summary


def _start_path(t):
    hint = t.get("start_hint") or f"/sites/{t['site']}/"
    return "/" + hint.split("://", 1)[-1].split("/", 1)[-1] if "://" in hint else hint


def _steps_target(steps):
    return json.dumps({"steps": [{"family": f, "do": d} for f, d in steps]}, ensure_ascii=False)


def human_tasks_sub():
    """Train-site human tasks with their gold steps: (family, annotated subtask), span order, reasoning last."""
    import ast
    from annotation.macros import canon
    from datagen import split
    train = set(split.load_split()["train"])
    test = set(split.load_split()["test"])
    lit = lambda v: ast.literal_eval(v) if isinstance(v, str) and v[:1] in "[{" else v      # noqa: E731
    out = []
    for f in sorted(ROOT.glob("data/annotations/*/*/task.json")):
        t = json.loads(f.read_text())
        sites = {x["id"] if isinstance(x, dict) else x for x in (lit(t.get("sites")) or [t["site"]])}
        if not sites <= train or sites & test:
            continue
        spans, subs = lit(t.get("macro_spans")) or {}, lit(t.get("macro_subtasks")) or {}
        order = sorted(spans, key=lambda m: spans[m][0]) if spans else []
        steps = [(FAMILY_OF.get(canon(m.split("#")[0]) or m), str(subs.get(m) or "").strip()) for m in order]
        if not steps or any(fam is None or not d for fam, d in steps):
            continue
        steps = [x for x in steps if x[0] != "Reasoning base"] + [x for x in steps if x[0] == "Reasoning base"]
        url = t.get("starting_url") or f"/sites/{t['site']}/"
        path = "/" + url.split("://", 1)[-1].split("/", 1)[-1] if "://" in url else url
        out.append({"task_id": t["task_id"], "instruction": t["instruction"], "start_path": path, "steps": steps})
    return out


def synthetic_rows_sub():
    """Subtask rows from the replayed episodes: a one-macro episode's step is its own instruction; a chain episode's
    steps are its parts' instructions, at its start and again after the first part (the re-plan)."""
    from datagen.viewer import _kept_rows
    from webmix.replay import load_task
    kept = _kept_rows()
    instr = lambda tid: load_task(kept[tid]["run"], tid)["instruction"]       # noqa: E731
    out = []
    for ep in sorted(REPLAY.iterdir()):
        if ep.name.startswith("_") or not (ep / "episode.json").exists():
            continue
        meta = json.loads((ep / "episode.json").read_text())
        if meta.get("variant") == "recovery" or meta.get("history_macro"):
            continue
        rows = [json.loads(line) for line in (ep / "rows.jsonl").read_text().split("\n") if line.strip()]
        if not rows:
            continue
        img = lambda r: next(x["image_url"]["url"] for x in r["messages"][1]["content"] if x.get("type") == "image_url")  # noqa: E731
        if meta.get("parts"):
            try:
                steps = [(FAMILY_OF.get(m), instr(t)) for m, t in zip(meta["macros"], meta["parts"])]
            except KeyError:
                continue
        else:
            steps = [(FAMILY_OF.get(meta["macro"]), meta["instruction"])]
        if any(fam is None for fam, _ in steps):
            continue
        out.append({"key": ep.name, "instruction": meta["instruction"], "done": [], "steps": steps,
                    "image": str(ep / img(rows[0])), "source": "synthetic"})
        if len(steps) == 2:
            nxt = next((r for r in rows if r["segment"] == 1), None)
            if nxt is not None:
                out.append({"key": ep.name + ":b1", "instruction": meta["instruction"], "done": [steps[0][1]],
                            "steps": steps[1:], "image": str(ep / img(nxt)), "source": "synthetic"})
    return out


def build_sub(base, synthetic_cap=900, human_repeat=2, seed=0, out_name="rows_sub.jsonl"):
    img_dir = OUT / "start_pages"
    hum = human_tasks_sub()
    render_starts(hum, base, img_dir)
    items = [{"key": t["task_id"], "instruction": t["instruction"], "done": [], "steps": t["steps"],
              "image": str(img_dir / f"{t['task_id']}.png"), "source": "human"}
             for t in hum if (img_dir / f"{t['task_id']}.png").exists()]
    syn = synthetic_rows_sub()
    rng = random.Random(seed)
    single = [x for x in syn if len(x["steps"]) == 1 and not x["done"]]
    multi = [x for x in syn if x not in single]
    rng.shuffle(single)
    rows = []
    for it in items * human_repeat + single[:synthetic_cap] + multi:
        split_ = "val" if _val(it["key"].split(":")[0]) else "train"
        rows.append({"task_id": it["key"], "source": it["source"], "split": split_, "family": "planner",
                     "messages": prompt_messages_sub(it["instruction"], it["done"], Path(it["image"]).name),
                     "dir": str(Path(it["image"]).parent), "target": _steps_target(it["steps"])})
    with open(OUT / out_name, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    n_h = sum(r["source"] == "human" for r in rows)
    print(f"subtask planner rows: {len(rows)} ({n_h} human incl. x{human_repeat}, {len(rows) - n_h} synthetic), "
          f"val {sum(r['split'] == 'val' for r in rows)}")
    return rows


def _val(key, frac=0.1):
    return int(hashlib.md5(key.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF < frac


# ── data ──────────────────────────────────────────────────────────────────────

def human_tasks():
    """Train-site human tasks -> [{task_id, instruction, start_path, families}]."""
    from annotation.macros import canon
    from datagen import split
    train = set(split.load_split()["train"])
    out = []
    for f in sorted(ROOT.glob("data/annotations/*/*/task.json")):
        t = json.loads(f.read_text())
        if not set(t.get("sites") or [t["site"]]) <= train:
            continue
        spans = t.get("macro_spans") or {}
        macros = sorted(spans, key=lambda m: spans[m][0]) if spans else list(t.get("macros") or [])
        fams = [FAMILY_OF.get(canon(m) or m) for m in macros]
        if not fams or None in fams:
            continue
        url = t.get("starting_url") or f"/sites/{t['site']}/"
        path = "/" + url.split("://", 1)[-1].split("/", 1)[-1] if "://" in url else url
        out.append({"task_id": t["task_id"], "instruction": t["instruction"], "start_path": path, "families": fams})
    return out


def held_out_tasks():
    """The human tasks on the held-out sites (webmix.evaluate.human_tasks) with their gold family sequence (macro
    spans in order), for the planner's offline accuracy."""
    import ast
    from annotation.macros import canon
    from webmix.evaluate import human_tasks as eval_tasks
    out = []
    for t in eval_tasks():
        raw = json.loads((ROOT / "data" / "annotations" / t["key"] / "task.json").read_text())
        spans = raw.get("macro_spans") or {}
        spans = ast.literal_eval(spans) if isinstance(spans, str) else spans
        macros = sorted(spans, key=lambda m: spans[m][0]) if spans else t["macros"]
        fams = [FAMILY_OF.get(canon(m) or m) for m in macros]
        if not fams or None in fams:
            continue
        hint = t["start_hint"] or f"/sites/{t['site']}/"
        path = "/" + hint.split("://", 1)[-1].split("/", 1)[-1] if "://" in hint else hint
        out.append({"task_id": t["task_id"], "instruction": t["instruction"], "start_path": path, "families": fams})
    return out


def accuracy(base, vllm_url, model, out_path):
    """Planner accuracy on the held-out human tasks at their start page (no rollout): exact family sequence,
    first family (what the router uses first), length, and multi-step tasks planned as multi-step."""
    import base64
    from openai import OpenAI
    tasks = held_out_tasks()
    img_dir = OUT / "start_pages_heldout"
    render_starts(tasks, base, img_dir)
    client = OpenAI(base_url=vllm_url, api_key="EMPTY")
    rows, n = [], 0
    for t in tasks:
        p = img_dir / f"{t['task_id']}.png"
        if not p.exists():
            continue
        url = "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()
        r = client.chat.completions.create(model=model, messages=prompt_messages(t["instruction"], [], url),
                                           temperature=0, max_tokens=120)
        plan = parse_plan(r.choices[0].message.content or "")
        rows.append({"task_id": t["task_id"], "gold": t["families"], "plan": plan})
    k = len(rows)
    multi = [x for x in rows if len(x["gold"]) > 1]
    summary = {"tasks": k, "exact": sum(x["plan"] == x["gold"] for x in rows),
               "first_family": sum(bool(x["plan"]) and x["plan"][0] == x["gold"][0] for x in rows),
               "same_length": sum(len(x["plan"]) == len(x["gold"]) for x in rows),
               "multi_step_tasks": len(multi), "multi_planned_multi": sum(len(x["plan"]) > 1 for x in multi),
               "family_recall": round(sum(len(set(x["plan"]) & set(x["gold"])) for x in rows)
                                      / max(1, sum(len(set(x["gold"])) for x in rows)), 3)}
    Path(out_path).write_text(json.dumps({"summary": summary, "rows": rows}, indent=1))
    print(json.dumps(summary), flush=True)
    return summary


def render_starts(tasks, base, img_dir):
    """Screenshot each task's start page in the harness viewport (1280x800, UTC; a fresh session each)."""
    from datagen import browser as B
    img_dir.mkdir(parents=True, exist_ok=True)
    with B.browser() as b:
        for t in tasks:
            p = img_dir / f"{t['task_id']}.png"
            if p.exists():
                continue
            ctx = B.new_context(b)
            try:
                page = ctx.new_page()
                B.goto_start(page, base + t["start_path"])
                page.screenshot(path=str(p))
            except Exception as e:
                print(f"render failed {t['task_id']}: {type(e).__name__}", flush=True)
            finally:
                ctx.close()


def synthetic_rows():
    """Start (and mid-chain boundary) planning rows from replayed episodes."""
    out = []
    for ep in sorted(REPLAY.iterdir()):
        if ep.name.startswith("_") or not (ep / "episode.json").exists():
            continue
        meta = json.loads((ep / "episode.json").read_text())
        if meta.get("variant") == "recovery":       # the same plan as its plain replay
            continue
        rows = [json.loads(line) for line in (ep / "rows.jsonl").read_text().split("\n") if line.strip()]
        macros = meta.get("macros") or ([meta["history_macro"]] if meta.get("history_macro") else []) + [meta["macro"]]
        fams = [FAMILY_OF.get(m) for m in macros]
        if None in fams or not rows:
            continue
        img = lambda r: next(x["image_url"]["url"] for x in r["messages"][1]["content"] if x.get("type") == "image_url")  # noqa: E731
        out.append({"key": ep.name, "instruction": meta["instruction"], "done": [], "plan": fams,
                    "image": str(ep / img(rows[0])), "source": "synthetic"})
        for k in range(1, len(fams)):               # the screen right after each segment's macro_done
            nxt = next((r for r in rows if r["segment"] == k), None)
            if nxt is not None:
                out.append({"key": ep.name + f":b{k}", "instruction": meta["instruction"], "done": fams[:k],
                            "plan": fams[k:], "image": str(ep / img(nxt)), "source": "synthetic"})
    return out


def build(base, synthetic_cap=900, human_repeat=2, seed=0, out_name="rows.jsonl"):
    img_dir = OUT / "start_pages"
    hum = human_tasks()
    render_starts(hum, base, img_dir)
    items = [{"key": t["task_id"], "instruction": t["instruction"], "done": [], "plan": t["families"],
              "image": str(img_dir / f"{t['task_id']}.png"), "source": "human"}
             for t in hum if (img_dir / f"{t['task_id']}.png").exists()]
    syn = synthetic_rows()
    rng = random.Random(seed)
    single = [s for s in syn if len(s["plan"]) == 1 and not s["done"]]
    multi = [s for s in syn if s not in single]
    rng.shuffle(single)
    syn = single[:synthetic_cap] + multi
    rows = []
    for it in items * human_repeat + syn:
        split_ = "val" if _val(it["key"].split(":")[0]) else "train"
        rows.append({"task_id": it["key"], "source": it["source"], "split": split_, "family": "planner",
                     "messages": prompt_messages(it["instruction"], it["done"], Path(it["image"]).name),
                     "dir": str(Path(it["image"]).parent), "target": json.dumps({"plan": it["plan"]})})
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / out_name, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    n_h = sum(r["source"] == "human" for r in rows)
    print(f"planner rows: {len(rows)} ({n_h} human incl. x{human_repeat} repeat, {len(rows) - n_h} synthetic), "
          f"val {sum(r['split'] == 'val' for r in rows)}")
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m webmix.planner")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--port", type=int, default=8312)
    b.add_argument("--human-repeat", type=int, default=2, help="copies of each human row (the only 3+ step plans)")
    b.add_argument("--out-name", default="rows.jsonl")
    bs_ = sub.add_parser("build-sub", help="subtask-planner rows (planner_v5)")
    bs_.add_argument("--port", type=int, default=8312)
    bs_.add_argument("--human-repeat", type=int, default=2)
    asub = sub.add_parser("accuracy-sub", help="subtask-planner accuracy on the held-out human tasks")
    asub.add_argument("--port", type=int, default=8312)
    asub.add_argument("--vllm", default="http://127.0.0.1:8400/v1")
    asub.add_argument("--model", default="qwen35-4b")
    asub.add_argument("--trained", action="store_true", help="a trained subtask planner (no worked examples)")
    asub.add_argument("--defined", action="store_true", help="the prompted planner with family definitions")
    asub.add_argument("--out", default=str(ROOT / "data" / "webmix" / "eval" / "planner_sub_accuracy.json"))
    a = sub.add_parser("accuracy", help="offline planner accuracy on the held-out human tasks")
    a.add_argument("--port", type=int, default=8312)
    a.add_argument("--vllm", default="http://127.0.0.1:8400/v1")
    a.add_argument("--model", default="planner")
    a.add_argument("--out", default=str(ROOT / "data" / "webmix" / "eval" / "planner_accuracy.json"))
    args = ap.parse_args(argv)
    if args.cmd == "accuracy-sub":
        from datagen import browser as B
        with B.Servers(ports=[args.port]) as srv:
            return accuracy_sub(srv.bases[0], args.vllm, args.model, args.out, prompted=not args.trained,
                                defined=args.defined)
    if args.cmd == "build-sub":
        from datagen import browser as B
        with B.Servers(ports=[args.port]) as srv:
            return build_sub(srv.bases[0], human_repeat=args.human_repeat)
    if args.cmd == "accuracy":
        from datagen import browser as B
        with B.Servers(ports=[args.port]) as srv:
            return accuracy(srv.bases[0], args.vllm, args.model, args.out)
    if args.cmd == "build":
        from datagen import browser as B
        with B.Servers(ports=[args.port]) as srv:
            build(srv.bases[0], human_repeat=args.human_repeat, out_name=args.out_name)


if __name__ == "__main__":
    main()
