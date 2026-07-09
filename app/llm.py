"""Shared LLM helper — routes a requested model to its provider.

Supported providers: Groq, OpenAI, Gemini (Vertex AI or public API).
There is no fallback chain: callers pick a model (or the default), and the
call is routed to that model's provider. SUPPORTED_MODELS is the registry;
unknown model names are routed by prefix (gemini-* -> Gemini, gpt-*/o* ->
OpenAI, everything else -> Groq).

Env:
    LLM_MODEL                     default model when the caller passes none
    GROQ_API_KEY                  Groq REST (OpenAI-compatible)
    OPENAI_API_KEY                OpenAI chat completions REST
    GOOGLE_GENAI_USE_VERTEXAI     "true" -> Vertex AI with service account
    GOOGLE_CREDENTIALS_JSON       service account JSON (Vertex)
    GOOGLE_CLOUD_PROJECT/LOCATION Vertex project + location
    GEMINI_API_KEY/GOOGLE_API_KEY public Gemini API key (non-Vertex)

Usage:
    from app.llm import call_llm, list_models
    response = call_llm("Translate 'hello' to French", model="gemini-2.5-flash")
    # Returns string or None
"""

import json
import os
import urllib.request
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
_OPENAI_URL = "https://api.openai.com/v1/chat/completions"

DEFAULT_MODEL = "gemini-2.5-flash"

# Registry of supported models per provider. Routing is exact-match first,
# then prefix-based for models not listed here.
SUPPORTED_MODELS = {
    "groq": [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "meta-llama/llama-4-scout-17b-16e-instruct",
        "meta-llama/llama-4-maverick-17b-128e-instruct",
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "qwen/qwen3-32b",
        "moonshotai/kimi-k2-instruct",
    ],
    "openai": [
        "gpt-5",
        "gpt-5-mini",
        "gpt-5-nano",
        "gpt-4.1",
        "gpt-4.1-mini",
        "gpt-4.1-nano",
        "gpt-4o",
        "gpt-4o-mini",
    ],
    "gemini": [
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash",
        "gemini-3-flash-preview",
        "gemini-3-pro-preview",
    ],
}

_MODEL_TO_PROVIDER = {m: p for p, models in SUPPORTED_MODELS.items() for m in models}


def _get_env(name):
    """Read a config value from the environment, falling back to .env."""
    val = os.environ.get(name, "")
    if val:
        return val
    env_path = _PROJECT_ROOT / ".env"
    if not env_path.exists():
        return ""
    text = env_path.read_text()
    # handle multi-line quoted values (e.g. GOOGLE_CREDENTIALS_JSON="{...\n...}")
    lines = text.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("export "):
            stripped = stripped[7:]
        if not stripped.startswith(name + "="):
            continue
        raw = stripped.split("=", 1)[1]
        if raw.startswith('"') and not (len(raw) > 1 and raw.rstrip().endswith('"')):
            parts = [raw[1:]]
            for cont in lines[i + 1:]:
                if cont.rstrip().endswith('"') and not cont.rstrip().endswith('\\"'):
                    parts.append(cont.rstrip()[:-1])
                    break
                parts.append(cont)
            value = "\n".join(parts)
            # dotenv-style unescaping inside double-quoted values
            return value.replace('\\"', '"').replace("\\\\", "\\")
        return raw.strip().strip('"').strip("'")
    return ""


def resolve_provider(model):
    """Map a model name to its provider ('groq' | 'openai' | 'gemini')."""
    if model in _MODEL_TO_PROVIDER:
        return _MODEL_TO_PROVIDER[model]
    # prefix routing for models not (yet) in the registry
    if model.startswith("gemini"):
        return "gemini"
    if model.startswith(("gpt-", "o1", "o3", "o4", "chatgpt")):
        return "openai"
    return "groq"


def _provider_configured(provider):
    if provider == "groq":
        return bool(_get_env("GROQ_API_KEY"))
    if provider == "openai":
        return bool(_get_env("OPENAI_API_KEY"))
    if provider == "gemini":
        if _get_env("GOOGLE_GENAI_USE_VERTEXAI").lower() in ("1", "true", "yes"):
            return bool(_get_env("GOOGLE_CREDENTIALS_JSON")
                        and _get_env("GOOGLE_CLOUD_PROJECT"))
        return bool(_get_env("GEMINI_API_KEY") or _get_env("GOOGLE_API_KEY"))
    return False


