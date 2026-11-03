"""daynight: the episode log round-trips, the meta agent never sees privileged fields, LLM replies are parsed
defensively, metrics and proposals are computed as documented, every night's command stays inside the experiment dir,
and the whole loop runs on the mock world (no browser, server, GPU or API key)."""
import json

import pytest

from daynight import config as C
from daynight import loop, meta, metrics, propose, train
from daynight.human_sim import LLMSimulatedHuman, MockSimulatedHuman, View
from daynight.schema import Analysis, Episode, Intervention, Label, Outcome, Step, read_episodes, write_jsonl


def _ep(eid="d1_x", ivs=(), passed=False, by_macro=None, macros=("filter_by_slider", "report_information")):
    steps = [Step(i=0, actor="agent", action={"delegate": {"family": "Drag & gesture", "instruction": "slide"}},
                  oracle={"macro": macros[0], "ok": False, "deviation": "wrong_value"}),
             Step(i=1, actor="agent", action={"done": {"text": "42"}}, report="42")]
    return Episode(episode_id=eid, day=1, task_id="x", instruction="Set the price slider to 40 and report the count",
                   site="e-commerce", sites=["e-commerce"], macros=list(macros), agent={"executor": "pooled_v4"},
                   human="simulated", steps=steps, interventions=list(ivs),
                   outcome=Outcome(passed=passed, by_macro=by_macro or {m: False for m in macros}))


def _iv(text="The value is wrong for the filter by slider step.", kind="message", step=0, et="wrong_value"):
    return Intervention(step=step, kind=kind, actor="simulated", text=text,
                        label=Label(error_type=et, macro="filter_by_slider", step=step))


def _cfg(tmp_path, **kw):
    return C.load(C.ROOT / "daynight" / "configs" / "v1_mock.yaml", out=str(tmp_path / "exp"), **kw)


def test_episode_round_trips_through_jsonl(tmp_path):
    ep = _ep(ivs=[_iv(), _iv(kind="takeover", step=1, et="premature_done")])
    write_jsonl(tmp_path / "e.jsonl", [ep])
    back, = read_episodes(tmp_path / "e.jsonl")
    assert back.interventions[1].label.error_type == "premature_done"
    assert back.steps[0].oracle["deviation"] == "wrong_value"
    assert back.takeover_step == 1 and not back.autonomous
    assert json.loads((tmp_path / "e.jsonl").read_text())["takeover_step"] == 1


def test_meta_digest_drops_oracle_and_labels():
    d = json.dumps(meta.digest(_ep(ivs=[_iv()])))
    assert "oracle" not in d and "deviation" not in d and "label" not in d
    assert "The value is wrong" in d                       # the human's own words are what the meta agent reads


def test_rule_meta_reads_the_message():
    a = meta.RuleMetaAgent().analyze(_ep(ivs=[_iv()]))
    assert a.intent == {"error_type": "wrong_value", "macro": "filter_by_slider",
                        "intended": "The value is wrong for the filter by slider step."}
    assert a.failure["step"] == 0
    vague = meta.RuleMetaAgent().analyze(_ep(ivs=[_iv(text="No, not like that.")]))
    assert vague.intent["macro"] == "filter_by_slider"     # the intervened step's family
    ok = meta.RuleMetaAgent().analyze(_ep(passed=True, by_macro={"filter_by_slider": True, "report_information": True}))
    assert ok.score == 1.0 and ok.failure is None


def test_llm_meta_parse_rejects_values_outside_the_taxonomy():
    m = meta.LLMMetaAgent("gemini-3.5-flash")
    ep = _ep(ivs=[_iv()])
    a = m.parse(json.dumps({"failure": {"step": 0, "macro": "not_a_macro", "error_type": "bad"},
                            "intent": {"error_type": "wrong_value", "macro": "filter_by_slider", "intended": "40"},
                            "score": 7, "rationale": "r"}), ep)
    assert a.failure["macro"] is None and a.failure["error_type"] == "other" and a.score == 1.0
    assert a.intent["error_type"] == "wrong_value"
    assert m.parse("not json", ep).source == "rule"         # unusable reply: the rules decide


def test_llm_human_parse_caps_messages_then_takes_over():
    h = LLMSimulatedHuman("gemini-3.5-flash", max_messages=1)
    ep = _ep()
    view = View("e", ep.instruction, ep.macros, None, ep.steps, [], progress={"filter_by_slider": False})
    reply = json.dumps({"decision": "message", "error_type": "wrong_value", "macro": "filter_by_slider", "step": 0,
                        "message": "Set it to 40, not 60."})
    d = h.parse(reply, view)
    assert d.kind == "message" and d.text == "Set it to 40, not 60." and d.label.error_type == "wrong_value"
    view.interventions = [_iv()]
    assert h.parse(reply, view).kind == "takeover"
    assert h.parse("garbage", view).kind == "continue"
    assert "Set the price slider" in h.prompt(view) and "filter_by_slider" in h.prompt(view)


