"""AI recommendations and versioned verifier evidence; human decisions stay separate."""
import hashlib
import json
import threading
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECOMMENDATIONS = {'keep', 'repaired', 'needs_repair', 'suggest_delete', 'unreviewed'}
SOURCES = ('gold', 'walk', 'agent', 'empty', 'answer_only')
LABELS = {'keep': 'Keep candidate', 'repaired': 'Repaired', 'needs_repair': 'Needs repair',
          'suggest_delete': 'Deletion suggested', 'unreviewed': 'Not reviewed', 'stale': 'Review outdated'}
TASK_FIELDS = ('instruction', 'instruction_ambiguous', 'expected_answer', 'answer', 'answer_type',
               'alternatives', 'expected_outcome', 'macros', 'macro_instances', 'macro_edges',
               'macro_subtasks', 'macro_operations', 'qa_answers', 'starting_url', 'sites', 'requires_login')
_LOCK = threading.RLock()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


@lru_cache(maxsize=4096)
def _file_hash(path, size, mtime, ctime):
    with open(path, 'rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def file_hash(path):
    try:
        stat = path.stat()
        return _file_hash(str(path.resolve()), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
    except FileNotFoundError:
        return None


def read_json(path, default=None):
    try:
        value = json.loads(path.read_text())
        return value if isinstance(value, dict) else (default if default is not None else {})
    except (OSError, ValueError):
        return default if default is not None else {}


def task_hash(task):
    return digest({key: task.get(key) for key in TASK_FIELDS})


def spec_hash(macros):
    return digest(macros)


def engine_hash():
    return digest({p: file_hash(ROOT / p) for p in ('evaluation/verifiers.py',
        'evaluation/evidence_checks.py', 'evaluation/trajectory.py', 'annotation/verifier_scaffold.py')})


def source_hash(directory, source):
    if source in ('empty', 'answer_only'):
        return digest(source)
    if source == 'agent':
        folder = ROOT / 'evaluation/results' / ('recorded_' + directory.name)
        names = ('trajectory.json', 'server_log.json', 'result.json')
    else:
        folder = directory
        names = ('verification_walk.json',) if source == 'walk' else ('trajectory.json', 'server_log.json')
    return digest({name: file_hash(folder / name) for name in names})


def snapshot(task, macros):
    return {'task': task_hash(task), 'spec': spec_hash(macros), 'engine': engine_hash()}


def save_ai_review(directory, task, data, actor):
    if not isinstance(data, dict):
        raise ValueError('Review must be a JSON object')
    recommendation = data.get('recommendation')
    if recommendation not in RECOMMENDATIONS:
        raise ValueError('Invalid AI recommendation')
    for key in ('issues', 'limitations', 'changes', 'documents'):
        if not isinstance(data.get(key, []), list) or any(not isinstance(x, str) for x in data.get(key, [])):
            raise ValueError(key + ' must be a list of strings')
    if not isinstance(data.get('note', ''), str):
        raise ValueError('note must be text')
    review = {key: data.get(key, [] if key != 'note' else '')
              for key in ('note', 'issues', 'limitations', 'changes', 'documents')}
    review.update(schema_version=1, recommendation=recommendation, reviewer=actor,
                  reviewed_at=datetime.now(timezone.utc).isoformat(),
                  task_hash=task_hash(task),
                  spec_hash=spec_hash(read_json(directory / 'verifier.json').get('macros', {})),
                  recording_hash=source_hash(directory, 'gold'))
    task['ai_review'] = review
    (directory / 'task.json').write_text(json.dumps(task, indent=2, ensure_ascii=False))
    return review


def record_run(directory, task, macros, source, report):
    """Only call for the saved effective spec, never unsaved builder drafts."""
    entry = dict(snapshot(task, macros), source=source, source_hash=source_hash(directory, source),
                 passed=bool(report['passed']), action_count=report.get('action_count', 0),
                 run_at=datetime.now(timezone.utc).isoformat())
    if report.get('engine_hash'):
        entry['engine'] = report['engine_hash']
    # Last result per source bounds storage and prevents parallel gold/walk writes losing a result.
    path = directory / 'verifier_runs.json'
    with _LOCK:
        payload = read_json(path, {'schema_version': 1, 'runs': {}})
        payload.setdefault('runs', {})[source] = entry
        tmp = path.with_suffix('.tmp')
        tmp.write_text(json.dumps(payload, indent=2))
        tmp.replace(path)
    return entry


def effective_macros(task, macros):
    from copy import deepcopy
    from annotation.verifier_scaffold import inject_qa_leaf, refresh_expected
    result = deepcopy(macros)
    inject_qa_leaf(result, task)
    refresh_expected(result, task)
    return result


def summary(directory, task):
    spec = read_json(directory / 'verifier.json').get('macros', {})
    ai = task.get('ai_review') or {}
    legacy = task.get('task_audit') or {}
    decision = ai.get('recommendation') or {'repair': 'needs_repair'}.get(legacy.get('decision'), legacy.get('decision', 'unreviewed'))
    if decision not in RECOMMENDATIONS:
        decision = 'unreviewed'
    stale = bool(ai) and (ai.get('task_hash') != task_hash(task) or
        ai.get('spec_hash') != spec_hash(spec) or ai.get('recording_hash') != source_hash(directory, 'gold'))
    state = 'stale' if stale else decision
    current = snapshot(task, effective_macros(task, spec))
    runs = []
    for source, entry in read_json(directory / 'verifier_runs.json').get('runs', {}).items():
        if source not in SOURCES:
            continue
        outdated = any(entry.get(k) != v for k, v in current.items()) or entry.get('source_hash') != source_hash(directory, source)
        negative = source in ('empty', 'answer_only')
        ok = not entry.get('passed') if negative else entry.get('passed')
        runs.append(dict(entry, stale=outdated, ok=ok,
                         label='Outdated' if outdated else ('Rejected' if ok else 'Accepted') if negative else ('Pass' if ok else 'Fail')))
    walk = next((r for r in runs if r['source'] == 'walk'), None)
    attention = state in ('unreviewed', 'needs_repair', 'suggest_delete', 'stale') or any(not r['ok'] or r['stale'] for r in runs)
    return {'ai': state, 'recommendation': decision, 'ai_label': LABELS[state], 'legacy': not bool(ai) and bool(legacy),
            'review': ai or {'note': legacy.get('note', ''), 'reviewer': legacy.get('reviewer', '')},
            'runs': runs, 'walk': 'unrun' if not walk else 'stale' if walk['stale'] else 'pass' if walk['ok'] else 'fail',
            'attention': attention, 'has_verifier': bool(spec)}
