"""The planner as a browser-use Agent (user, 2026-09-30: "The planner has to go through sth like browser use, or browser
use itself").

The screenshot-only planner (webmix.planner.plan_steps) planned blind: no URL, no element list, no page text, and no
say in when the task ends. On WebArena that cost 16 of the 18 tasks base solved and it did not: steps for controls
that do not exist, wandering, answers written into the plan, and tasks solved mid-way then undone by later steps
(the router had no stop decision and took the last step's message as the answer).

Here the planner is itself a browser-use Agent on the live session, so every planning turn sees what a specialist
sees (URL, tabs, the interactive elements with their options, the screenshot). It cannot click, type or navigate: its
acting tool is `delegate(family, instruction)`, which runs that family's specialist as its own episode on the same
browser (the one-step episodes the specialists were trained on, with the whole task as background) and returns what
the specialist did and saw. Results land in the planner's history, so the loop is closed by construction; the planner
ends the task with `done`, whose text is the answer. It may also scroll to read.

Budget: specialist actions (the steps that touch the site) share the single agent's 40; each delegation gets at most
`sub_cap` of them; planner turns are capped separately (`max_turns`).
"""
from typing import Literal

from browser_use import Agent, BrowserSession, Tools
from browser_use.agent.views import ActionResult
from pydantic import BaseModel, Field

from webmix import harness as H
from webmix.planner import FAMILY_DEFS

FAMILIES = tuple(FAMILY_DEFS)
PLANNER_KEEPS = {"done", "scroll"}          # look-only besides delegate; every site-changing action is a specialist's
STEP_TIMEOUT = 3600                         # a planner turn contains a whole specialist episode (browser-use's 180 s default)


class DelegateAction(BaseModel):
    family: Literal[FAMILIES] = Field(description="The kind of step: picks the specialist that does it")
    instruction: str = Field(description="One step, said exactly: the control to use (as named on the page) and the "
                                         "names or values from the task")


PLANNER_PROMPT = (
    "<planner_role>\nYou lead a team of specialists. You do not click, type or navigate yourself: every step that "
    "touches the website is done by a specialist that you call with the delegate action. Each specialist does one "
    "kind of step (its family):\n"
    + "\n".join(f"- {f}: {d}" for f, d in FAMILY_DEFS.items())
    + "\n\nHow to work:\n"
      "1. Look at the current page (its URL, its interactive elements and the screenshot) and choose the next single "
      "step toward the task. Delegate it to its family with one short instruction that names the exact controls and "
      "values you see on the page. One family per step.\n"
      "2. The delegate result says what the specialist did and saw. Check it against the page now shown. If a step "
      "failed or its control does not exist, reach the goal another way; do not repeat a failed step.\n"
      "3. Use only controls the page shows or that its menus and links lead to. Never guess an answer before it has "
      "been read from the page.\n"
      "4. Call done as soon as the task is complete. If the task asks for information, done's text is the answer "
      "(from what the specialists reported or what the page shows; you may scroll to read). If the task asks to change "
      "something or to show a page, call done once the change is made or the page is shown, without leaving it.\n"
      "5. Specialists have a limited number of steps in total; do not spend them on steps the task does not need.\n"
      "</planner_role>")


# v2 (2026-09-30 22:00, from the v1 smoke traces): specialists say "finished" after steps that changed nothing (the
# planner then re-delegated the same step), and the planner answered "most clicks" from a partial, unsorted list.
PLANNER_PROMPT_V2 = PLANNER_PROMPT.replace(
    "do not repeat a failed step.\n",
    "do not repeat a failed step. A specialist may say it finished when it did not: trust the page, and the report's "
    "note on whether the page changed.\n").replace(
    "Never guess an answer before it has been read from the page.\n",
    "Never guess an answer before it has been read from the page. To find the largest, smallest, newest or oldest "
    "item, sort or filter the list rather than reading part of it.\n")


