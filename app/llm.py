"""Shared LLM helper — thin compatibility layer over helpers.llm.

The implementation (provider routing, SDK calls, token tracking, the model
registry) lives in helpers.llm. This module re-exports the historical API so
existing callers keep working:

    from app.llm import call_llm, list_models, DEFAULT_MODEL

For new code, prefer helpers.llm.LLMClient — it exposes per-call/per-client/
global token usage and supports anthropic, openai, gemini, ollama and groq.
"""
from helpers.llm import (  # noqa: F401  (re-exported for backward compat)
    DEFAULT_MODEL,
    LLMClient,
    MODELS,
    SUPPORTED_MODELS,
    TokenUsage,
    _get_env,
    call_llm,
    list_models,
    resolve_provider,
)
