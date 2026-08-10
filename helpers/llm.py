"""Unified LLM client — one place for calling models and tracking tokens.

A single `LLMClient` routes a model name to its provider and calls it through
that provider's official SDK, returning the response text and accumulating
token usage (per call, per client, and globally). Supported providers:

    anthropic   claude-*            (ANTHROPIC_API_KEY)
    openai      gpt-*, o1/o3/o4     (OPENAI_API_KEY)
    gemini      gemini-*            (GEMINI_API_KEY / GOOGLE_API_KEY, or Vertex)
    ollama      ollama/<model>      (local; OLLAMA_HOST, default localhost:11434)
    groq        everything else     (GROQ_API_KEY, OpenAI-compatible endpoint)

`MODELS` is the registry of current models per provider; routing is exact-match
first, then by prefix. `call_llm(...)` is the one-shot convenience (returns
str | None) that the rest of the codebase already uses.

    from helpers.llm import LLMClient, call_llm, MODELS
    client = LLMClient("claude-sonnet-5")
    text = client.complete("Summarize this.", system="Be terse.")
    print(client.usage.as_dict())      # {'prompt':.., 'completion':.., 'total':.., 'calls':..}
    print(LLMClient.GLOBAL.as_dict())  # cumulative across every client this process
"""
from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL = os.environ.get("LLM_MODEL") or "gemini-2.5-flash"

# Current models per provider (latest first). Unlisted names still route by
# prefix, so this is a convenience/allow-list, not an exhaustive gate.
MODELS = {
    "anthropic": [
        "claude-opus-4-8", "claude-opus-5", "claude-sonnet-5",
        "claude-haiku-4-5-20251001", "claude-3-7-sonnet-latest",
    ],
    "openai": [
        "gpt-5", "gpt-5-mini", "gpt-5-nano",
        "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano",
        "o3", "o4-mini", "gpt-4o", "gpt-4o-mini",
    ],
    "gemini": [
        "gemini-3-pro-preview", "gemini-3-flash-preview", "gemini-3.1-pro-preview",
        "gemini-3.5-flash", "gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite",
    ],
    "ollama": [
        "llama3.3", "llama3.2", "qwen2.5", "qwen2.5-coder",
        "mistral", "phi4", "gemma2", "deepseek-r1",
    ],
    "groq": [
        "llama-3.3-70b-versatile", "llama-3.1-8b-instant",
        "meta-llama/llama-4-scout-17b-16e-instruct",
        "meta-llama/llama-4-maverick-17b-128e-instruct",
        "openai/gpt-oss-120b", "openai/gpt-oss-20b",
        "qwen/qwen3-32b", "moonshotai/kimi-k2-instruct",
    ],
}
SUPPORTED_MODELS = MODELS  # backward-compat alias
_MODEL_TO_PROVIDER = {m: p for p, ms in MODELS.items() for m in ms}


# ── env / .env access (ported from the original app.llm) ──────────────────────

def _get_env(name: str) -> str:
    """Read a config value from the environment, falling back to .env (handles
    multi-line quoted values like GOOGLE_CREDENTIALS_JSON)."""
    val = os.environ.get(name, "")
    if val:
        return val
    env_path = _ROOT / ".env"
    if not env_path.exists():
        return ""
    lines = env_path.read_text().splitlines()
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("export "):
            s = s[7:]
        if not s.startswith(name + "="):
            continue
        raw = s.split("=", 1)[1]
        if raw.startswith('"') and not (len(raw) > 1 and raw.rstrip().endswith('"')):
            parts = [raw[1:]]
            for cont in lines[i + 1:]:
                if cont.rstrip().endswith('"') and not cont.rstrip().endswith('\\"'):
                    parts.append(cont.rstrip()[:-1]); break
                parts.append(cont)
            return "\n".join(parts).replace('\\"', '"').replace("\\\\", "\\")
        return raw.strip().strip('"').strip("'")
    return ""