# v7 (2026-10-02, from the WebVoyager / Online-Mind2Web failure study; developed on MiniWeb only): constraints were
# dropped between delegations, false "done" reports were believed, answers were reported from pages not on screen,
# "report" steps were delegated instead of done, and a login was guessed on a live site.
PLANNER_PROMPT_V7 = PLANNER_PROMPT_V2.replace(
    "</planner_role>",
    "6. Before the first delegation, write in your memory a checklist of everything the task asks for (each name, "
    "value, filter, date, sort order, and what the final result must be). Keep it updated as items are done.\n"
    "7. Every delegate result ends with a page check: what actually changed on the page (URL, field values, checked "
    "or selected options). Believe the page check over the specialist's own words. If it shows no change, the step did "
    "not happen: do it another way.\n"
    "8. When steps stop making progress, change strategy instead of repeating: use the site's search box with the "
    "exact query, its filter and sort controls, a different link or menu, or go back.\n"
    "9. Before calling done, check every checklist item against the page (URL, fields, selected filters, the results "
    "shown). Fix anything missing first. For an information task, scroll so the answer is visible on screen, then call "
    "done yourself with the answer; never delegate a step only to report.\n"
    "10. Never invent credentials, personal details or payment details. If the task needs a login or data it did not "
    "give, do what is possible without it and say so in done.\n"
    "</planner_role>")
STALL_WARN, STALL_FORCE = 3, 6     # v7: delegations in a row without progress before a warning / a forced done
SPEC_STALL = 3                      # v7: a specialist is stopped after this many actions in a row that changed nothing


def _norm(s):
    return " ".join("".join(c.lower() if c.isalnum() else " " for c in s).split())


class PlannerTools(Tools):
    """The planner's tools: browser-use caps every action at 180 s (BROWSER_USE_ACTION_TIMEOUT_S), but delegate holds a
    whole specialist episode (2026-09-30: 7 delegations killed mid-episode on a busy GPU)."""

    async def act(self, *args, action_timeout=None, **kwargs):
        return await super().act(*args, action_timeout=STEP_TIMEOUT, **kwargs)


# v3: v2 with the planner in browser-use's flash format (memory + action), the specialists' format: the long
# evaluation/memory/next-goal output degenerated into whitespace in 25 planner turns (invalid JSON).
# v4 (dev-set v2 failures): specialists given the whole task overreach (a "click Sign In" step searched and filtered;
# a "open the translator" step translated and sent the message, wrongly) and the planner believed the reports; the
# planner's instructions already carry the names and values. So specialists get only their instruction. And a
# planner that keeps delegating after the specialist budget is gone (up to 8 times) is stopped.
VERSIONS = {
    "v1": dict(prompt=PLANNER_PROMPT, flash=False, page_check=False, overall=True, stop_when_spent=False),
    "v2": dict(prompt=PLANNER_PROMPT_V2, flash=False, page_check=True, overall=True, stop_when_spent=False),
    "v3": dict(prompt=PLANNER_PROMPT_V2, flash=True, page_check=True, overall=True, stop_when_spent=False),
    "v4": dict(prompt=PLANNER_PROMPT_V2, flash=True, page_check=True, overall=False, stop_when_spent=True),
    "v4n": dict(prompt=PLANNER_PROMPT_V2, flash=False, page_check=True, overall=False, stop_when_spent=True),
    # v5: the shared budget counts site actions only. 36% of v4's specialist steps were bookkeeping (a step whose only
    # action is done or macro_done): ~1.5 per delegation, ~8-12 of the 40, where the single agent pays one done.
    "v5": dict(prompt=PLANNER_PROMPT_V2, flash=True, page_check=True, overall=False, stop_when_spent=True,
               count_site_actions=True),
    # v6: with specialists doing only their step (v4), a 3-4 macro task needs ~10+ delegations; 9 of v5's 16 failed
    # long dev tasks used all 12 planner turns, several repeating one delegation (a Reasoning step 7 times). Planner
    # turns do not touch the site (the budget stays 40 site actions): 25 turns, and a delegation identical to the
    # previous one on an unchanged page is refused.
    "v6": dict(prompt=PLANNER_PROMPT_V2, flash=True, page_check=True, overall=False, stop_when_spent=True,
               count_site_actions=True, max_turns=25, repeat_guard=True),
    # v6c: v6 with the whole task as specialist background again (v1-v3 had it). Held-out interim: v5 22/47 vs v1
    # 26/47 on the same tasks; on dev v3 (context) = v4 (none) = 25. Decided on a second dev set (dev2), not held-out.
    "v6c": dict(prompt=PLANNER_PROMPT_V2, flash=True, page_check=True, overall=True, stop_when_spent=True,
                count_site_actions=True, max_turns=25, repeat_guard=True),
    # v7 (2026-10-02, user: "do all those fixes and test on MiniWeb only first ... call those v7"): v6 plus
    #  A budget fix: a specialist with k site actions left runs k+1 steps (browser-use forces done on the last step, so
    #    with 1 left it used to run 0 actions, the budget never reached 0 and the planner looped to its turn cap);
    #  B the planner's own observations go into the live-web trajectory (om2w.trajectory), and it scrolls the answer
    #    into view before done (prompt);
    #  C progress control: a step already tried on the same page state is refused (catches A-B-A-B cycles, not only
    #    an exact repeat), a warning after STALL_WARN delegations without progress, done forced after STALL_FORCE, and a
    #    specialist stopped after SPEC_STALL actions in a row that changed nothing;
    #  D verify before done: every result carries the page-state diff (URL, fields, checked / selected controls), a
    #    success report on an unchanged page is flagged, and the planner keeps a constraint checklist (prompt);
    #  G no invented credentials: passwords absent from the task text are refused (harness.GuardedTools) + prompt.
    "v7": dict(prompt=PLANNER_PROMPT_V7, flash=True, page_check=True, overall=False, stop_when_spent=True,
               count_site_actions=True, max_turns=25, repeat_guard=True, v7=True),
}