@pytest.mark.parametrize("dev,kind", [(None, "continue"), ("wrong_value", "message")])
def test_mock_human_follows_the_oracle(dev, kind):
    ep = _ep()
    ep.steps[0].oracle["deviation"] = dev
    view = View("e", ep.instruction, ep.macros, None, ep.steps[:1], [])
    import asyncio
    assert asyncio.run(MockSimulatedHuman(vague_share=0).decide(view)).kind == kind


def test_intent_accuracy_against_labels():
    eps = [_ep("a", ivs=[_iv()]), _ep("b", ivs=[_iv()]), _ep("c")]
    an = [Analysis("a", failure={"step": 1, "macro": "filter_by_slider", "error_type": "wrong_value"},
                   intent={"error_type": "wrong_value", "macro": "filter_by_slider"}),
          Analysis("b", failure={"step": 9, "macro": "report_information", "error_type": "wrong_answer"},
                   intent={"error_type": "wrong_answer", "macro": "report_information"}),
          Analysis("c")]
    acc = metrics.intent_accuracy(eps, an)
    assert acc == {"n": 2, "error_type": 0.5, "macro": 0.5, "step": 0.5}


def test_day_metrics_split_autonomous_assisted_takeover():
    both = {"filter_by_slider": True, "report_information": True}
    eps = [_ep("a", passed=True, by_macro=both), _ep("b", ivs=[_iv()], passed=True, by_macro=both),
           _ep("c", ivs=[_iv(kind="takeover")])]
    row = metrics.day_metrics(1, eps)
    assert (row["autonomous_success"], row["assisted_success"], row["takeover_rate"]) == (0.3333, 0.3333, 0.3333)
    assert row["per_macro"]["filter_by_slider"] == {"n": 3, "passed": 2, "pass_rate": 0.6667}


def test_proposals_rank_by_trouble_and_skip_question_answering(tmp_path):
    cfg = _cfg(tmp_path)
    per = {"report_information": {"attempts": 9, "trouble": 9, "weakness": 1.0, "errors": {}},
           "filter_by_slider": {"attempts": 8, "trouble": 4, "weakness": 0.5, "errors": {}},
           "upload_file": {"attempts": 1, "trouble": 1, "weakness": 1.0, "errors": {}},
           "search": {"attempts": 5, "trouble": 0, "weakness": 0.0, "errors": {}}}
    ps = propose.propose({"per_macro": per}, cfg)
    assert [p.macro for p in ps] == ["filter_by_slider", "upload_file"]
    assert all(p.target >= cfg["propose"]["min_per_macro"] for p in ps)


def test_night_commands_stay_inside_the_experiment(tmp_path):
    cfg = _cfg(tmp_path)
    ps = propose.propose({"per_macro": {"filter_by_slider": {"attempts": 2, "trouble": 2, "weakness": 1.0,
                                                             "errors": {}}}}, cfg)
    cmds = propose.night_commands(cfg, 3, ps) + [("train", train.train_command(cfg, 3, "/a/day_2"))]
    exp = str(C.out_dir(cfg))
    gen = next(c for s, c in cmds if s == "generate")
    assert f"MINIWEB_DATAGEN_DIR={exp}/datagen" in gen and "--run-id d3_filter_by_slider" in gen
    assert f"WEBMIX_REPLAY_DIR={exp}/replay" in next(c for s, c in cmds if s == "replay")
    tr = cmds[-1][1]
    assert "--init-adapter /a/day_2" in tr and f"--rows-dir {exp}/rows/day_3" in tr and f"--out {exp}/adapters/day_3" in tr


def test_config_rejects_ports_outside_the_harness_range(tmp_path):
    with pytest.raises(ValueError):
        C.load(None, out=str(tmp_path), agent={**C.DEFAULTS["agent"], "ports": [8200]})


def test_mock_loop_runs_end_to_end_and_refuses_to_overwrite(tmp_path, capsys):
    out = tmp_path / "exp"
    args = ["--config", str(C.ROOT / "daynight" / "configs" / "v1_mock.yaml"), "--out", str(out), "--days", "2",
            "--tasks-per-day", "12"]
    loop.main(args)
    rows = [json.loads(line) for line in (out / "metrics.jsonl").read_text().split("\n") if line.strip()]
    assert [r["day"] for r in rows] == [1, 2, 3]                    # day 3: the last agent's probe only
    assert rows[0]["episodes"] == 12 and rows[0]["probe"]["episodes"] == 30 and rows[2]["episodes"] == 0
    assert rows[1]["agent"] == "dn1"
    assert (out / "adapters" / "day_2" / "skills.json").exists()
    assert (out / "day_1" / "night_plan.sh").read_text().count("-m datagen run") >= 1
    assert json.loads((out / "state.json").read_text())["phase"] == "done"
    with pytest.raises(SystemExit):
        loop.main(args)
