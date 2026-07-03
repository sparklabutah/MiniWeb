"""Shared LLM helper — uses Groq API (OpenAI-compatible), falls back to Claude CLI.

Usage:
    from app.llm import call_llm
    response = call_llm("Translate 'hello' to French", system="You are a translator.")
    # Returns string or None
"""

import json
import os
import urllib.request
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CLAUDE_CLI = "/uufs/chpc.utah.edu/sys/installdir/r8/claude/2.1.83/bin/claude"

# Groq API — fast, free tier, OpenAI-compatible
_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
_GROQ_MODEL = "llama-3.3-70b-versatile"


def _get_groq_key():
    key = os.environ.get("GROQ_API_KEY", "")
    if key:
        return key
    env_path = _PROJECT_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith("export "):
                line = line[7:]
            if line.startswith("GROQ_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def call_llm(prompt, system=None, max_tokens=500, temperature=0.7, json_mode=False):
    """Call LLM. Tries Groq first, then Claude CLI.

    Returns response text (str) or None on failure.
    """
    # Try Groq API (may be blocked on some networks)
    result = _call_groq(prompt, system, max_tokens, temperature, json_mode)
    if result:
        return result

    # Claude CLI
    return _call_claude(prompt, system, max_tokens)


def _call_groq(prompt, system=None, max_tokens=500, temperature=0.7, json_mode=False):
    key = _get_groq_key()
    if not key:
        return None

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    body = {
        "model": _GROQ_MODEL,
        "messages": messages,
        "max_completion_tokens": max_tokens,
        "temperature": temperature,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}

    try:
        payload = json.dumps(body).encode()
        req = urllib.request.Request(
            _GROQ_URL,
            data=payload,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "User-Agent": "MiniWeb/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


def _call_claude(prompt, system=None, max_tokens=500):
    import subprocess

    full_prompt = f"{system}\n\n{prompt}" if system else prompt
    try:
        cmd = [_CLAUDE_CLI, "-p", full_prompt, "--output-format", "text"]
        if max_tokens <= 200:
            cmd.extend(["--max-turns", "1"])
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return None
