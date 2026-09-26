import unittest

from annotation.verifier_scaffold import _span_indices, inject_qa_leaf, leaf_macros


class MacroTaggingTests(unittest.TestCase):
    def test_ui_span_includes_first_and_last_action(self):
        self.assertEqual(_span_indices([1, 3], 3), [0, 1, 2])
        self.assertEqual(_span_indices([3], 3), [2])

    def test_invalid_spans_do_not_silently_select_different_actions(self):
        for span in ([0, 2], [3, 2], [1, 4], [True, 2], [1, 2, 3], [], None):
            self.assertEqual(_span_indices(span, 3), [])

    def test_repeated_instances_do_not_make_intermediate_qa_terminal(self):
        task = {'macros': ['search', 'search', 'report_information'],
                'macro_instances': ['search', 'search#2', 'report_information'],
                'macro_edges': [{'from': 'search', 'to': 'search#2'},
                                {'from': 'search#2', 'to': 'report_information'}]}
        spec = {'search': {'type': 'qa_answer'}, 'report_information': {'type': 'qa_answer'}}
        result = inject_qa_leaf(spec, task)
        self.assertFalse(result['search']['leaf'])
        self.assertTrue(result['report_information']['leaf'])

    def test_dangling_graph_edge_cannot_disable_terminal_answer(self):
        task = {'macros': ['report_information'],
                'macro_edges': [{'from': 'report_information', 'to': 'removed_macro'}]}
        self.assertEqual(leaf_macros(task), {'report_information'})

    def test_leaf_instance_maps_to_base_verifier(self):
        task = {'macros': ['search', 'search'], 'macro_instances': ['search', 'search#2'],
                'macro_edges': [{'from': 'search', 'to': 'search#2'}]}
        self.assertEqual(leaf_macros(task), {'search'})

    def test_scaffold_collects_both_recorded_search_instances(self):
        from annotation.app import _span_actions
        task = {'macro_spans': {'search': [1, 1], 'search#2': [3, 3]}}
        trajectory = [{'type': 'action', 'action': 'type', 'value': value}
                      for value in ('Seattle', 'unrelated', 'Portland')]
        self.assertEqual([a['value'] for a in _span_actions(task, trajectory, 'search')],
                         ['Seattle', 'Portland'])
