"""Macro judge: target-identity replies, best-of-3 voting, and the harness fallback."""
import json
import unittest
from unittest.mock import patch

from evaluation import macro_judge


def reply(verdict, agent="POST /sites/x/item/12/like", ref="POST /sites/x/item/12/like", extra="none"):
    return json.dumps({"agent_target": agent, "reference_target": ref, "extra_targets": extra,
                       "verdict": verdict, "why": f"{verdict} because"})


class MacroJudgeTests(unittest.TestCase):
    def test_targets_are_kept_with_the_verdict(self):
        with patch("app.llm.call_llm", side_effect=[reply("fail", agent="product_id=15", ref="product_id=58")] * 2):
            out = macro_judge.judge_instance({"x": 1})
        self.assertFalse(out["passed"])
        self.assertEqual((out["agent_target"], out["reference_target"], out["votes"]), ("product_id=15", "product_id=58", "0/2"))

    def test_split_is_settled_by_a_third_vote(self):
        with patch("app.llm.call_llm", side_effect=[reply("pass"), reply("fail"), reply("pass")]) as llm:
            out = macro_judge.judge_instance({"x": 1})
        self.assertTrue(out["passed"]); self.assertEqual(out["votes"], "2/3"); self.assertEqual(llm.call_count, 3)

    def test_prompt_asks_for_targets_before_the_verdict(self):
        self.assertIn('"agent_target"', macro_judge.SYSTEM)
        self.assertLess(macro_judge.SYSTEM.index('"agent_target"'), macro_judge.SYSTEM.index('"verdict"'))


class HarnessGraderTests(unittest.TestCase):
    def test_judge_unavailable_falls_back_to_the_verifier(self):
        from evaluation import run_agent_verify
        down = {"passed": False, "instances": {"a": {"passed": False, "why": "judge unavailable"}}}
        with patch("evaluation.macro_judge.grade", return_value=down):
            self.assertIsNone(run_agent_verify.judge_episode("Minh/x", [], "", None))
        ok = {"passed": True, "instances": {"a": {"passed": True, "why": "ok"}}}
        with patch("evaluation.macro_judge.grade", return_value=ok):
            self.assertTrue(run_agent_verify.judge_episode("Minh/x", [], "", None)["passed"])


if __name__ == "__main__":
    unittest.main()