def list_models(configured_only=False):
    """Supported models per provider, with configuration status.

    Returns: {provider: {"configured": bool, "models": [...]}}
    """
    out = {}
    for provider, models in SUPPORTED_MODELS.items():
        configured = _provider_configured(provider)
        if configured_only and not configured:
            continue
        out[provider] = {"configured": configured, "models": list(models)}
    return out


def call_llm(prompt, system=None, max_tokens=500, temperature=0.7,
             json_mode=False, model=None):
    """Call the given model (or the default), routed to its provider.

    Returns response text (str) or None on failure.
    """
    model = model or _get_env("LLM_MODEL") or DEFAULT_MODEL
    provider = resolve_provider(model)
    fn = {"groq": _call_groq, "openai": _call_openai, "gemini": _call_gemini}[provider]
    return fn(prompt, system, max_tokens, temperature, json_mode, model)


def _post_json(url, body, headers):
    payload = json.dumps(body).encode()
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json",
                 "User-Agent": "MiniWeb/1.0", **headers},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


# ── Groq ────────────────────────────────────────────────────────────────────

def _call_groq(prompt, system, max_tokens, temperature, json_mode, model):
    key = _get_env("GROQ_API_KEY")
    if not key:
        return None
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    body = {
        "model": model,
        "messages": messages,
        "max_completion_tokens": max_tokens,
        "temperature": temperature,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    try:
        data = _post_json(_GROQ_URL, body, {"Authorization": f"Bearer {key}"})
        return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


# ── OpenAI ──────────────────────────────────────────────────────────────────

def _call_openai(prompt, system, max_tokens, temperature, json_mode, model):
    key = _get_env("OPENAI_API_KEY")
    if not key:
        return None
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    body = {
        "model": model,
        "messages": messages,
        "max_completion_tokens": max_tokens,
    }
    # gpt-5 family and o* reasoning models reject non-default temperature
    if not model.startswith(("gpt-5", "o1", "o3", "o4")):
        body["temperature"] = temperature
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    try:
        data = _post_json(_OPENAI_URL, body, {"Authorization": f"Bearer {key}"})
        return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


# ── Gemini (Vertex AI or public API) ────────────────────────────────────────

_vertex_credentials = None  # cached google-auth credentials


def _get_vertex_token():
    """OAuth token from the GOOGLE_CREDENTIALS_JSON service account."""
    global _vertex_credentials
    if _vertex_credentials is None:
        creds_json = _get_env("GOOGLE_CREDENTIALS_JSON")
        if not creds_json:
            return None
        from google.oauth2 import service_account
        info = json.loads(creds_json)
        _vertex_credentials = service_account.Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/cloud-platform"])
    if not _vertex_credentials.valid:
        from google.auth.transport.requests import Request
        _vertex_credentials.refresh(Request())
    return _vertex_credentials.token


def _call_gemini(prompt, system, max_tokens, temperature, json_mode, model):
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": temperature,
        },
    }
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    if json_mode:
        body["generationConfig"]["responseMimeType"] = "application/json"

    try:
        use_vertex = _get_env("GOOGLE_GENAI_USE_VERTEXAI").lower() in ("1", "true", "yes")
        if use_vertex:
            token = _get_vertex_token()
            project = _get_env("GOOGLE_CLOUD_PROJECT")
            if not token or not project:
                return None
            location = _get_env("GOOGLE_CLOUD_LOCATION") or "global"
            host = ("aiplatform.googleapis.com" if location == "global"
                    else f"{location}-aiplatform.googleapis.com")
            url = (f"https://{host}/v1/projects/{project}/locations/{location}"
                   f"/publishers/google/models/{model}:generateContent")
            headers = {"Authorization": f"Bearer {token}"}
        else:
            key = _get_env("GEMINI_API_KEY") or _get_env("GOOGLE_API_KEY")
            if not key:
                return None
            url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
                   f"{model}:generateContent")
            headers = {"x-goog-api-key": key}

        data = _post_json(url, body, headers)
        parts = data["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts).strip() or None
    except Exception:
        return None
