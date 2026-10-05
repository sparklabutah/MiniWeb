"""webmix.augment: recovery (injected, corrected mistake) and chain (two trajectories, one episode) variants."""
import pytest

from webmix import augment as A
from webmix.replay import LEAK, Unsupported, _clean

TASK = {"control": {"kind": "form"}}


def _op(op, seg=0, **kw):
    return {"op": op, "segment": seg, "macro": "create_by_form", **kw}


def _field(css="#name", type_="text"):
    return {"css_path": css, "tag": "input", "type": type_, "box": [100, 100, 200, 20]}


def test_near_miss_changes_numbers_and_words_plausibly():
    assert A.near_miss("2418", "s") != "2418" and len(A.near_miss("2418", "s")) == 4
    miss = A.near_miss("Harbor Inn", "s")
    assert miss != "Harbor Inn" and sorted(miss) == sorted("Harbor Inn")      # two letters swapped
    assert A.near_miss("Q3", "s") is None


def test_inject_mistake_before_a_text_input():
    plan = [_op("click", el={"css_path": "#go", "tag": "a"}, point=[1, 1]),
            _op("input", el=_field(), text="Harbor Inn", select_all=False),
            _op("click", el={"css_path": "#save", "tag": "button"}, point=[5, 5]),
            _op("macro_done"), _op("done", text="Done.", answer=None)]
    out = A.inject_mistake(plan, TASK, "seed")
    assert [o["op"] for o in out] == ["click", "input", "input", "click", "macro_done", "done"]
    wrong, right = out[1], out[2]
    assert wrong["inject"] and wrong["text"] != "Harbor Inn" and wrong["text"] in wrong["what"]
    assert right["recover"] and right["text"] == "Harbor Inn" and right["select_all"]   # replaces the wrong text
    assert out[0].get("aug_prefix") and not out[3].get("aug_prefix")
    assert plan[1].get("select_all") is False                                          # the input plan is untouched


def test_inject_mistake_select_is_chosen_live_and_slider_clicks_elsewhere():
    sel = A.inject_mistake([_op("select", el={"css_path": "#s", "tag": "select"}, text="Open")], TASK, "x")
    assert sel[0]["inject"] and sel[0]["text"] == "" and sel[0]["right"] == "Open"
    rng = {"css_path": "#r", "tag": "input", "type": "range", "box": [100, 50, 200, 20]}
    sl = A.inject_mistake([_op("click", el=rng, point=[260, 60])], TASK, "x")         # at 0.8 of the track
    assert sl[0]["inject"] and sl[0]["point"][0] == pytest.approx(220) and sl[1]["point"] == [260, 60]


def test_no_mistake_where_it_cannot_be_seen_or_fixed():
    for op in (_op("input", el=_field(type_="password"), text="hunter22", select_all=False),
               _op("input", el=_field(type_="date"), text="2026-03-05", select_all=True),
               _op("click", el={"css_path": "#b", "tag": "button"}, point=[1, 1])):
        with pytest.raises(Unsupported):
            A.inject_mistake([op], TASK, "x")
    with pytest.raises(Unsupported):                            # a one-time code differs every session
        A.inject_mistake([_op("input", el=_field(), text="123456", select_all=False)], {"control": {"kind": "reveal"}}, "x")


def test_chains_never_pair_two_changes_of_one_table():
    vote = lambda i: {"check": {"kind": "state", "site": "forums", "scope": ["posts"],  # noqa: E731
                                "expect": [{"collection": "posts", "item_id": i}]}}
    assert A._scope(vote("1")) & A._scope(vote("2"))
    assert not A._scope(vote("1")) & A._scope({"check": {"kind": "request", "path": "/sites/forums/"}})


def test_merged_instruction_must_keep_every_value():
    a, b = "Set the Max Price slider to 600.", 'Then sort by "Price: Low to High".'
    assert A._values(a + " " + b) >= {"600", "Price: Low to High"}


def test_memory_leak_sentences_are_stripped():
    assert _clean(LEAK.sub("", "The previous step was not executed yet. The slider shows 2000.")) == "The slider shows 2000."
