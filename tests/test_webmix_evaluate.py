"""webmix.evaluate routing: the planner-routed arm switches adapters by the planner's plan at each macro_done."""
import asyncio
import json
from types import SimpleNamespace

from webmix.evaluate import Planned


class _Act:
    def __init__(self, d):
        self.d = d

    def model_dump(self, exclude_none=True):
        return self.d

    @classmethod
    def model_validate(cls, d):
        return cls(d)


def _llm(script):
    """A stand-in ChatOpenAI whose replies are the scripted action lists."""
    replies = iter(script)

    async def ainvoke(messages, output_format=None, **kw):
        return SimpleNamespace(completion=SimpleNamespace(action=[_Act(a) for a in next(replies)]))
    return SimpleNamespace(model=None, ainvoke=ainvoke)


def _planner(plans, seen):
    replies = iter(plans)

    async def create(model=None, messages=None, **kw):
        seen.append(messages[1]["content"][0]["text"])
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({"plan": next(replies)})))])
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


def test_planned_arm_follows_the_plan_and_replans_after_macro_done():
    llm = _llm([[{"click": {}}], [{"macro_done": {}}], [{"input": {}}], [{"macro_done": {}}], [{"done": {}}]])
    bs = SimpleNamespace(take_screenshot=lambda: asyncio.sleep(0, result=b"png"))
    r = Planned(llm, bs, "Filter by X, then search Y", "http://x/v1", "planner", {"select", "rest"}, "base")
    seen = []
    r.client = _planner([["Discrete selection", "Text entry"], ["Text entry"], []], seen)

    async def run():
        for _ in range(5):
            await llm.ainvoke([])
    asyncio.run(run())
    assert [t["model"] for t in r.trace] == ["select", "select", "rest", "rest", "base"]
    assert r.done == ["Discrete selection", "Text entry"]
    assert "Steps finished: none" in seen[0] and "Steps finished: Discrete selection" in seen[1]


def test_planned_arm_falls_back_when_the_adapter_is_not_loaded():
    llm = _llm([[{"drag": {}}]])
    bs = SimpleNamespace(take_screenshot=lambda: asyncio.sleep(0, result=b"png"))
    r = Planned(llm, bs, "Drag it", "http://x/v1", "planner", {"select"}, "pooled")
    r.client = _planner([["Drag & gesture"]], [])
    asyncio.run(llm.ainvoke([]))
    assert r.trace[0]["model"] == "pooled" and r.trace[0]["family"] == "Drag & gesture"


def test_reasoning_goes_to_its_specialist_else_the_base_model():
    from webmix.evaluate import arm_models
    task = {"macro": "report_information", "start": {"prefix": {"macro": "filter_by_dropdown"}}}
    assert arm_models("oracle", task, "base", {"select", "rest"}) == ["select", "base"]
    assert arm_models("oracle", task, "base", {"select", "reasoning"}) == ["select", "reasoning"]
    llm = _llm([[{"click": {}}]])
    bs = SimpleNamespace(take_screenshot=lambda: asyncio.sleep(0, result=b"png"))
    r = Planned(llm, bs, "How many?", "http://x/v1", "planner", {"select", "rest"}, "pooled_v4", "base")
    r.client = _planner([["Reasoning base"]], [])
    asyncio.run(llm.ainvoke([]))
    assert r.trace[0]["model"] == "base"                  # not the pooled fallback


def test_router_gates_a_premature_done_into_macro_done():
    from webmix.evaluate import Routed
    llm = _llm([[{"click": {}}], [{"done": {"text": "ok"}}], [{"input": {}}], [{"done": {"text": "ok"}}]])
    r = Routed(llm, ["select", "rest"], gate=True)

    async def run():
        return [await llm.ainvoke([]) for _ in range(4)]
    outs = asyncio.run(run())
    assert "macro_done" in outs[1].completion.action[0].model_dump() and r.trace[1].get("gated")
    assert [t["model"] for t in r.trace] == ["select", "select", "rest", "rest"]
    assert "done" in outs[3].completion.action[0].model_dump()        # the last planned macro may finish the task
    ungated = Routed(_llm([[{"done": {}}]]), ["select", "rest"])
    assert ungated.gates == 0


def test_gate_blocks_done_on_an_untouched_step_but_not_a_reasoning_answer():
    from webmix.evaluate import premature
    assert premature(2, 3, "Form transaction")                 # steps planned after the current one
    assert premature(1, 0, "Form transaction")                 # macro_done, re-plan [FORM], then done at once
    assert not premature(1, 2, "Form transaction")             # the last step was acted on
    assert not premature(1, 0, "Reasoning base")               # the answer is the reasoning step's action
    assert not premature(0, 0, None)


def test_planned_router_gates_macro_done_then_done():
    llm = _llm([[{"click": {}}], [{"macro_done": {}}], [{"done": {"text": "x"}}], [{"click": {}}], [{"done": {"text": "y"}}]])
    bs = SimpleNamespace(take_screenshot=lambda: asyncio.sleep(0, result=b"png"))
    r = Planned(llm, bs, "Filter, then fill the form", "http://x/v1", "planner", {"select", "rest"}, "pooled_v4", "base",
                gate=True)
    r.client = _planner([["Discrete selection", "Form transaction"], ["Form transaction"], ["Form transaction"]], [])

    async def run():
        return [await llm.ainvoke([]) for _ in range(5)]
    outs = asyncio.run(run())
    assert r.trace[2].get("gated") and "macro_done" in outs[2].completion.action[0].model_dump()
    assert "done" in outs[4].completion.action[0].model_dump()   # after acting on the FORM step, done is allowed


def test_gated_done_leaves_the_specialist_a_note():
    from webmix import harness as H
    llm = _llm([[{"click": {}}], [{"macro_done": {}}], [{"done": {"text": "x"}}]])
    bs = SimpleNamespace(take_screenshot=lambda: asyncio.sleep(0, result=b"png"))
    r = Planned(llm, bs, "Filter, then fill the form", "http://x/v1", "planner", {"select", "rest"}, "pooled_v4", "base",
                gate=True, note=True)
    r.client = _planner([["Discrete selection", "Form transaction"], ["Form transaction"]], [])

    async def run():
        for _ in range(3):
            await llm.ainvoke([])
    asyncio.run(run())
    note = H.ROUTER_NOTES.pop(id(bs))
    assert "not finished" in note and "Form transaction" in note
