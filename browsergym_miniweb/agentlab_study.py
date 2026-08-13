"""AgentLab wiring for the MiniWeb BrowserGym benchmark (browser-gym branch).

Builds a `bgym.Benchmark` over MiniWeb gym ids and a `GenericAgentArgs` agent,
ready for `agentlab.experiments.study.make_study`.

Model-agnostic: pass any model name the repo's router (helpers.llm) understands —
    claude-*          -> AnthropicModelArgs                (ANTHROPIC_API_KEY)
    gpt-* / o-series  -> OpenAIModelArgs                   (OPENAI_API_KEY)
    gemini-*          -> LiteLLMModelArgs "gemini/<name>"  (GEMINI_API_KEY)
    ollama/<name>     -> LiteLLMModelArgs "ollama_chat/<name>"  (OLLAMA_API_BASE,
                         default http://localhost:11434)
Anything else routes through LiteLLM as "groq/<name>" (GROQ_API_KEY), matching
helpers.llm's catch-all.

The default agent is VISUAL — screenshot + set-of-marks on top of the AXTree —
which any vision-language model can consume; pass visual=False for text-only
models. (The FLAGS_GPT_4o preset this started from is just AgentLab's tuned flag
set named after the model it was tuned on; nothing in it is model-specific.)

Visual sanity-check of the offline sandbox (watch external visits bounce to the
/_blocked page):
    agentlab-assistant \
        --agent_config browsergym_miniweb.agentlab_study.MINIWEB_ASSISTANT_AGENT \
        --start_url http://localhost:8099/
"""
import bgym
from agentlab.agents import dynamic_prompting as dp
from agentlab.agents.generic_agent.generic_agent import GenericAgentArgs
from agentlab.agents.generic_agent.generic_agent_prompt import GenericPromptFlags
from agentlab.llm.chat_api import (AnthropicModelArgs, LiteLLMChatModel,
                                   LiteLLMModelArgs, OpenAIModelArgs)

import browsergym_miniweb  # noqa: F401  (registers gym ids + report_answer action + offline)
from helpers.llm import DEFAULT_MODEL, resolve_provider

try:  # same aliases as the native runner; evaluation.agents needs browser_use,
    from evaluation.agents import MODEL_ALIASES  # which this env may not have
except Exception:
    MODEL_ALIASES = {}


def _gym_id(task_id: str) -> str:
    # EnvArgs / BrowserGym prepend "browsergym/" themselves — task_name must NOT include it
    return "miniweb." + task_id.replace("/", ".")


def make_benchmark(task_ids, max_steps: int = 15, headless: bool = True) -> bgym.Benchmark:
    return bgym.Benchmark(
        name="miniweb",
        high_level_action_set_args=bgym.HighLevelActionSetArgs(
            # bid = DOM actions; chat = send_msg_to_user + report_answer (the latter
            # injected into the 'chat' subset in browsergym_miniweb/__init__.py).
            # NO 'nav' subset on purpose: the agent must navigate MiniWeb through the
            # portal's own UI (search bar, site tiles, tab bar), starting from the
            # directory — not via a goto tool.
            subsets=["chat", "bid"],
            multiaction=False,
            strict=False,
            retry_with_force=True,
            demo_mode="off",
        ),
        is_multi_tab=False,
        supports_parallel_seeds=True,
        env_args_list=[bgym.EnvArgs(task_name=_gym_id(t), max_steps=max_steps,
                                    headless=headless)
                       for t in task_ids],
        backends=[],                     # run with make_study(..., ignore_dependencies=True)
    )