def site_actions(hist):
    """Steps of a specialist episode that touch the site (not only done / macro_done)."""
    n = 0
    for st in hist.history:
        acts = [next(iter(a.model_dump(exclude_none=True)), "") for a in (st.model_output.action if st.model_output else [])]
        n += bool(set(acts) - {"done", "macro_done"})
    return n


class Team:
    """The planner's delegate action and its bookkeeping (trace, specialist histories, shared step budget)."""

    def __init__(self, pick_model, vllm_url, overall, context="", sub_cap=15, budget=H.MAX_STEPS, on_end=None,
                 temperature=0.0, version="v1"):
        self.pick_model, self.vllm_url, self.overall, self.context = pick_model, vllm_url, overall, context
        self.sub_cap, self.budget, self.on_end, self.temperature = sub_cap, budget, on_end, temperature
        self.version, self.cfg = version, VERSIONS[version]
        self.spent_calls = 0
        self.used, self.hists, self.trace = 0, [], []
        self.current = None                        # the specialist Agent running now (partial history on a timeout)
        self.tried, self.answers, self.stall, self.stop_note = {}, set(), 0, ""     # v7 progress control

    def tools(self):
        drop = [a for a in Tools().registry.registry.actions if a not in PLANNER_KEEPS]
        tools = PlannerTools(exclude_actions=drop)

        @tools.registry.action("Hand the next step of the task to the specialist of its family. The specialist does "
                               "only this step on the current page and reports what it did and saw.",
                               param_model=DelegateAction)
        async def delegate(params: DelegateAction, browser_session: BrowserSession):
            return await self.run_step(params.family, params.instruction, browser_session)
        return tools

    async def run_step(self, family, instruction, bs):
        left = self.budget - self.used
        if left <= 0:
            self.spent_calls += 1
            if self.cfg["stop_when_spent"] and self.spent_calls > 1:
                last = next((t["answer"] for t in reversed(self.trace) if t["answer"]), "") or ""
                return ActionResult(is_done=True, success=False, extracted_content=last, long_term_memory=last)
            msg = "No specialist steps are left. Call done now with your best answer from what has been found."
            return ActionResult(extracted_content=msg, long_term_memory=msg)
        model = self.pick_model(family)
        url = await bs.get_current_page_url()
        title = await _title(bs)
        v7 = self.cfg.get("v7")
        if v7:                                     # C: refuse a step already tried on this same page state
            s0 = await H.page_state(bs)
            fp0, key = H.fingerprint(s0), (family, _norm(instruction))
            if fp0 is not None and key in self.tried.get(fp0, set()):
                self.stall += 1
                if self.stall >= STALL_FORCE:
                    return self._force_done()
                msg = ("Refused: this exact step was already tried on the page as it is now, and it did not get further. "
                       "Choose a different step (another control, the search box, a filter or sort, a link, going back) "
                       "or call done." + self._stall_note())
                return ActionResult(extracted_content=msg, long_term_memory=msg)
        elif self.cfg.get("repeat_guard") and self.trace and (self.trace[-1]["family"], self.trace[-1]["subtask"]) == (
                family, instruction) and self.trace[-1].get("url_after") == url:
            msg = ("You just delegated this exact step and the page has not changed since. Choose a different step "
                   "(another control or another way), or call done.")
            return ActionResult(extracted_content=msg, long_term_memory=msg)
        step = (f"Overall task (for context only): {self.overall}\nYour step now: {instruction}\n"
                "Do only this step, then call done.") if self.cfg["overall"] else (
                f"{instruction}\nDo only this, then call done and report what you did and what the page shows.")
        agent = Agent(task=H.instruction(step + self.context, url),
                      llm=H.make_llm(model, base_url=self.vllm_url, temperature=self.temperature),
                      browser_session=bs, tools=H.make_tools(guard_text=self.overall if v7 else None),
                      max_failures=3, **H.AGENT_KWARGS)
        H.use_normalized_coordinates(bs)
        self.current, self.stop_note = agent, ""
        # A: browser-use spends the last of max_steps on a forced done, so k site actions need k + 1 steps
        cap = min(self.sub_cap, left + 1) if v7 else min(self.sub_cap, left)
        h = await agent.run(max_steps=cap, on_step_start=lambda a: H.enable_clipboard(bs, a),
                            on_step_end=self._spec_hook(bs, s0) if v7 else self.on_end)
        self.current = None
        if v7:
            return await self._report_v7(h, family, instruction, model, bs, s0, fp0, key)
        n = max(1, len(h.history))
        self.used += site_actions(h) if self.cfg.get("count_site_actions") else n
        self.hists.append(h)
        said = h.final_result() or next((e for e in reversed(h.errors()) if e), None) or "no report"
        status = "finished" if h.is_done() else "stopped at its step limit without finishing"
        self.trace.append({"subtask": instruction, "family": family, "model": model, "steps": len(h.history),
                           "done": h.is_done(), "answer": h.final_result(),
                           "url_after": await bs.get_current_page_url()})
        msg = (f"{family} specialist ({model}), {n} steps, {status}. It reported: {str(said)[:700]} "
               f"[specialist steps left: {self.budget - self.used}]")
        if self.cfg["page_check"]:
            url2, title2 = await bs.get_current_page_url(), await _title(bs)
            moved = f"the page went from {url} to {url2}" if url2 != url else (
                f"same URL ({url2})" + (", title changed" if title2 != title else ", same title"))
            msg += f" [check: {moved}]"
        return ActionResult(extracted_content=msg, long_term_memory=msg)

    # ── v7 ─────────────────────────────────────────────────────────────────────────────────────────────────────────
    def _stall_note(self):
        return (f" WARNING: {self.stall} steps in a row have made no progress. Change strategy now, or call done with "
                "what has been found." if self.stall >= STALL_WARN else "")

    def _force_done(self):
        """C: after STALL_FORCE delegations without progress the episode ends with the best answer found so far."""
        last = next((t["answer"] for t in reversed(self.trace) if t["answer"]), "") or ""
        self.trace.append({"subtask": "(stopped: no progress)", "family": "", "model": "", "steps": 0, "done": False,
                           "answer": None, "url_after": None, "forced_done": True})
        return ActionResult(is_done=True, success=False, extracted_content=last, long_term_memory=last)

    def _spec_hook(self, bs, s0):
        """C: the specialist's on_step_end. Stops it after SPEC_STALL actions in a row that left the page (scroll
        position included) exactly as it was. The evaluation's own hook (self.on_end) still runs first."""
        fps = [H.fingerprint(s0, scroll=True)]

        async def hook(agent):
            if self.on_end is not None:
                await self.on_end(agent)
            fps.append(H.fingerprint(await H.page_state(bs), scroll=True))
            tail = fps[-(SPEC_STALL + 1):]
            if len(tail) == SPEC_STALL + 1 and tail[0] is not None and len(set(tail)) == 1:
                self.stop_note = f"; stopped after {SPEC_STALL} actions in a row that changed nothing on the page"
                agent.stop()
        return hook

    async def _report_v7(self, h, family, instruction, model, bs, s0, fp0, key):
        """D: what the specialist said, plus what the page shows actually changed; C: progress bookkeeping."""
        n = max(1, len(h.history))
        self.used += site_actions(h)
        self.hists.append(h)
        s1 = await H.page_state(bs)
        fp1 = H.fingerprint(s1)
        if fp0 is not None:
            self.tried.setdefault(fp0, set()).add(key)
        changes = H.diff_states(s0, s1) if fp1 != fp0 else []
        ans = (h.final_result() or "").strip()
        progress = bool(changes) or (family.startswith("Reasoning") and ans and ans not in self.answers)
        if ans:
            self.answers.add(ans)
        self.stall = 0 if progress else self.stall + 1
        said = h.final_result() or next((e for e in reversed(h.errors()) if e), None) or "no report"
        status = ("finished" if h.is_done() else "stopped at its step limit without finishing") + self.stop_note
        url_after = s1.get("url") if s1 else await bs.get_current_page_url()
        self.trace.append({"subtask": instruction, "family": family, "model": model, "steps": len(h.history),
                           "done": h.is_done(), "answer": h.final_result(), "url_after": url_after,
                           "changes": changes, "progress": progress, "stopped": bool(self.stop_note)})
        check = "; ".join(changes) if changes else "nothing on the page changed"
        msg = (f"{family} specialist ({model}), {n} steps, {status}. It reported: {str(said)[:600]} "
               f"[page check: {check}] [specialist steps left: {self.budget - self.used}]")
        if not changes and h.is_done() and not family.startswith("Reasoning"):
            msg += (" Its report describes a result, but the page did not change: the step most likely did not "
                    "happen.")
        if self.stall >= STALL_FORCE:
            return self._force_done()
        return ActionResult(extracted_content=msg + self._stall_note(), long_term_memory=msg + self._stall_note())


