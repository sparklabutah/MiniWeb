"""Repair form state in recorded HTML snapshots.

The old recorder serialized pages with outerHTML, which writes ATTRIBUTES, not
live DOM PROPERTIES. Typed text lives in el.value (a property), so a snapshot
taken after typing shows an empty input — the page state is wrong, silently.
(recorder.js now mirrors properties into attributes before serializing, so this
only affects recordings made before that fix.)

The axtree, however, reads live properties and DID capture the value. This pass
recovers the value from the action itself (which records exactly what was typed
or selected) and injects it into the corresponding element in the HTML snapshot,
so the snapshot finally shows what the annotator saw.

Only observations that follow a value-setting action (type/change/select/check)
are touched, and only when the value is missing from the HTML. Every repaired
observation is flagged:

    "form_state_repaired": true

Screenshots/axtrees derived from a repaired snapshot should be regenerated —
run scripts/backfill_observations.py afterwards (it will re-render them).

Usage:
    python scripts/repair_form_state.py --dry-run
    python scripts/repair_form_state.py
"""
import argparse
import glob
import html as html_mod
import json
import os
import re

VALUE_ACTIONS = ("type", "change", "select", "check")


def _find_input_by_selector(snapshot, selector):
    """Locate the opening tag of the element the action targeted.

    Recorded selectors are things like  input[name="date_from"],  #code-input,
    select[name="status"]. Match on name= / id= — the only parts that identify a
    specific element; bare tag selectors ("input") cannot and are skipped.
    """
    m = re.search(r'\[name=["\']?([^"\'\]]+)', selector or "")
    if m:
        return ("name", m.group(1))
    m = re.match(r"#([\w-]+)", selector or "")
    if m:
        return ("id", m.group(1))
    return (None, None)


def _select_body(snapshot, selector):
    """Return (match, head, body, tail) for the <select> the selector names."""
    attr, key = _find_input_by_selector(snapshot, selector)
    if not attr:
        return None
    sel_re = re.compile(
        rf'(<select\b[^>]*\b{attr}=["\']?{re.escape(key)}["\']?[^>]*>)(.*?)(</select>)',
        re.S | re.I)
    return sel_re.search(snapshot)


def _option_is_selected(snapshot, selector, value):
    """True when the option carrying `value` already has the selected attribute."""
    m = _select_body(snapshot, selector)
    if not m:
        return False
    body = m.group(2)
    opt = re.search(
        rf'<option\b[^>]*\bvalue=["\']?{re.escape(str(value))}["\']?[^>]*>', body, re.I)
    return bool(opt and re.search(r'\bselected\b', opt.group(0), re.I))


def _inject_value(snapshot, attr, key, value, is_select, selector=""):
    """Put `value` into the element identified by attr=key. Returns new html or None."""
    esc_key = re.escape(key)
    esc_val = html_mod.escape(str(value), quote=True)

    if is_select:
        m = _select_body(snapshot, selector)
        if not m:
            return None
        head, body, tail = m.groups()
        # clear any existing selection (the default option is usually marked
        # selected), then mark the option the annotator actually chose
        body_new = re.sub(r'\s+selected(=(["\'])[^"\']*\2)?', "", body, flags=re.I)
        body_new, n = re.subn(
            rf'(<option\b[^>]*\bvalue=["\']?{re.escape(str(value))}["\']?)',
            r"\1 selected", body_new, count=1, flags=re.I)
        if not n:
            return None
        return snapshot[:m.start()] + head + body_new + tail + snapshot[m.end():]

    # input/textarea: add or replace the value attribute on the opening tag
    tag_re = re.compile(
        rf'<(input|textarea)\b([^>]*\b{attr}=["\']?{esc_key}["\']?[^>]*)>', re.I)
    m = tag_re.search(snapshot)
    if not m:
        return None
    tag, attrs = m.group(1), m.group(2)
    if re.search(r'\bvalue=', attrs, re.I):
        # lambda replacement: a literal string would let re interpret backslashes
        # in the value (e.g. "C:\\fakepath\\letter.docx") as escape sequences
        attrs_new = re.sub(r'\bvalue=(["\']).*?\1', lambda _m: f'value="{esc_val}"',
                           attrs, count=1, flags=re.I)
    else:
        attrs_new = attrs.rstrip() + f' value="{esc_val}"'
    return snapshot[:m.start()] + f"<{tag}{attrs_new}>" + snapshot[m.end():]


def repair_task(traj_file, dry_run=False):
    events = json.loads(open(traj_file).read())
    acts = [(i, e) for i, e in enumerate(events) if e.get("type") == "action"]
    repaired = skipped = 0

    for n, (i, action) in enumerate(acts):
        if action.get("action") not in VALUE_ACTIONS:
            continue
        value = action.get("text") or action.get("value") or action.get("option_text")
        if value in (None, ""):
            continue
        nxt = acts[n + 1][0] if n + 1 < len(acts) else len(events)
        obs = next((events[j] for j in range(i + 1, nxt)
                    if events[j].get("type") == "observation"), None)
        if not obs:
            continue
        snapshot = obs.get("snapshot") or ""
        if not snapshot:
            continue
        is_select = action.get("action") == "select"
        if not is_select and str(value) in snapshot:
            continue  # value already in the markup — nothing to do
        if is_select and _option_is_selected(snapshot, action.get("selector", ""), value):
            continue
        # NB: for a <select>, the option's value string always appears in the
        # HTML (it is one of the options) — that is NOT evidence the option was
        # chosen. Only the `selected` attribute on the right <option> is.

        attr, key = _find_input_by_selector(snapshot, action.get("selector", ""))
        if not attr:
            skipped += 1
            continue
        new_html = _inject_value(snapshot, attr, key, value,
                                 is_select=is_select,
                                 selector=action.get("selector", ""))
        if not new_html:
            skipped += 1
            continue
        if not dry_run:
            obs["snapshot"] = new_html
            obs["form_state_repaired"] = True
        repaired += 1

    if repaired and not dry_run:
        with open(traj_file, "w") as f:
            json.dump(events, f, ensure_ascii=False)
    return repaired, skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    total_r = total_s = touched = 0
    for tf in sorted(glob.glob("data/annotations/*/*/trajectory.json")):
        r, s = repair_task(tf, dry_run=args.dry_run)
        if r or s:
            print(f"  {os.path.basename(os.path.dirname(tf)):40s} repaired={r} unmatched={s}")
        total_r += r
        total_s += s
        touched += bool(r)

    print(f"\n{'(dry run) ' if args.dry_run else ''}"
          f"repaired {total_r} observations across {touched} tasks; "
          f"{total_s} could not be matched to an element")
    if total_r and not args.dry_run:
        print("Re-run scripts/backfill_observations.py to regenerate screenshots/axtrees "
              "from the repaired HTML.")


if __name__ == "__main__":
    main()
