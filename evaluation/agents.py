"""Pluggable agent interface and browser-use implementation.

AgentRunner is the protocol every agent must satisfy. The evaluation harness
only calls this interface -- it never touches browser-use (or any other library)
directly.

Built-in:
  - BrowserUseAgent: wraps the browser-use library with any LLM backend.
  - MockAgent: no LLM, no browser -- exercises the pipeline for free.
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from html.parser import HTMLParser
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


# ── Mock agent (no LLM, no browser) ─────────────────────────────────────────

class _TextExtractor(HTMLParser):
    """Minimal HTML→text extractor."""

    def __init__(self):
        super().__init__()
        self._pieces: list[str] = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        self._skip = tag in ("script", "style", "noscript")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            self._pieces.append(data)

    def get_text(self) -> str:
        return " ".join(self._pieces)


def _html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    return parser.get_text()


def _fetch(url: str, timeout: int = 10) -> str:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception:
        return ""


class MockAgent:
    """Pipeline-validation agent. No LLM, no browser.

    For each task it:
      1. GETs the site index page
      2. Follows obvious links (categories, search, detail pages) based on
         keywords in the instruction
      3. Extracts visible text and returns a best-guess answer

    This won't produce high pass rates but exercises the full eval pipeline
    (server management, task loading, verification, result aggregation)
    without any API calls or browser processes.
    """

    def __init__(self, *, use_vision=False, max_steps=20,
                 timeout=180, headless=True):
        self._server_url: str | None = None
        self.timeout = timeout
        self.max_steps = max_steps

    async def setup(self, server_url: str) -> None:
        self._server_url = server_url
        # Verify the server is reachable
        _fetch(server_url)

    async def run(self, task: str, server_url: str, task_dir: Path) -> AgentResult:
        t0 = time.time()
        trajectory = []
        answer = None

        try:
            # Step 1: fetch the site index
            index_html = _fetch(server_url)
            index_text = _html_to_text(index_html)
            trajectory.append({"action": "navigate", "url": server_url})

            # Step 2: try to find relevant links from the instruction
            instruction_lower = task.lower()

            # Extract all <a href="..."> links from the page
            links = re.findall(r'href="([^"]*)"', index_html)
            # Normalise relative links
            links = [
                l if l.startswith("http") else server_url.rstrip("/") + "/" + l.lstrip("/")
                for l in links if not l.startswith("#") and not l.startswith("javascript")
            ]

            # Try keyword matching to pick a relevant link
            visited = {server_url}
            pages_text = [index_text]

            keywords = re.findall(r'\b[a-z]{4,}\b', instruction_lower)
            # Remove common stop words
            stop = {"that", "this", "with", "from", "have", "what", "your",
                    "navigate", "page", "using", "many", "listed", "find",
                    "click", "search", "filter", "sort", "select", "open",
                    "look", "check", "view", "show", "display", "which",
                    "does", "total", "number", "count", "name", "after",
                    "before", "into", "then", "also", "each", "when", "more",
                    "most", "about", "been", "would", "could", "should"}
            keywords = [k for k in keywords if k not in stop][:5]

            steps = 1
            for link in links[:20]:
                if steps >= self.max_steps:
                    break
                link_lower = link.lower()
                if any(kw in link_lower for kw in keywords) and link not in visited:
                    visited.add(link)
                    page_html = _fetch(link)
                    if page_html:
                        page_text = _html_to_text(page_html)
                        pages_text.append(page_text)
                        trajectory.append({"action": "navigate", "url": link})
                        steps += 1

                        # Extract sub-links and follow one level deeper
                        sub_links = re.findall(r'href="([^"]*)"', page_html)
                        for sl in sub_links[:5]:
                            if steps >= self.max_steps:
                                break
                            full = sl if sl.startswith("http") else server_url.rstrip("/") + "/" + sl.lstrip("/")
                            if full not in visited and any(kw in full.lower() for kw in keywords):
                                visited.add(full)
                                sub_html = _fetch(full)
                                if sub_html:
                                    pages_text.append(_html_to_text(sub_html))
                                    trajectory.append({"action": "navigate", "url": full})
                                    steps += 1

            # Step 3: try to extract a plausible answer
            all_text = "\n".join(pages_text)

            # Look for numbers if the task asks "how many"
            if "how many" in instruction_lower or "count" in instruction_lower:
                # Try to find a count from the page
                numbers = re.findall(r'\b(\d+)\b', all_text)
                if numbers:
                    answer = numbers[0]

            if answer is None:
                # Return first 200 chars of extracted text as a generic answer
                answer = all_text[:200].strip() or "done"

            # Save trajectory
            with open(task_dir / "trajectory.json", "w") as f:
                json.dump(trajectory, f, indent=2)

        except Exception as e:
            return AgentResult(
                elapsed=round(time.time() - t0, 1),
                steps=0,
                is_done=False,
                final_result=None,
                errors=[str(e)],
            )

        elapsed = round(time.time() - t0, 1)
        return AgentResult(
            elapsed=elapsed,
            steps=len(trajectory),
            is_done=True,
            final_result=answer,
            errors=[],
        )

    async def teardown(self) -> None:
        pass


# ── Claude CLI LLM (drop-in for browser-use) ────────────────────────────────

CLAUDE_CLI = "/uufs/chpc.utah.edu/sys/installdir/r8/claude/2.1.83/bin/claude"


class ChatClaude:
    """browser-use BaseChatModel backed by Claude CLI subprocess.

    Implements the ainvoke() protocol so browser-use Agent can use it as its LLM.
    Each call spawns `claude -p <prompt>` and parses the response.
    """

    _verified_api_keys: bool = True  # no key needed

    def __init__(self, model: str = "claude-cli", timeout: int = 120):
        self.model = model
        self._timeout = timeout

    @property
    def provider(self) -> str:
        return "claude-cli"

    @property
    def name(self) -> str:
        return self.model

    @property
    def model_name(self) -> str:
        return self.model

    @staticmethod
    def _serialize_messages(messages) -> str:
        """Convert browser-use message objects into a single text prompt."""
        parts = []
        for msg in messages:
            role = getattr(msg, "role", "user")
            content = getattr(msg, "content", "")
            if isinstance(content, list):
                # Multi-part content (text + images) — extract text parts
                text_parts = []
                for part in content:
                    if hasattr(part, "text"):
                        text_parts.append(part.text)
                    elif isinstance(part, dict) and "text" in part:
                        text_parts.append(part["text"])
                content = "\n".join(text_parts)
            if content:
                parts.append(f"[{role.upper()}]\n{content}")
        return "\n\n".join(parts)

    @staticmethod
    def _extract_json(text: str) -> str:
        """Strip markdown code fences from Claude's response."""
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        # Also handle trailing fence
        if "```" in text:
            text = text.split("```")[0]
        return text.strip()

    async def ainvoke(self, messages, output_format=None, **kwargs):
        from browser_use.llm.views import ChatInvokeCompletion, ChatInvokeUsage
        from browser_use.llm.exceptions import ModelProviderError

        prompt_text = self._serialize_messages(messages)

        if output_format is not None:
            schema = output_format.model_json_schema()
            prompt_text += (
                "\n\n---\nYou MUST respond with ONLY valid JSON (no markdown, no explanation) "
                "matching this schema:\n"
                + json.dumps(schema, indent=2)
            )

        try:
            proc = await asyncio.create_subprocess_exec(
                CLAUDE_CLI, "-p", prompt_text, "--output-format", "text",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self._timeout
            )
            text = stdout.decode("utf-8", errors="replace").strip()

            if proc.returncode != 0:
                err = stderr.decode("utf-8", errors="replace")[:200]
                raise ModelProviderError(
                    message=f"Claude CLI returned {proc.returncode}: {err}",
                    model=self.model,
                )
        except asyncio.TimeoutError:
            raise ModelProviderError(
                message=f"Claude CLI timed out after {self._timeout}s",
                model=self.model,
            )

        usage = ChatInvokeUsage(
            prompt_tokens=0, completion_tokens=0, total_tokens=0,
            prompt_cached_tokens=None, prompt_image_tokens=None,
            prompt_cache_creation_tokens=None,
        )

        if output_format is None:
            return ChatInvokeCompletion(
                completion=text, usage=usage, stop_reason="end_turn",
            )

        # Structured output: parse JSON into Pydantic model
        json_text = self._extract_json(text)
        try:
            parsed = output_format.model_validate_json(json_text)
        except Exception:
            # Retry: sometimes there's extra text around the JSON
            # Try to find the outermost { }
            start = json_text.find("{")
            end = json_text.rfind("}")
            if start >= 0 and end > start:
                json_text = json_text[start:end + 1]
                parsed = output_format.model_validate_json(json_text)
            else:
                raise ModelProviderError(
                    message=f"Failed to parse JSON from Claude response: {text[:200]}",
                    model=self.model,
                )

        return ChatInvokeCompletion(
            completion=parsed, usage=usage, stop_reason="end_turn",
        )
