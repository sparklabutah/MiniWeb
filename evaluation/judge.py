"""LLM-as-Judge evaluator for MiniWeb browser agent tasks.

Given the task instruction, agent trajectory, expected answer, and a rubric,
calls GPT-5.5 to score whether the agent completed the task correctly.

Usage:
    from evaluation.judge import judge_task

    result = judge_task(
        instruction="Filter banking transactions by Groceries...",
        trajectory=[...],  # browser-use action trace
        expected_answer="5",
        rubric="...",
        agent_answer="5",
    )
    # result = {"pass": True, "score": 1.0, "reasoning": "..."}
"""

import json
import os
from pathlib import Path





_JUDGE_PROMPT = """You are a judge evaluating whether a browser agent correctly completed a web task.

## Task Instruction
{instruction}

## Expected Answer
{expected_answer}

## Rubric
{rubric}

## Agent's Final Answer
{agent_answer}

## Agent's Action Trace
{trajectory}

## Scoring Rules
1. Compare the agent's answer against the expected answer. Minor formatting differences (e.g., "$5" vs "5", extra whitespace) are acceptable.
2. Check each rubric criterion — did the agent's actions satisfy it?
3. If the task requires a specific answer, the answer must be correct (or a reasonable equivalent).
4. If the task requires an action (e.g., "create a post"), the trace must show the action was performed.

## Output
Respond with ONLY a JSON object:
{{"pass": true/false, "score": 0.0-1.0, "reasoning": "brief explanation"}}
"""


def format_trajectory(trajectory):
    """Format browser-use trajectory for the judge prompt."""
    if not trajectory:
        return "(no actions recorded)"

    lines = []
    for i, step in enumerate(trajectory):
        if isinstance(step, dict):
            action = step.get("action", step.get("type", ""))
            target = step.get("target", step.get("element", ""))
            text = step.get("text", step.get("value", ""))
            url = step.get("url", "")
            if action:
                detail = f"{action}"
                if target:
                    detail += f" on {target}"
                if text:
                    detail += f': "{text[:50]}"'
                if url:
                    detail += f" [{url}]"
                lines.append(f"{i+1}. {detail}")
        elif isinstance(step, str):
            lines.append(f"{i+1}. {step}")

    return "\n".join(lines) if lines else "(no actions recorded)"




def _parse_json_response(text):
    """Extract JSON from an LLM response (handles ```json``` wrappers)."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()
    return json.loads(text)


def _call_shared_llm(prompt, model=None):
    """Judge via the shared model-routing helper (None -> default model)."""
    import sys
    root = str(Path(__file__).resolve().parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    from app.llm import call_llm
    text = call_llm(prompt, max_tokens=1000, temperature=0.0, json_mode=True,
                    model=model)
    if not text:
        raise RuntimeError(f"LLM call failed (model={model or 'default'})")
    return text


def judge_task(instruction, trajectory, expected_answer, rubric,
               agent_answer="", model="auto"):
    """Call LLM to judge whether the agent completed the task.

    Returns: {"pass": bool, "score": float, "reasoning": str}

    model may be any name in app.llm.SUPPORTED_MODELS — it is routed to the
    right provider automatically. "auto" (or the legacy "claude-cli") uses
    the default model.
    """
    traj_text = format_trajectory(trajectory)

    prompt = _JUDGE_PROMPT.format(
        instruction=instruction,
        expected_answer=expected_answer or "(no specific answer expected)",
        rubric=rubric,
        agent_answer=agent_answer or "(agent did not provide an answer)",
        trajectory=traj_text[:3000],
    )

    try:
        # "auto"/"claude-cli" (legacy alias) -> default model
        routed = None if model in ("auto", "claude-cli") else model
        text = _call_shared_llm(prompt, model=routed)

        verdict = _parse_json_response(text)
        return {
            "pass": bool(verdict.get("pass", False)),
            "score": float(verdict.get("score", 0.0)),
            "reasoning": verdict.get("reasoning", ""),
        }
    except Exception as e:
        return {"pass": False, "score": 0.0, "reasoning": f"Judge error: {e}"}