# MiniWeb's tuned flag set — AgentLab's proven AXTree/CoT/history defaults with
# the visual channel (screenshot + set-of-marks) on. Model-agnostic.
FLAGS_MINIWEB = GenericPromptFlags(
    obs=dp.ObsFlags(
        use_html=False,
        use_ax_tree=True,
        use_focused_element=True,
        use_error_logs=True,
        use_history=True,
        use_past_error_logs=False,
        use_action_history=True,
        use_think_history=False,
        use_diff=False,
        html_type="pruned_html",
        use_screenshot=True,
        use_som=True,
        extract_visible_tag=True,
        extract_clickable_tag=True,
        extract_coords="False",
        filter_visible_elements_only=False,
    ),
    action=dp.ActionFlags(
        # kept in sync with make_benchmark's action set (benchmark-level wins)
        action_set=bgym.HighLevelActionSetArgs(subsets=["chat", "bid"],
                                               multiaction=False),
        long_description=False,
        individual_examples=False,
    ),
    use_plan=False,
    use_criticise=False,
    use_thinking=True,
    use_memory=False,
    use_concrete_example=True,
    use_abstract_example=True,
    use_hints=True,
    enable_chat=False,
    max_prompt_tokens=28_000,   # fit a local 32k-context model (ollama n_ctx=32768)
                                # with headroom for the response; AgentLab trims to fit
    be_cautious=True,
    extra_instructions=None,
)


def _raw_b64_images(messages):
    """Copy of `messages` with data-URI images reduced to raw base64.

    litellm's ollama_chat route forwards OpenAI-style image_url values verbatim
    into ollama's `images` field, but ollama expects bare base64 — the "data:"
    prefix makes it fail with 'illegal base64 data at input byte 4'.
    """
    out = []
    for m in messages:
        content = m.get("content") if isinstance(m, dict) else None
        if isinstance(content, list):
            parts, changed = [], False
            for p in content:
                url = p.get("image_url") if isinstance(p, dict) else None
                if isinstance(url, dict) and str(url.get("url", "")).startswith("data:"):
                    p = {**p, "image_url": {**url, "url": url["url"].split(",", 1)[-1]}}
                    changed = True
                elif isinstance(url, str) and url.startswith("data:"):
                    p = {**p, "image_url": url.split(",", 1)[-1]}
                    changed = True
                parts.append(p)
            if changed:
                m = {**m, "content": parts}
        out.append(m)
    return out


class OllamaChatModel(LiteLLMChatModel):
    """LiteLLM ollama_chat with the image format ollama actually accepts."""

    def __call__(self, messages, n_samples=1, temperature=None):
        return super().__call__(_raw_b64_images(messages), n_samples, temperature)


class OllamaModelArgs(LiteLLMModelArgs):
    def make_model(self):
        return OllamaChatModel(
            model_name=self.model_name,
            temperature=self.temperature,
            max_tokens=self.max_new_tokens,
            log_probs=self.log_probs,
        )


def make_model_args(model_name: str,
                    max_total_tokens: int = 32000,
                    max_new_tokens: int = 2000,
                    temperature: float = 0.0):
    """Route a model name to the right AgentLab chat-model args (see module doc)."""
    model_name = MODEL_ALIASES.get(model_name, model_name)
    provider = resolve_provider(model_name)
    common = dict(
        max_total_tokens=max_total_tokens,
        max_input_tokens=max_total_tokens - max_new_tokens,
        max_new_tokens=max_new_tokens,
        temperature=temperature,
        vision_support=True,
    )
    if provider == "anthropic":
        return AnthropicModelArgs(model_name=model_name, **common)
    if provider == "openai":
        return OpenAIModelArgs(model_name=model_name, **common)
    if provider == "gemini":
        return LiteLLMModelArgs(model_name=f"gemini/{model_name}", **common)
    if provider == "ollama":
        bare = model_name.split("/", 1)[1] if model_name.startswith("ollama/") \
            else model_name.split(":", 1)[1] if model_name.startswith("ollama:") \
            else model_name
        return OllamaModelArgs(model_name=f"ollama_chat/{bare}", **common)
    # groq / everything else — LiteLLM's groq route, same catch-all as helpers.llm
    return LiteLLMModelArgs(model_name=f"groq/{model_name}", **common)


def miniweb_agent(model_name: str = DEFAULT_MODEL,
                  visual: bool = True,
                  max_total_tokens: int = 32000,
                  max_new_tokens: int = 2000) -> GenericAgentArgs:
    flags = FLAGS_MINIWEB.copy()
    if not visual:
        flags.obs.use_screenshot = False
        flags.obs.use_som = False
    return GenericAgentArgs(
        chat_model_args=make_model_args(model_name, max_total_tokens, max_new_tokens),
        flags=flags,
    )


# ready-made config for `agentlab-assistant --agent_config ...` (see module doc)
MINIWEB_ASSISTANT_AGENT = miniweb_agent()