def resolve_provider(model: str) -> str:
    """Map a model name to 'anthropic' | 'openai' | 'gemini' | 'ollama' | 'groq'."""
    if model in _MODEL_TO_PROVIDER:
        return _MODEL_TO_PROVIDER[model]
    if model.startswith("ollama/") or model.startswith("ollama:"):
        return "ollama"
    if model.startswith("claude"):
        return "anthropic"
    if model.startswith("gemini"):
        return "gemini"
    if model.startswith(("gpt-", "o1", "o3", "o4", "chatgpt")):
        return "openai"
    return "groq"


# ── token usage ───────────────────────────────────────────────────────────────

@dataclass
class TokenUsage:
    prompt: int = 0
    completion: int = 0
    total: int = 0
    calls: int = 0

    def add(self, prompt: int, completion: int) -> None:
        self.prompt += prompt or 0
        self.completion += completion or 0
        self.total += (prompt or 0) + (completion or 0)
        self.calls += 1

    def as_dict(self) -> dict:
        return {"prompt": self.prompt, "completion": self.completion,
                "total": self.total, "calls": self.calls}


# ── the client ────────────────────────────────────────────────────────────────

class LLMClient:
    """Call any supported model and track its token usage.

    Usage is accumulated on the instance (`self.usage`) and on the process-wide
    `LLMClient.GLOBAL`. `complete()` returns the response text, or None on
    failure (matching the historical `call_llm` contract)."""

    GLOBAL = TokenUsage()
    _lock = threading.Lock()

    def __init__(self, model: str | None = None, *, temperature: float = 0.7,
                 max_tokens: int = 1024, timeout: int = 60):
        self.model = model or DEFAULT_MODEL
        self.provider = resolve_provider(self.model)
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.usage = TokenUsage()

    def _track(self, prompt_toks: int, completion_toks: int) -> None:
        self.usage.add(prompt_toks, completion_toks)
        with LLMClient._lock:
            LLMClient.GLOBAL.add(prompt_toks, completion_toks)

    def complete(self, prompt: str, *, system: str | None = None,
                 json_mode: bool = False, max_tokens: int | None = None,
                 temperature: float | None = None) -> str | None:
        mt = max_tokens if max_tokens is not None else self.max_tokens
        temp = temperature if temperature is not None else self.temperature
        backend = {
            "anthropic": self._anthropic, "openai": self._openai,
            "gemini": self._gemini, "ollama": self._ollama, "groq": self._groq,
        }[self.provider]
        try:
            text, p, c = backend(prompt, system, mt, temp, json_mode)
        except Exception:
            return None
        if text is None:
            return None
        self._track(p, c)
        return text.strip() or None

    # -- backends: return (text, prompt_tokens, completion_tokens) --------------

    def _openai(self, prompt, system, mt, temp, json_mode, *, base_url=None, key=None):
        from openai import OpenAI
        key = key or _get_env("OPENAI_API_KEY")
        if not key:
            return None, 0, 0
        client = OpenAI(api_key=key, base_url=base_url, timeout=self.timeout)
        msgs = ([{"role": "system", "content": system}] if system else []) + \
               [{"role": "user", "content": prompt}]
        kw = {"model": self.model.split("/", 1)[-1] if base_url else self.model,
              "messages": msgs, "max_completion_tokens": mt}
        if not self.model.startswith(("gpt-5", "o1", "o3", "o4")):
            kw["temperature"] = temp
        if json_mode:
            kw["response_format"] = {"type": "json_object"}
        r = client.chat.completions.create(**kw)
        u = r.usage
        return r.choices[0].message.content, getattr(u, "prompt_tokens", 0), getattr(u, "completion_tokens", 0)

    def _groq(self, prompt, system, mt, temp, json_mode):
        return self._openai(prompt, system, mt, temp, json_mode,
                            base_url="https://api.groq.com/openai/v1",
                            key=_get_env("GROQ_API_KEY"))

    def _anthropic(self, prompt, system, mt, temp, json_mode):
        from anthropic import Anthropic
        key = _get_env("ANTHROPIC_API_KEY")
        if not key:
            return None, 0, 0
        client = Anthropic(api_key=key, timeout=self.timeout)
        sys_txt = system or ""
        if json_mode:
            sys_txt = (sys_txt + "\nRespond with ONLY valid JSON, no prose or markdown.").strip()
        kw = {"model": self.model, "max_tokens": mt, "temperature": temp,
              "messages": [{"role": "user", "content": prompt}]}
        if sys_txt:
            kw["system"] = sys_txt
        r = client.messages.create(**kw)
        text = "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
        return text, r.usage.input_tokens, r.usage.output_tokens

    def _gemini(self, prompt, system, mt, temp, json_mode):
        from google import genai
        from google.genai import types
        if _get_env("GOOGLE_GENAI_USE_VERTEXAI").lower() in ("1", "true", "yes"):
            # Vertex AI: build credentials from the service-account JSON (the SDK's
            # default path uses ADC, which isn't set here).
            creds = None
            creds_json = _get_env("GOOGLE_CREDENTIALS_JSON")
            if creds_json:
                from google.oauth2 import service_account
                creds = service_account.Credentials.from_service_account_info(
                    json.loads(creds_json),
                    scopes=["https://www.googleapis.com/auth/cloud-platform"])
            client = genai.Client(vertexai=True, credentials=creds,
                                  project=_get_env("GOOGLE_CLOUD_PROJECT"),
                                  location=_get_env("GOOGLE_CLOUD_LOCATION") or "global")
        else:
            key = _get_env("GEMINI_API_KEY") or _get_env("GOOGLE_API_KEY")
            if not key:
                return None, 0, 0
            client = genai.Client(api_key=key)
        cfg = types.GenerateContentConfig(
            temperature=temp,
            system_instruction=system or None,
            response_mime_type="application/json" if json_mode else None,
        )
        r = client.models.generate_content(model=self.model, contents=prompt, config=cfg)
        um = r.usage_metadata
        return (r.text, getattr(um, "prompt_token_count", 0) or 0,
                getattr(um, "candidates_token_count", 0) or 0)

    def _ollama(self, prompt, system, mt, temp, json_mode):
        import ollama
        model = self.model.split("/", 1)[-1] if "/" in self.model else self.model
        client = ollama.Client(host=_get_env("OLLAMA_HOST") or "http://localhost:11434")
        msgs = ([{"role": "system", "content": system}] if system else []) + \
               [{"role": "user", "content": prompt}]
        r = client.chat(model=model, messages=msgs,
                        format="json" if json_mode else None,
                        options={"temperature": temp, "num_predict": mt})
        return (r["message"]["content"], r.get("prompt_eval_count", 0), r.get("eval_count", 0))


# ── module-level convenience (backward-compatible with the old app.llm) ───────

def call_llm(prompt, system=None, max_tokens=500, temperature=0.7,
             json_mode=False, model=None):
    """One-shot call. Returns response text (str) or None on failure."""
    return LLMClient(model, temperature=temperature, max_tokens=max_tokens).complete(
        prompt, system=system, json_mode=json_mode)


def _provider_configured(provider: str) -> bool:
    keys = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY",
            "groq": "GROQ_API_KEY"}
    if provider in keys:
        return bool(_get_env(keys[provider]))
    if provider == "gemini":
        if _get_env("GOOGLE_GENAI_USE_VERTEXAI").lower() in ("1", "true", "yes"):
            return bool(_get_env("GOOGLE_CLOUD_PROJECT"))
        return bool(_get_env("GEMINI_API_KEY") or _get_env("GOOGLE_API_KEY"))
    if provider == "ollama":
        return True  # local; assume a daemon may be running
    return False


def list_models(configured_only=False):
    """{provider: {"configured": bool, "models": [...]}}."""
    out = {}
    for provider, models in MODELS.items():
        configured = _provider_configured(provider)
        if configured_only and not configured:
            continue
        out[provider] = {"configured": configured, "models": list(models)}
    return out
