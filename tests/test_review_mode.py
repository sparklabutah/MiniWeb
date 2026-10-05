import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from annotation import review_mode


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


class ReviewModeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.patches = [mock.patch.object(review_mode, 'ANNOTATIONS_DIR', self.root),
                        mock.patch('annotation.macro_browser.ANNOTATIONS_DIR', self.root)]
        for p in self.patches:
            p.start()
        review_mode._index.cache_clear()
        self.task = self.root / 'Minh' / 'news_0001'
        _write(self.task / 'task.json', {
            'instruction': 'Find the latest Weather article and save it.', 'macros': ['toggle_relationship'],
            'review_tag': {'tag': 'verified', 'by': 'minh', 'at': '2026-08-05T01:00:00Z'},
            'ai_review': {'recommendation': 'repaired', 'reviewed_at': '2026-09-22T12:00:00+00:00'}})
        _write(self.task / 'verifier.json', {'macros': {'toggle_relationship': {'type': 'request_made'}}})

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def freeze(self, **task):
        before = {'instruction': 'Find the latest Weather article and save it.', 'macros': ['toggle_relationship']}
        before.update(task)
        review_mode.write_before(self.task, before, {'macros': {}}, 'test')

    def queues(self):
        review_mode._index.cache_clear()
        return review_mode.index()['tasks'][0]['queues']

    def test_first_edit_freezes_the_original_once(self):
        self.assertTrue(review_mode.ensure_before(self.task))
        frozen = json.loads((self.task / 'before_review.json').read_text())
        self.assertEqual(frozen['task']['macros'], ['toggle_relationship'])
        self.assertFalse(review_mode.ensure_before(self.task))      # never overwritten

    def test_tags_from_before_the_correction_count_as_unmarked(self):
        for tag in ('verified', 'stale', None):
            task = json.loads((self.task / 'task.json').read_text())
            task['review_tag'] = tag and {'tag': tag, 'by': 'minh', 'at': '2026-08-05T01:00:00Z'}
            (self.task / 'task.json').write_text(json.dumps(task))
            self.assertEqual(self.queues(), ['todo', 'all'])
            self.assertIsNone(review_mode.detail('Minh', 'news_0001')['human'])

    def test_instruction_only_change_counts_as_reworded(self):
        self.freeze(instruction='Can you go to News and save the latest weather article?')
        changed = review_mode.detail('Minh', 'news_0001')['changed']
        self.assertTrue(changed['instruction'])
        self.assertFalse(changed['tags'])

    def test_reverifying_after_the_correction_moves_it_to_done(self):
        self.freeze(macros=['filter_by_options', 'toggle_relationship'])
        task = json.loads((self.task / 'task.json').read_text())
        task['review_tag'] = {'tag': 'verified', 'by': 'minh', 'at': '2026-09-26T19:00:00Z'}
        (self.task / 'task.json').write_text(json.dumps(task))
        self.assertEqual(self.queues(), ['done', 'all'])
        self.assertEqual(review_mode.detail('Minh', 'news_0001')['human']['tag'], 'verified')

    def test_urgent_tasks_come_first(self):
        other = self.root / 'Minh' / 'aaa_0000'           # sorts first by key, but has nothing to fix
        _write(other / 'task.json', {'instruction': 'x', 'macros': ['search'],
                                     'review_tag': {'tag': 'verified', 'by': 'minh', 'at': '2026-08-05T01:00:00Z'},
                                     'ai_review': {'reviewed_at': '2026-09-22T12:00:00+00:00'}})
        task = json.loads((self.task / 'task.json').read_text())
        task['macro_ai_review'] = {'flags': ['Recording contradicts the instruction']}
        (self.task / 'task.json').write_text(json.dumps(task))
        review_mode._index.cache_clear()
        self.assertEqual([t['key'] for t in review_mode.index()['tasks']], ['Minh/news_0001', 'Minh/aaa_0000'])

    def test_detail_reports_before_and_now(self):
        self.freeze(macros=['filter_by_options', 'toggle_relationship'])
        d = review_mode.detail('Minh', 'news_0001')
        self.assertEqual([t['macro'] for t in d['before']['tags']], ['filter_by_options', 'toggle_relationship'])
        self.assertTrue(d['changed']['tags'])
        self.assertFalse(d['reviewed'])
        self.assertIsNone(review_mode.detail('..', 'Minh'))

    def outdated(self, **task_fields):
        _write(self.task / 'verifier_runs.json', {'runs': {'gold': {'source': 'gold', 'passed': False}, 'walk': {'source': 'walk', 'passed': True}}})
        _write(self.task / 'verification_walk.json', {'recorded_at': '2026-09-22T15:00:00', 'trajectory': []})
        task = json.loads((self.task / 'task.json').read_text())
        task.update(task_fields)
        (self.task / 'task.json').write_text(json.dumps(task))

    def test_detail_names_who_recorded_each_walk(self):
        self.outdated(verification_walk_by={'by': 'codex-review', 'at': '2026-09-22T15:00:00'},
                      rerecorded_at='2026-08-01T10:00:00', rerecorded_by='Minh')
        d = review_mode.detail('Minh', 'news_0001')
        self.assertEqual((d['walk_by']['by'], d['walk_by']['ai']), ('codex-review', True))
        self.assertEqual(d['rerecorded'], {'by': 'Minh', 'at': '2026-08-01T10:00:00'})

    def test_unstamped_walk_falls_back_to_the_walk_file(self):
        self.outdated()
        self.assertEqual(review_mode.detail('Minh', 'news_0001')['walk_by']['by'], 'unknown')
        _write(self.task / 'verification_walk.json', {'recorded_by': 'Minh', 'recorded_at': '2026-09-27T09:00:00'})
        by = review_mode.detail('Minh', 'news_0001')['walk_by']
        self.assertEqual((by['by'], by['ai']), ('Minh', False))


if __name__ == '__main__':
    unittest.main()
