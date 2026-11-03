"""The real human's interface (v1): the agent's browser, headful, plus this terminal.

After every agent step the terminal shows what the agent did and waits for one line:

    <Enter>          let the agent continue
    m <text>         send the agent a corrective message
    t                take over: the agent stops, and you finish the task yourself in the same browser window
                     (the page recorder that MiniWeb injects into every site logs your actions)

During a takeover, type `done [answer]` when the task is finished (the answer only for a task that asks a question).
After a message or a takeover you are asked for the error type (optional, <Enter> skips): a label for RQ1.

Try it without a browser on the mock world:

    python -m daynight.day --config daynight/configs/v1_mock.yaml --day 1 --human real --tasks 2
"""
from __future__ import annotations

import asyncio

from daynight.human_sim import Decision, Human, _step_line
from daynight.schema import ERROR_TYPES, Label


async def _ask(prompt):
    return (await asyncio.to_thread(input, prompt)).strip()


async def ask_label(view, step):
    """-> Label or None: the error type, picked by number."""
    menu = "  ".join(f"{i}={t}" for i, t in enumerate(ERROR_TYPES, 1))
    raw = await _ask(f"  error type? {menu}  (<Enter> skips): ")
    if not raw.isdigit() or not 1 <= int(raw) <= len(ERROR_TYPES):
        return None
    macros = view.macros
    m = None
    if len(macros) > 1:
        raw_m = await _ask("  which part? " + "  ".join(f"{i}={x}" for i, x in enumerate(macros, 1)) + "  (<Enter> skips): ")
        m = macros[int(raw_m) - 1] if raw_m.isdigit() and 1 <= int(raw_m) <= len(macros) else None
    elif macros:
        m = macros[0]
    return Label(error_type=ERROR_TYPES[int(raw) - 1], macro=m, step=step)


class TerminalHuman(Human):
    actor = "real"
    can_act = True

    async def decide(self, view):
        if not view.steps:
            return Decision()
        if len(view.steps) == 1 or not getattr(self, "_shown", None) == view.episode_id:
            self._shown = view.episode_id
            print(f"\n=== {view.episode_id}\nTask: {view.instruction}\nParts: {', '.join(view.macros)}", flush=True)
        print(_step_line(view.steps[-1]), flush=True)
        if view.done:
            print("  the agent says it is done" + (f": {view.answer}" if view.answer else ""), flush=True)
        while True:
            raw = await _ask("  [Enter]=continue  m <text>=message  t=take over > ")
            if not raw:
                return Decision()
            if raw == "t":
                return Decision("takeover", "", await ask_label(view, view.steps[-1].i))
            if raw.startswith("m ") and raw[2:].strip():
                return Decision("message", raw[2:].strip(), await ask_label(view, view.steps[-1].i))
            print("  ? type nothing, `m <text>` or `t`", flush=True)

    async def take_over(self, view):
        print("  You have the browser. Finish the task there, then type `done [answer]` here.", flush=True)
        while True:
            raw = await _ask("  takeover > ")
            if raw == "done" or raw.startswith("done "):
                answer = raw[5:].strip() or None
                note = await _ask("  a note on what the agent got wrong (optional): ")
                return answer, note, None
