"""Data for the Macro Browser: every tagged macro instance and its gold sub-trajectory.

Read-only. Spans are 1-based inclusive indices into a task's recorded actions
(`macro_span_source.index_base`); each action is paired with the screenshot of the
observation recorded with it.
"""
import json
from functools import lru_cache
from pathlib import Path

from annotation.storage import ANNOTATIONS_DIR


def _task_files():
    for path in sorted(ANNOTATIONS_DIR.glob("*/*/task.json")):
        if not any(part.startswith(".") for part in path.relative_to(ANNOTATIONS_DIR).parts):
            yield path


def instances(task):
    """[(instance_id, base_macro)] in task order; derives `#n` ids for duplicates."""
    macros = task.get("macros") or []
    ids = task.get("macro_instances") or []
    if len(ids) != len(macros):
        seen, ids = {}, []
        for m in macros:
            seen[m] = seen.get(m, 0) + 1
            ids.append(m if seen[m] == 1 else f"{m}#{seen[m]}")
    return list(zip(ids, macros))


def _tags(task):
    ops = task.get("macro_operations") or {}
    spans = task.get("macro_spans") or {}
    subtasks = task.get("macro_subtasks") or {}
    required = task.get("macro_required") or {}
    out = []
    for inst, macro in instances(task):
        span = spans.get(inst)
        valid = (isinstance(span, list) and len(span) == 2
                 and all(isinstance(x, int) and not isinstance(x, bool) for x in span) and 1 <= span[0] <= span[1])
        out.append({"instance": inst, "macro": macro, "op": ops.get(inst) or None,
                    "span": span if valid else None, "subtask": subtasks.get(inst, ""),
                    "required": required.get(inst, True)})
    return out


def _signature():
    return tuple((str(p), p.stat().st_mtime_ns) for p in _task_files())


@lru_cache(maxsize=2)
def _index(signature):
    tasks, by_macro = [], {}
    for path, _ in signature:
        task = json.loads(Path(path).read_text())
        d = Path(path).parent
        key = f"{d.parent.name}/{d.name}"
        review = task.get("ai_review") or {}
        summary = {"key": key, "annotator": d.parent.name, "task_id": d.name,
                   "instruction": task.get("instruction", ""), "sites": task.get("sites") or [task.get("site")],
                   "n_actions": task.get("trajectory_actions"), "recommendation": review.get("recommendation"),
                   "tags": _tags(task)}
        tasks.append(summary)
        for tag in summary["tags"]:
            by_macro.setdefault(tag["macro"], []).append(
                {"key": key, "annotator": summary["annotator"], "instruction": summary["instruction"],
                 "recommendation": summary["recommendation"], **tag})
    return {"tasks": tasks, "macros": dict(sorted(by_macro.items(), key=lambda kv: (-len(kv[1]), kv[0])))}


def index():
    return _index(_signature())


def _outline(observation, limit=140):
    """Readable page outline for recordings without screenshots (accessibility tree or DOM)."""
    tree = observation.get("axtree_json")
    lines = []
    if tree:
        try:
            tree = json.loads(tree) if isinstance(tree, str) else tree
        except ValueError:
            tree = None
    if isinstance(tree, dict):
        def walk(node, depth):
            if len(lines) >= limit or not isinstance(node, dict):
                return
            label = node.get("text") or node.get("value") or node.get("name") or ""
            if label or node.get("role") not in ("div", "span", "section", "body"):
                extra = f" → {node['href']}" if node.get("href") else ""
                lines.append("  " * min(depth, 8) + f"{node.get('role', '')}: {str(label)[:120]}{extra}")
            for child in node.get("children") or []:
                walk(child, depth + 1)
        walk(tree, 0)
    elif observation.get("snapshot"):
        import re
        from html import unescape
        html = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", observation["snapshot"])
        text = unescape(re.sub(r"<[^>]+>", "\n", html))
        lines = [line.strip()[:160] for line in text.splitlines() if line.strip()][:limit]
    return "\n".join(lines)


def task_detail(annotator, task_id, source="gold"):
    """The task's tags plus every recorded action with its frame.

    `source` is the original recording ("gold", trajectory.json) or the fresh
    verification walk ("walk", verification_walk.json)."""
    d = (ANNOTATIONS_DIR / annotator / task_id).resolve()
    if d.parent.parent != ANNOTATIONS_DIR.resolve() or not (d / "task.json").is_file():
        return None
    task = json.loads((d / "task.json").read_text())
    name = "verification_walk.json" if source == "walk" else "trajectory.json"
    trajectory = json.loads((d / name).read_text()) if (d / name).is_file() else []
    events = trajectory if isinstance(trajectory, list) else trajectory.get("trajectory", [])
    actions, last_shot = [], None
    for i, e in enumerate(events):
        if e.get("type") == "observation" and e.get("screenshot"):
            last_shot = e["screenshot"]
        if e.get("type") != "action":
            continue
        # the observation recorded with (right after) the action shows its page
        shot, seen = None, None
        for nxt in events[i + 1:]:
            if nxt.get("type") == "action":
                break
            if nxt.get("type") == "observation":
                seen = seen or nxt
                if nxt.get("screenshot"):
                    shot = nxt["screenshot"]
                    break
        value = e.get("value")
        actions.append({"index": len(actions) + 1, "action": e.get("action"), "target": str(e.get("target") or "")[:200],
                        "value": "" if value in (None, "") else str(value)[:200],
                        "url": str(e.get("url") or "").replace("https://miniweb-production.up.railway.app", ""),
                        "frame": shot or last_shot,
                        "outline": "" if (shot or last_shot) else _outline(seen or {})})
    return {"key": f"{annotator}/{task_id}", "source": source, "instruction": task.get("instruction", ""),
            "expected_answer": task.get("expected_answer", ""), "tags": _tags(task),
            "edges": task.get("macro_edges") or [], "span_source": task.get("macro_span_source"),
            "actions": actions}
