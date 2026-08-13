"""Tighten macros that are 'too loose': their interaction group matches on action
TYPE alone (target/value OPEN) and their only backend grounding is a fully-open
request_made — so irrelevant clicks + any network event satisfy them.

Fix (keeps modality tolerance, adds relevance): re-anchor each such macro to the
reference trajectory's RELEVANT signals —
  * the terminal control the annotator clicked (button/link label, matched loosely), and/or
  * the value they entered (type/select/change/drag), via an affordance OR (modality-loose).
Plus: ground request_made to a SAME-SITE mutating call in the span when one exists,
else drop the useless open request_made. A junk-click trajectory then fails.

Only touches macros detected as loose; leaves the other ~440 checks untouched.
DRY-RUN prints a plan; pass --write to persist.
"""
import glob, json, pathlib, re, sys
sys.path.insert(0, ".")
from annotation import macro_templates as mt

WRITE = "--write" in sys.argv
GROUND = {"request_made", "page_visited", "qa_answer", "answer_grounded"}
VALUE_AFFORD = ["type", "select", "change"]


def leaves(node, acc):
    if not isinstance(node, dict):
        return
    if node.get("op") in ("AND", "OR"):
        for c in node.get("checks", []):
            leaves(c, acc)
    else:
        acc.append(node)


def is_open(v):
    return isinstance(v, dict) and v.get("open") is True


def asserted(n, k):
    v = n.get(k, {"open": True})
    return not (v is None or is_open(v) or v == "")


def is_loose(tree):
    """Grounded ONLY by request_made leaves that are all fully open (method+url open)."""
    ns = []
    leaves(tree, ns)
    g = [n for n in ns if n.get("type") in GROUND]
    if not g or any(n.get("type") != "request_made" for n in g):
        return False
    return all(not asserted(n, "method") and not asserted(n, "url") for n in g)


def label_of(target):
    m = re.search(r"'([^']+)'", target or "")
    return m.group(1).strip() if m else ""


def rel(u):
    i = (u or "").find("/sites/")
    return (u[i:] if i >= 0 else (u or "")).split("?")[0]


def site_of(task_dir):
    # dir name is "<site>_<hash>"; site may contain underscores but hash is last token
    return task_dir.name.rsplit("_", 1)[0]


def span_actions(task, traj, macro):
    tags = task.get("macro_tags") or []
    span = next((t.get("span") for t in tags if mt._canon(t.get("macro")) == macro), None)
    acts = [e for e in traj if e.get("type") == "action"]
    if span is None:
        return acts
    return [acts[i] for i in mt._span_indices(span, len(acts))]


def a_incl(action, *, target=None, value=None):
    n = {"type": "action_included", "action": action,
         "target": target if target else {"open": True},
         "value": value if value else {"open": True}}
    return n


# control-label keywords that signal the macro's committing action (navigation
# links like 'Contacts' won't match, so a coarse span's trailing nav is ignored)
MACRO_KEYWORDS = {
    "export": ["export", "download", "csv"],
    "delete_from_table": ["delete", "remove"],
    "share_by_form": ["share", "post", "send", "comment"],
    "edit_by_form": ["save", "update", "submit", "edit", "post", "run"],
    "edit_by_image": ["save", "update"],
    "configure_by_form": ["save", "apply", "set", "update"],
}


