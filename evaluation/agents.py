"""Pluggable agent interface and browser-use implementation.

AgentRunner is the protocol every agent must satisfy. The evaluation harness
only calls this interface -- it never touches browser-use (or any other library)
directly.

Built-in:
  - BrowserUseAgent: wraps the browser-use library with any LLM backend.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass
class AgentResult:
    """Result returned by an agent after running a single task."""

    elapsed: float
    steps: int
    is_done: bool
    final_result: str | None
    errors: list[str] = field(default_factory=list)


@runtime_checkable
class AgentRunner(Protocol):
    """Interface that every agent implementation must satisfy."""

    async def setup(self, server_url: str) -> None:
        """One-time setup before running tasks (e.g. start browser)."""
        ...

    async def run(self, task: str, server_url: str, task_dir: Path) -> AgentResult:
        """Execute a single task. Save trajectory artifacts to *task_dir*."""
        ...

    async def teardown(self) -> None:
        """Release resources (e.g. close browser)."""
        ...


# -- Chrome flags to reduce per-instance resource usage under parallel load --
_EXTRA_CHROME_ARGS = [
    "--disable-gpu",
    "--disable-software-rasterizer",
    "--disable-extensions",
    "--no-sandbox",
]

_RETRYABLE_ERRORS = ("Timeout", "ReadTimeout", "ConnectionError", "WebSocket", "CDP")


def _is_retryable(exc: Exception) -> bool:
    text = f"{type(exc).__name__}: {exc}"
    return any(k in text for k in _RETRYABLE_ERRORS)


class BrowserUseAgent:
    """AgentRunner backed by the *browser-use* library."""

    def __init__(
        self,
        llm,
        *,
        use_vision: bool = False,
        max_steps: int = 50,
        timeout: int = 300,
        headless: bool = True,
    ):
        self.llm = llm
        self.use_vision = use_vision
        self.max_steps = max_steps
        self.timeout = timeout
        self.headless = headless
        self._session = None
        self._server_url: str | None = None

    async def _start_session(self, max_retries: int = 3) -> None:
        from browser_use import BrowserSession

        for attempt in range(1, max_retries + 1):
            self._session = BrowserSession(
                headless=self.headless,
                keep_alive=True,
                args=_EXTRA_CHROME_ARGS,
            )
            try:
                await self._session.start()
                return
            except Exception as e:
                if attempt < max_retries and _is_retryable(e):
                    print(
                        f"    [BrowserUseAgent] start attempt "
                        f"{attempt}/{max_retries} failed ({type(e).__name__}), retrying..."
                    )
                    try:
                        await self._session.kill()
                    except Exception:
                        pass
                    self._session = None
                    await asyncio.sleep(3 * attempt)
                else:
                    raise

    async def setup(self, server_url: str) -> None:
        self._server_url = server_url
        await self._start_session()
        page = await self._session.get_current_page()
        await page.goto(server_url)
        await asyncio.sleep(2)

    async def restart_session(self) -> None:
        old_dir = None
        if self._session:
            try:
                old_dir = getattr(self._session.browser_profile, "user_data_dir", None)
            except Exception:
                pass
            try:
                await self._session.kill()
            except Exception:
                pass
            self._session = None
        if old_dir:
            shutil.rmtree(str(old_dir), ignore_errors=True)

        await self._start_session()
        page = await self._session.get_current_page()
        await page.goto(self._server_url)
        await asyncio.sleep(2)

    async def run(self, task: str, server_url: str, task_dir: Path) -> AgentResult:
        from browser_use import Agent

        instruction = (
            f"You are interacting with a web application at {server_url}. "
            f"Your task: {task}"
        )

        agent = Agent(
            task=instruction,
            llm=self.llm,
            browser_session=self._session,
            use_vision=self.use_vision,
            save_conversation_path=str(task_dir / "conversations"),
            max_steps=self.max_steps,
        )

        timed_out = False
        t0 = time.time()
        try:
            history = await asyncio.wait_for(agent.run(), timeout=self.timeout)
        except asyncio.TimeoutError:
            timed_out = True
            history = agent.history
        elapsed = time.time() - t0

        # Save trajectory
        history.save_to_file(task_dir / "history.json")
        screenshots_dst = task_dir / "screenshots"
        for step_idx, path_str in enumerate(history.screenshot_paths()):
            if path_str and Path(path_str).exists():
                screenshots_dst.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path_str, screenshots_dst / f"step_{step_idx}.png")

        if timed_out:
            raise asyncio.TimeoutError()

        return AgentResult(
            elapsed=round(elapsed, 1),
            steps=len(history.history),
            is_done=history.is_done(),
            final_result=history.final_result(),
            errors=history.errors(),
        )

    async def teardown(self) -> None:
        user_data_dir = None
        if self._session:
            try:
                user_data_dir = getattr(self._session.browser_profile, "user_data_dir", None)
            except Exception:
                pass
            try:
                await self._session.kill()
            except Exception:
                pass
            self._session = None
        if user_data_dir:
            shutil.rmtree(str(user_data_dir), ignore_errors=True)
