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
import subprocess
import urllib.request
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


def generate_rubric(task):
    """Generate a rubric from a task's macros and instruction.

    The rubric is a checklist that the judge uses to evaluate the agent.
    """
    instruction = task.get("instruction", "")
    macros = task.get("macros", [])
    expected = task.get("expected_answer", "")
    difficulty = task.get("difficulty", "easy")

    criteria = []

    for macro in macros:
        verb = macro.split("_")[0]
        modality = "_".join(macro.split("_")[1:]) if "_" in macro else ""

        if verb in ("navigate", "browse"):
            criteria.append(f"Agent navigated to the correct page ({modality.replace('_', ' ')})")
        elif verb in ("search",):
            criteria.append(f"Agent performed a search using the correct method ({modality.replace('_', ' ')})")
        elif verb in ("filter",):
            criteria.append(f"Agent applied the correct filter ({modality.replace('_', ' ')})")
        elif verb in ("sort",):
            criteria.append(f"Agent sorted results correctly ({modality.replace('_', ' ')})")
        elif verb in ("extract", "compute", "count", "compare", "verify", "calculate"):
            criteria.append(f"Agent extracted/computed the correct value")
        elif verb in ("create", "submit", "post", "message", "register", "apply", "book"):
            criteria.append(f"Agent created/submitted the required content ({modality.replace('_', ' ')})")
        elif verb in ("edit", "update", "configure"):
            criteria.append(f"Agent modified the correct item ({modality.replace('_', ' ')})")
        elif verb in ("delete", "cancel"):
            criteria.append(f"Agent deleted/cancelled the correct item")
        elif verb in ("authenticate", "login"):
            criteria.append(f"Agent logged in successfully")
        elif verb in ("share", "save", "follow", "subscribe", "react", "rate", "star", "bookmark"):
            criteria.append(f"Agent performed the social action: {verb} ({modality.replace('_', ' ')})")
        elif verb in ("pay", "checkout", "add", "redeem"):
            criteria.append(f"Agent completed the transaction: {verb}")
        elif verb in ("upload", "export", "play"):
            criteria.append(f"Agent performed media action: {verb} ({modality.replace('_', ' ')})")
        elif verb in ("select",):
            criteria.append(f"Agent selected the correct option ({modality.replace('_', ' ')})")
        elif verb == "tab":
            criteria.append(f"Agent switched to the correct tab/site")
        else:
            criteria.append(f"Agent performed: {macro}")

    if expected and expected.lower() not in ("done", ""):
        criteria.append(f"Agent's answer matches expected: \"{expected}\"")
    elif expected and expected.lower() == "done":
        criteria.append("Agent completed the action (no specific answer required, just confirmation)")

    rubric = "Checklist — ALL must be satisfied:\n"
    for i, c in enumerate(criteria, 1):
        rubric += f"{i}. {c}\n"

    return rubric


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


def generate_all_rubrics(site_id):
    """Generate rubrics for all tasks in a site's tasks.json."""
    tasks_file = Path(__file__).resolve().parent.parent / "sites" / site_id / "tasks.json"
    if not tasks_file.exists():
        return []

    tasks = json.loads(tasks_file.read_text())
    for task in tasks:
        task["rubric"] = generate_rubric(task)
    return tasks