def build_interaction(sacts, macro):
    """Relevance-anchored interaction node from the span's actions, or None.

    Anchors on the committing BUTTON the annotator clicked and/or the VALUE they
    entered. A slider/canvas 'control' is not a button, so there we anchor on the
    value only; freeform multi-line values (code, long bodies) are skipped as too
    tight and we fall back to the button (+ backend) instead.
    """
    kws = MACRO_KEYWORDS.get(macro, [])
    labeled = [(a.get("action"), a.get("target") or "", label_of(a.get("target") or ""))
               for a in sacts if a.get("action") in ("click", "submit") and label_of(a.get("target") or "")]

    # committing control: only trust a real BUTTON (links/sliders are navigation
    # or the widget itself, not the commit). Prefer one matching the macro intent.
    btns = [lb for act, t, lb in labeled if t.startswith("button")]
    btn = next((lb for lb in reversed(btns) if any(k in lb.lower() for k in kws)),
               btns[-1] if btns else "")
    # if no button at all, a labeled link matching intent is the next best anchor
    if not btn:
        btn = next((lb for act, t, lb in reversed(labeled) if any(k in lb.lower() for k in kws)), "")

    # entered value: LAST non-empty (corrected) value; skip freeform (code/long)
    vals = [(a.get("value") or a.get("text") or a.get("option_text") or "").strip()
            for a in sacts if a.get("action") in ("type", "select", "change", "drag")]
    vals = [v for v in vals if v]
    primary = vals[-1] if vals else ""
    freeform = bool(primary) and ("\n" in primary or len(primary) > 80)
    if freeform:
        primary = ""

    branches = []
    if btn:
        branches.append(a_incl("click", target=btn))
    if primary:
        branches.append({"op": "OR", "label": f"entered value {primary[:40]!r}",
                         "checks": [a_incl(af, value=primary) for af in VALUE_AFFORD]})
    if not branches:
        return None
    if len(branches) == 1:
        return branches[0]
    return {"op": "AND", "label": "relevant interaction (control + value)", "checks": branches}


# URL-path keywords that make a mutating call plausibly THIS macro's commit — so we
# don't ground onto an unrelated same-site POST (e.g. a 'join' during a delete task)
URL_KEYWORDS = {
    "export": ["export", "download"],
    "delete_from_table": ["delete", "remove"],
    "share_by_form": ["share", "comment"],
    "edit_by_form": ["save", "update", "edit", "execute", "run", "note"],
    "edit_by_image": ["save", "update", "note"],
    "configure_by_form": ["config", "setting", "prefs", "update", "save"],
}


def ground_backend(sacts, traj, site, macro):
    """Ground a same-site mutating call whose URL matches this macro's intent —
    only when one clearly corresponds; otherwise drop the useless open request_made."""
    ukws = URL_KEYWORDS.get(macro, [])
    if not ukws:
        return None
    muts = [e for e in traj if (e.get("method") or "").upper() in ("POST", "PUT", "PATCH", "DELETE")
            and f"/sites/{site}/" in (e.get("url") or "")
            and any(k in rel(e.get("url")).lower() for k in ukws)]
    if not muts:
        return None
    call = muts[0]
    return {"type": "request_made", "method": call["method"].upper(),
            "url": rel(call["url"]), "body_fields": {"open": True},
            "status": {"open": True}, "label": "backend call for this macro"}


def main():
    changed, skipped = [], []
    for vf in sorted(glob.glob("data/annotations/*/*/verifier.json")):
        spec = json.load(open(vf))
        d = pathlib.Path(vf).parent
        macros = spec.get("macros") or {}
        loose = {m: t for m, t in macros.items() if is_loose(t)}
        if not loose:
            continue
        task = json.load(open(d / "task.json"))
        traj = mt._load_trajectory(d)
        site = site_of(d)
        tid = f"{d.parent.name}/{d.name}"
        for m, tree in loose.items():
            sacts = span_actions(task, traj, m)
            inter = build_interaction(sacts, m)
            if inter is None:
                skipped.append((tid, m, "no control/value to anchor"))
                continue
            backend = ground_backend(sacts, traj, site, m)
            checks = [inter] + ([backend] if backend else [])
            new_tree = checks[0] if len(checks) == 1 else {
                "op": "AND", "label": f"{m} (relevance-anchored)", "checks": checks}
            macros[m] = new_tree
            changed.append((tid, m, bool(backend), inter))
        if WRITE:
            spec["retightened"] = True
            (d / "verifier.json").write_text(json.dumps(spec, indent=1, ensure_ascii=False))

    print(f"{'WROTE' if WRITE else 'DRY-RUN'}: retightened {len(changed)} macros, skipped {len(skipped)}\n")
    for tid, m, be, inter in changed:
        print(f"  ✓ {tid} [{m}]  backend={'grounded' if be else 'dropped'}")
        print("      " + json.dumps(inter))
    print()
    for tid, m, why in skipped:
        print(f"  – SKIP {tid} [{m}]  ({why})")


main()
