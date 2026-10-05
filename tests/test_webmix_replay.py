"""webmix.replay.build_plan: recorded datagen pixel actions -> browser-use action plan."""
import pytest

from webmix.replay import Unsupported, build_plan


def _el(css, tag="input", **kw):
    return {"css_path": css, "tag": tag, "type": kw.pop("type", "text"), "role": kw.pop("role", ""),
            "accessible_name": kw.pop("name", css), "box": [0, 0, 100, 20], **kw}


def _traj(steps, history=(), macro="create_by_form", history_macro=None):
    """steps / history: [(action, element record extras)]"""
    def split(lst):
        acts, recs = [], []
        for i, (a, rec) in enumerate(lst):
            acts.append({"i": i, "action": a})
            recs.append({"i": i, **rec})
        return acts, recs
    ha, hr = split(history)
    sa, sr = split(steps)
    return ({"macro": macro, "history_macro": history_macro, "history": ha, "steps": sa},
            {"history": hr, "steps": sr})


def ops(plan):
    return [o["op"] for o in plan]


def test_click_select_all_type_merges_into_one_input():
    f = _el("#title")
    t, e = _traj([({"type": "click", "x": 5, "y": 5}, {"element": f}),
                  ({"type": "key", "key": "Control+a"}, {"element": f}),
                  ({"type": "type", "text": "Hello"}, {"element": f}),
                  ({"type": "type", "text": " world"}, {"element": f}),
                  ({"type": "key", "key": "Enter"}, {"element": f})])
    plan = build_plan(t, e)
    assert ops(plan) == ["input", "key", "macro_done", "done"]
    assert plan[0]["text"] == "Hello world" and plan[0]["select_all"] is True
    assert plan[1]["key"] == "Enter"


def test_select_clicks_and_keys_become_select_dropdown_with_chosen_label():
    s = _el("#difficulty", tag="select", type="")
    t, e = _traj([({"type": "click", "x": 5, "y": 5}, {"element": s, "select": {"before": {"label": "Easy"}, "after": None}}),
                  ({"type": "key", "key": "ArrowDown"}, {"element": s, "select": {"after": {"label": "Medium"}}}),
                  ({"type": "key", "key": "Enter"}, {"element": s, "select": {"after": {"label": "Medium"}}}),
                  ({"type": "click", "x": 50, "y": 90}, {"element": _el("#go", tag="button", type="submit")})])
    plan = build_plan(t, e)
    assert ops(plan) == ["select", "click", "macro_done", "done"]
    assert plan[0]["text"] == "Medium"


def test_mid_chain_gets_a_macro_done_per_segment_and_answer_ends_in_done():
    t, e = _traj([({"type": "scroll", "x": 1, "y": 1, "dx": 0, "dy": 400}, {"scroll": {"window": [0, 0]}}),
                  ({"type": "answer", "text": "42"}, {})],
                 history=[({"type": "click", "x": 5, "y": 5}, {"element": _el("#sort", tag="button")})],
                 macro="report_information", history_macro="sort_by_form")
    plan = build_plan(t, e)
    assert ops(plan) == ["click", "macro_done", "scroll", "macro_done", "done"]
    assert [o["macro"] for o in plan] == ["sort_by_form", "sort_by_form", "report_information",
                                          "report_information", "report_information"]
    assert plan[-1]["text"] == "42" and plan[-1]["answer"] == "42"


def test_answer_read_off_the_start_page():
    t, e = _traj([({"type": "answer", "text": "7"}, {})], macro="count_entries")
    assert ops(build_plan(t, e)) == ["macro_done", "done"]


def test_navigation_targets_are_rebased_paths():
    t, e = _traj([({"type": "new_tab", "url": "http://localhost:8301/sites/email/"}, {}),
                  ({"type": "switch_tab", "index": 0}, {})], macro="reveal_by_2fa")
    plan = build_plan(t, e)
    assert plan[0] == {**plan[0], "op": "navigate", "url": "/sites/email/", "new_tab": True}
    assert plan[1]["op"] == "switch" and plan[1]["index"] == 0


def test_click_on_a_field_without_typing_stays_a_click():
    f = _el("#q")
    t, e = _traj([({"type": "click", "x": 5, "y": 5}, {"element": f}),
                  ({"type": "key", "key": "ArrowDown"}, {"element": f})])
    assert ops(build_plan(t, e)) == ["click", "key", "macro_done", "done"]


def test_pre_finder_upload_is_unsupported():
    t, e = _traj([({"type": "upload", "x": 1, "y": 1, "file": "Desktop/a.png"}, {"element": _el("#f", type="file")})])
    with pytest.raises(Unsupported):
        build_plan(t, e)
