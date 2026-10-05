"""Grader audit: blind human labels of agent episodes, to check the verifier and the VLM judge (review round 1, C1).

Cases (built by scripts/build_grader_audit.py, uploaded by scripts/upload_db_railway.py --grader-audit) live in
<ANNOTATIONS_DIR>/.grader_audit/<case_id>/ as case.json + step images; their order and the overlap set every labeler
does are in .grader_audit/_index/order.json. Labels are appended to <ANNOTATIONS_DIR>/.grader_audit_labels/
<labeler>.jsonl; the last record of a case wins. Nothing here knows either grader's verdict.
"""
import json
import re
from datetime import datetime, timezone

from annotation.storage import ANNOTATIONS_DIR

VALUES = {"pass", "fail", "unsure"}
_ID = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


def _cases_dir():
    return ANNOTATIONS_DIR / ".grader_audit"


def _labels_dir():
    return ANNOTATIONS_DIR / ".grader_audit_labels"


def _labeler_file(labeler):
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", labeler or "anonymous")[:60]
    return _labels_dir() / f"{safe}.jsonl"


def order():
    """(ordered case ids, overlap ids)."""
    root = _cases_dir()
    f = root / "_index" / "order.json"
    if f.exists():
        d = json.loads(f.read_text())
        ids = [c for c in d.get("order", []) if (root / c / "case.json").exists()]
        return ids, set(d.get("overlap", []))
    if not root.exists():
        return [], set()
    return sorted(p.parent.name for p in root.glob("*/case.json")), set()


def case(case_id):
    if not _ID.match(case_id or ""):
        return None
    f = _cases_dir() / case_id / "case.json"
    return json.loads(f.read_text()) if f.exists() else None


def case_dir(case_id):
    return _cases_dir() / case_id if _ID.match(case_id or "") else None


def labels(labeler):
    """{case_id: last label record} of one labeler."""
    f = _labeler_file(labeler)
    return labels_from_file(f) if f.exists() else {}


def all_labels():
    """Every labeler's last label per case: [{labeler, case_id, primitives, notes, at}]."""
    out = []
    d = _labels_dir()
    if d.exists():
        for f in sorted(d.glob("*.jsonl")):
            out += labels_from_file(f).values()
    return out


def labels_from_file(f):
    out = {}
    for line in f.read_text().splitlines():
        if line.strip():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            out[r.get("case_id")] = r
    return out


def save(labeler, case_id, primitives, notes=""):
    """Validate and append one label. Raises ValueError on a bad case or value."""
    c = case(case_id)
    if c is None:
        raise ValueError(f"unknown case {case_id!r}")
    want = {p["instance"] for p in c["primitives"]}
    prim = {k: v for k, v in (primitives or {}).items() if k in want}
    if set(prim) != want or any(v not in VALUES for v in prim.values()):
        raise ValueError(f"label every primitive as one of {sorted(VALUES)}")
    rec = {"labeler": labeler, "case_id": case_id, "primitives": prim, "notes": (notes or "")[:4000],
           "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    f = _labeler_file(labeler)
    f.parent.mkdir(parents=True, exist_ok=True)
    with open(f, "a") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec
