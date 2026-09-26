import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from annotation import macro_browser


class MacroBrowserTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        task_dir = root / 'Minh' / 'news_0001'
        task_dir.mkdir(parents=True)
        (task_dir / 'task.json').write_text(json.dumps({
            'instruction': 'Find the latest Weather article and save it.',
            'macros': ['navigate_by_route', 'navigate_by_route', 'toggle_relationship'],
            'macro_operations': {'navigate_by_route#2': 'extremum'},
            'macro_spans': {'navigate_by_route': [1, 1], 'navigate_by_route#2': [2, 3], 'toggle_relationship': [0, 9]}}))
        (task_dir / 'trajectory.json').write_text(json.dumps([
            {'type': 'action', 'action': 'click', 'target': "link 'Weather'"},
            {'type': 'observation', 'screenshot': 'screenshots/step_000.png'},
            {'type': 'action', 'action': 'scroll', 'target': 'page'},
            {'type': 'action', 'action': 'click', 'target': "link 'Storm'"},
            {'type': 'observation', 'axtree_json': json.dumps({'role': 'heading', 'text': 'Storm warning'})}]))
        (root / '.trash' / 'old_0002').mkdir(parents=True)
        (root / '.trash' / 'old_0002' / 'task.json').write_text(json.dumps({'macros': ['search']}))
        self.patch = mock.patch.object(macro_browser, 'ANNOTATIONS_DIR', root)
        self.patch.start()
        macro_browser._index.cache_clear()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_repeated_instances_are_separate_occurrences(self):
        idx = macro_browser.index()
        self.assertEqual([o['instance'] for o in idx['macros']['navigate_by_route']],
                         ['navigate_by_route', 'navigate_by_route#2'])
        self.assertEqual(idx['macros']['navigate_by_route'][1]['op'], 'extremum')
        self.assertNotIn('search', idx['macros'])            # hidden .trash tasks are skipped

    def test_invalid_span_is_reported_as_missing(self):
        tags = {t['instance']: t for t in macro_browser.index()['tasks'][0]['tags']}
        self.assertIsNone(tags['toggle_relationship']['span'])

    def test_actions_are_one_based_with_frames_or_outline(self):
        detail = macro_browser.task_detail('Minh', 'news_0001')
        self.assertEqual([a['index'] for a in detail['actions']], [1, 2, 3])
        self.assertEqual(detail['actions'][0]['frame'], 'screenshots/step_000.png')
        # an action without its own screenshot keeps the last one seen
        self.assertEqual(detail['actions'][1]['frame'], 'screenshots/step_000.png')

    def test_path_traversal_is_rejected(self):
        self.assertIsNone(macro_browser.task_detail('..', 'Minh'))


if __name__ == '__main__':
    unittest.main()
