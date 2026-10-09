"""miniwebagent.evaluate routing: the oracle router switches adapters at each macro_done and gates a premature done; the
planner agent's specialist choice (sub_model) falls back when an adapter is not loaded."""
import asyncio
from types import SimpleNamespace


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


def test_reasoning_goes_to_its_specialist_else_the_base_model():
    from miniwebagent.evaluate import arm_models, sub_model
    task = {"macro": "report_information", "start": {"prefix": {"macro": "filter_by_dropdown"}}}
    assert arm_models("oracle", task, "base", {"select", "rest"}) == ["select", "base"]
    assert arm_models("oracle", task, "base", {"select", "reasoning"}) == ["select", "reasoning"]
    args = SimpleNamespace(adapters={"select", "rest"}, fallback="pooled_v4", base_name="base", reasoning_to_fallback=False)
    assert sub_model("Reasoning base", args) == "base"                 # not the pooled fallback
    assert sub_model("Reasoning base", SimpleNamespace(**{**vars(args), "adapters": {"reasoning"}})) == "reasoning"
    assert sub_model("Reasoning base", SimpleNamespace(**{**vars(args), "reasoning_to_fallback": True})) == "pooled_v4"


def test_planner_agent_specialist_falls_back_when_the_adapter_is_not_loaded():
    from miniwebagent.evaluate import sub_model
    args = SimpleNamespace(adapters={"select"}, fallback="pooled_v4", base_name="base", reasoning_to_fallback=False)
    assert sub_model("Discrete selection", args) == "select"
    assert sub_model("Drag & gesture", args) == "pooled_v4"
    assert sub_model("Drag & gesture", SimpleNamespace(**{**vars(args), "fallback": None})) == "base"


def test_router_gates_a_premature_done_into_macro_done():
    from miniwebagent.evaluate import Routed
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
    from miniwebagent.evaluate import premature
    assert premature(2, 3, "Form transaction")                 # steps planned after the current one
    assert premature(1, 0, "Form transaction")                 # macro_done, re-plan [FORM], then done at once
    assert not premature(1, 2, "Form transaction")             # the last step was acted on
    assert not premature(1, 0, "Reasoning base")               # the answer is the reasoning step's action
    assert not premature(0, 0, None)


def test_gated_done_leaves_the_specialist_a_note():
    from miniwebagent import harness as H
    from miniwebagent.evaluate import Routed
    llm = _llm([[{"click": {}}], [{"done": {"text": "x"}}]])
    bs = SimpleNamespace()
    r = Routed(llm, ["select", "rest"], gate=True, fams=["Discrete selection", "Form transaction"], bs=bs, note=True)

    async def run():
        for _ in range(2):
            await llm.ainvoke([])
    asyncio.run(run())
    assert r.trace[1].get("gated")
    note = H.ROUTER_NOTES.pop(id(bs))
    assert "not finished" in note and "Form transaction" in note