async def _title(bs):
    try:
        return await H.evaluate(bs, "document.title") or ""
    except Exception:
        return ""


async def run_planner_agent(bs, task_text, start_url, pick_model, vllm_url, planner_model, *, context="", sub_cap=15,
                            budget=H.MAX_STEPS, max_turns=12, on_end=None, temperature=0.0, version="v1",
                            expose=None, turns=None):
    """-> (_Hist over the specialist episodes with the planner's answer, trace, the planner's own history).
    expose: a dict that receives the Team, so a caller whose wait_for times out can still save what was done.
    turns: overrides the version's planner-turn cap (2026-10-01: the 100-step Online-Mind2Web runs use 60)."""
    from webmix.evaluate import _Hist
    team = Team(pick_model, vllm_url, task_text, context, sub_cap, budget, on_end, temperature, version)
    if expose is not None:
        expose["team"] = team
    planner = Agent(task=H.instruction(task_text + context, start_url),
                    llm=H.make_llm(planner_model, base_url=vllm_url, temperature=temperature),
                    browser_session=bs, tools=team.tools(), extend_system_message=VERSIONS[version]["prompt"],
                    max_failures=3, use_vision=True, flash_mode=VERSIONS[version]["flash"], use_thinking=False,
                    use_judge=False, enable_planning=False,
                    message_compaction=False, max_actions_per_step=1, directly_open_url=False,
                    step_timeout=STEP_TIMEOUT)
    if expose is not None:
        expose["planner"] = planner          # v7: its observations go into the live-web trajectory
    H.use_normalized_coordinates(bs)
    ph = await planner.run(max_steps=turns or VERSIONS[version].get("max_turns", max_turns))
    answer = ph.final_result()
    if not answer and team.trace:                  # out of turns before done: the last specialist report
        answer = team.trace[-1]["answer"]
    return _Hist(team.hists, answer), team.trace, ph
