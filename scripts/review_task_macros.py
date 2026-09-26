"""Build/replay the September macro review. Mutations use the annotation API only."""
import argparse
import copy
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from annotation.macros import canon, all_canonical, operation_names
from annotation.quality import effective_macros
from annotation.verifier_scaffold import _span_indices

P = ROOT / 'data/task_review_macros_2026-09-23'
FIELDS = ('macros', 'macro_instances', 'num_macros', 'macro_operations', 'macro_edges',
          'macro_positions', 'macro_subtasks', 'macro_spans', 'macro_tags', 'qa_answers',
          'macro_span_source', 'macro_ai_review')


def read(path):
    return json.loads(path.read_text())


def base(m):
    return canon(m.split('#', 1)[0])


def canonical_node(m):
    b, sep, occurrence = m.partition('#')
    return canon(b) + (sep + occurrence if sep else '')


def conjunction(trees):
    unique = []
    for tree in trees:
        if tree not in unique:
            unique.append(copy.deepcopy(tree))
    assert unique
    return unique[0] if len(unique) == 1 else {'op': 'AND', 'checks': unique}


def build():
    baseline = read(P / 'baseline.json')
    keys = read(P / 'ordered_keys.json')
    decisions = {}
    for line in (P / 'manual_decisions.tsv').read_text().splitlines():
        if not line or line.startswith('#'):
            continue
        i, renames, additions, ops, reason = [x.strip() for x in line.split('|')]
        decisions[int(i)] = ({k: v for k, v in (s.split('>') for s in renames.split(',') if s)},
                             {k: v for k, v in (s.split('<') for s in additions.split(',') if s)},
                             {k: v for k, v in (s.split('=') for s in ops.split(',') if s)}, reason)
    # Preserve genuine destination-only navigation tasks already in the dataset.
    navigation_tasks = {99, 194, 218, 299, 347, 365}
    plan = {}
    for i, key in enumerate(keys):
        original = baseline[key]['task']
        task = copy.deepcopy(original)
        saved = copy.deepcopy((baseline[key]['verifier'] or {}).get('macros', {}))
        renames, additions, overrides, reason = decisions.get(i, ({}, {}, {}, ''))
        renames = dict(renames)
        old = original.get('macro_instances') or original.get('macros', [])
        counts = Counter()
        old_nodes = []
        for m in old:
            m = canonical_node(m)
            if m in old_nodes:
                counts[base(m)] += 1
                m = base(m) + '#' + str(counts[base(m)] + 1)
            old_nodes.append(m)
        notes = [reason] if reason else []
        if 'navigate_by_route' in map(base, old_nodes) and i not in navigation_tasks and 'navigate_by_route' not in renames:
            targets = [base(m) for m in old_nodes if base(m) != 'navigate_by_route']
            assert targets, (i, 'navigation-only case not reviewed')
            target = next((m for m in targets if m != 'report_information'), targets[0])
            renames['navigate_by_route'] = renames.get(target, target)
            notes.append('Removed incidental navigation as a separate macro; its existing page gates remain attached to the workflow.')
        # A rename merging into an existing macro does not create an extra occurrence.
        current_bases = {base(m) for m in old_nodes}
        node_map = {}
        nodes = []
        for m in old_nodes:
            b = base(m)
            dest = renames.get(b, b)
            suffix = m[len(b):]
            n = dest if b != dest and dest in current_bases else dest + suffix
            node_map[m] = n
            if n not in nodes:
                nodes.append(n)
        for added in additions:
            if added not in nodes:
                nodes.append(added)
        # The two sign-ins were collapsed by an earlier instruction repair.
        if i == 204:
            nodes.insert(2, 'authenticate_by_form#2')
            notes.append('Restored separate WebMail and Lakeport Medical authentication occurrences.')
        # Restore the three separately recorded find/save pairs in PhoneCompare.
        if i == 104:
            nodes = ['search', 'toggle_relationship', 'search#2', 'toggle_relationship#2',
                     'search#3', 'toggle_relationship#3', 'compare_by_form', 'report_information']
            notes.append('Recovered the three distinct phone searches and Favorite actions from the original tags.')
        operations = {}
        for m, op in (original.get('macro_operations') or {}).items():
            n = node_map.get(canonical_node(m))
            if n in nodes and op in operation_names() and (base(m) != 'navigate_by_route'):
                operations[n] = op
        for m, op in overrides.items():
            assert op == '-' or op in operation_names(), (i, m, op)
            assert m in nodes, (i, m, nodes)
            if op == '-':
                operations.pop(m, None)
            else:
                operations[m] = op
        if 'report_information' in nodes and not operations.get('report_information'):
            operations['report_information'] = 'read'
            notes.append('Made the terminal reporting operation explicit (read displayed information).')
        # Fold a removed navigation selection operation where it describes real reasoning.
        navop = (original.get('macro_operations') or {}).get('navigate_by_route')
        if navop == 'extremum' and 'navigate_by_route' in renames:
            receiver = 'report_information' if 'report_information' in nodes else renames['navigate_by_route']
            if receiver not in overrides and not operations.get(receiver):
                operations[receiver] = navop
        # Re-key saved verifier trees without deleting any existing condition.
        grouped = {}
        for m, tree in saved.items():
            target = renames.get(base(m), base(m))
            grouped.setdefault(target, []).append(tree)
        for target, donor in additions.items():
            if saved:
                assert donor in saved, (i, target, donor)
                grouped.setdefault(target, []).append(saved[donor])
        spec = {m: conjunction(trees) for m, trees in grouped.items()}
        if i == 215:
            def remove_wildcard_alternatives(tree):
                if tree.get('op') == 'OR':
                    tree['checks'] = [ch for ch in tree['checks'] if not (
                        ch.get('type') == 'action_included' and not ch.get('advisory')
                        and any(isinstance(v, dict) and v.get('open') for v in ch.values()))]
                for child in tree.get('checks', []):
                    remove_wildcard_alternatives(child)
            remove_wildcard_alternatives(spec['search'])
            notes.append('Removed two unfilled submit/keypress alternatives from the search gate; retained the specific search interaction and exact query request.')
        if 'report_information' in additions:
            # Move terminal QA to its reporting node. Keeping another copy on
            # the now-intermediate action would incorrectly demand a reasoning
            # trace as well as the user's answer.
            donor = renames.get(additions['report_information'], additions['report_information'])
            def without_qa(tree):
                if tree.get('type') == 'qa_answer':
                    return None
                if tree.get('op') == 'AND':
                    children = [child for ch in tree['checks']
                                if (child := without_qa(ch)) is not None]
                    return conjunction(children) if children else None
                return tree
            stripped = without_qa(spec[donor])
            assert stripped, (i, 'report donor has no action gate')
            spec[donor] = stripped
        assert set(spec) == {base(n) for n in nodes} or not saved, (i, set(spec), nodes)
        # Collapse renamed nodes and canonicalize obsolete aliases. Reporting is terminal.
        def mapped(n):
            n = canonical_node(n)
            return node_map.get(n, n)
        edges = []
        for e in original.get('macro_edges') or []:
            a, b = mapped(e.get('from', '')), mapped(e.get('to', ''))
            if a in nodes and b in nodes and a != b and a != 'report_information':
                edge = {'from': a, 'to': b}
                if edge not in edges:
                    edges.append(edge)
        # Reject cycles introduced by consolidating old occurrence paths.
        graph = {n: [] for n in nodes}
        clean_edges = []
        def reaches(a, b, seen=None):
            seen = set() if seen is None else seen
            if a == b:
                return True
            if a in seen:
                return False
            seen.add(a)
            return any(reaches(c, b, seen) for c in graph[a])
        for e in edges:
            if not reaches(e['to'], e['from']):
                graph[e['from']].append(e['to'])
                clean_edges.append(e)
        edges = clean_edges
        if 'report_information' in nodes:
            for n in nodes:
                if n != 'report_information' and not graph[n]:
                    edges.append({'from': n, 'to': 'report_information'})
        # Valid recorded boundaries are historical evidence, not new walkthrough annotations.
        traj_path = ROOT / 'data/annotations' / key / 'trajectory.json'
        action_count = sum(e.get('type') == 'action' for e in read(traj_path)) if traj_path.exists() else 0
        spans = {}
        span_candidates = dict(original.get('macro_spans') or {})
        for tag in original.get('macro_tags') or []:
            m = tag.get('macro')
            if m and m not in span_candidates and tag.get('span'):
                span_candidates[m] = tag['span']
        for m, span in span_candidates.items():
            n = mapped(m)
            if n in nodes and base(m) != 'navigate_by_route' and _span_indices(span, action_count) and n not in spans:
                spans[n] = span
        if i in navigation_tasks:
            s = span_candidates.get('navigate_by_route')
            if _span_indices(s, action_count):
                spans['navigate_by_route'] = s
        # Old free-text subtasks often describe superseded instructions. Retain
        # only independently reviewed occurrence descriptions below.
        subtasks = {}
        if len(nodes) != len(set(map(base, nodes))):
            approved = {343, 345, 368, 399}
            if i in approved:
                subtasks = {mapped(m): v for m, v in (original.get('macro_subtasks') or {}).items()
                            if mapped(m) in nodes}
        if i == 204:
            subtasks = {'authenticate_by_form': 'Sign in to WebMail with the supplied credentials.',
                        'authenticate_by_form#2': 'Sign in to Lakeport Medical with the supplied credentials.',
                        'filter_by_dropdown': 'Show Scheduled appointments.',
                        'search': 'Find the sent implementation email and check the Phase 1 dates.',
                        'cancel_by_form': 'Cancel the July 15 dentist-referral consultation.'}
        if i == 332:
            subtasks = {'search': 'Find contacts whose displayed names use Dr.',
                        'create_by_form': 'Create Doctorate contacts.',
                        'edit_by_cell': 'Enter the requested contact columns and records.',
                        'edit_by_cell#2': 'Continue entering contact records.',
                        'edit_by_cell#3': 'Complete the contact records and save.'}
        qa = {}
        for m, value in (original.get('qa_answers') or {}).items():
            n = mapped(m)
            if n in nodes and (n not in qa or m == n):
                qa[n] = value
        positions = {}
        for m, pos in (original.get('macro_positions') or {}).items():
            n = mapped(m)
            if n in nodes and n not in positions:
                positions[n] = pos
        for j, n in enumerate(nodes):
            positions.setdefault(n, {'x': 60 + (j % 4) * 240, 'y': 40 + (j // 4) * 100})
        task.update(macros=[base(n) for n in nodes], macro_instances=nodes, num_macros=len(nodes),
                    macro_operations=operations, macro_edges=edges, macro_positions=positions,
                    macro_subtasks=subtasks, macro_spans=spans, qa_answers=qa,
                    macro_span_source={'source': 'gold', 'recording_hash': baseline[key]['recording_hash'],
                                       'index_base': 1, 'status': 'historical_boundaries_not_reannotated'})
        task['macro_tags'] = [{'macro': base(n), 'instance': n, 'op': operations.get(n),
                               'span': spans.get(n, []), 'subtask': subtasks.get(n, ''),
                               'from': 'codex-macro-review'} for n in nodes]
        semantic_changed = (task['macros'] != original.get('macros', []) or
                            operations != (original.get('macro_operations') or {}) or
                            nodes != (original.get('macro_instances') or original.get('macros', [])))
        metadata_changes = [f for f in FIELDS[:-2] if task.get(f) != original.get(f)]
        if not notes:
            notes.append('Reviewed the instruction, physical interaction labels, and reasoning operations; no semantic tag correction was needed.')
        if original.get('macro_subtasks') and subtasks != original.get('macro_subtasks'):
            notes.append('Removed legacy free-text hints that were not reconfirmed against the revised instruction; the current instruction remains authoritative.')
        if metadata_changes:
            notes.append('Synchronized instance IDs, graph edges, tag chips, operation keys, positions, and valid historical span references.')
        task['macro_ai_review'] = {'reviewer': 'codex-review', 'reviewed_at': datetime.now(timezone.utc).isoformat(),
                                  'status': 'corrected' if semantic_changed else 'checked', 'notes': notes,
                                  'span_status': 'Historical gold boundaries retained where valid; not manually re-annotated for the repaired walkthrough.',
                                  'document': f'data/task_review_macros_2026-09-23/tasks/{key.replace("/", "__")}.md'}
        plan[key] = {'index': i, 'semantic_changed': semantic_changed, 'notes': notes,
                     'fields': {f: task[f] for f in FIELDS if task.get(f) != original.get(f)},
                     'task': task, 'macros': spec, 'verifier_changed': spec != saved,
                     'verifier_note': 'Required outcome conditions retained under corrected base labels; added labels reuse the corresponding compound workflow gate. Terminal QA checks moved to report nodes. One noted wildcard repair tightens search. Grading remains per base macro.'}
    (P / 'plan.json').write_text(json.dumps(plan, indent=2, ensure_ascii=False))
    print({'reviewed': len(plan), 'semantic_changes': sum(r['semantic_changed'] for r in plan.values()),
           'verifier_rekeys': sum(r['verifier_changed'] for r in plan.values())})


def session():
    import requests
    s = requests.Session()
    for c in read(Path('/tmp/miniweb-review-browser.json'))['cookies']:
        s.cookies.set(c['name'], c['value'], domain=c['domain'], path=c['path'])
    return s


def apply():
    plan = read(P / 'plan.json')
    s = session()
    applied = []
    for key, row in plan.items():
        ann, tid = key.split('/')
        for field, value in row['fields'].items():
            r = s.post('http://127.0.0.1:8080/annotate/api/update_task_field',
                       json={'annotator': ann, 'task_id': tid, 'field': field, 'value': value}, timeout=30)
            assert r.ok, (key, field, r.status_code)
        if row['verifier_changed']:
            r = s.post(f'http://127.0.0.1:8080/annotate/api/task_verifier/{ann}/{tid}',
                       json={'macros': row['macros']}, timeout=30)
            assert r.ok, (key, r.status_code)
        applied.append(key)
        (P / 'applied.json').write_text(json.dumps(applied, indent=2, ensure_ascii=False))
        if len(applied) % 50 == 0:
            print('Updated through annotation API', len(applied), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['build', 'apply'])
    args = parser.parse_args()
    {'build': build, 'apply': apply}[args.action]()
