#!/usr/bin/env bash
# vLLM for the WebMix arms: Qwen3.5 base + LoRA adapters on one server, one GPU.
#
#   bash webmix/serve.sh                                 # base only, port 8400
#   LORA_MODULES="drag=data/webmix/adapters/drag io=data/webmix/adapters/io" bash webmix/serve.sh
#
# Requests pick the adapter by the OpenAI `model` field (an adapter name, or the base's served name).
# JIT-free on this machine (no nvcc; settings from method/hyperWeb/scripts/startVLM_lora.sh):
# FlashAttention backend, PyTorch sampler, Triton GDN prefill. LD_LIBRARY_PATH: the env's own
# libstdc++ (the system one is older than its ICU needs). Thinking off: the chat template renders the
# same empty <think></think> block the training rows were tokenized with.
set -euo pipefail
ENV="${WEBMIX_ENV:-$HOME/.conda/envs/webmix}"
export LD_LIBRARY_PATH="$ENV/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PATH="$ENV/bin:$PATH"
export VLLM_USE_FLASHINFER_SAMPLER=0

MODEL="${MODEL:-Qwen/Qwen3.5-4B}"
SERVED="${SERVED:-qwen35-4b}"
PORT="${PORT:-8400}"
LORA_MODULES="${LORA_MODULES:-}"
EAGER="${EAGER:-1}"                  # 1 = no CUDA-graph capture (fast start; the pilot restarts often)

args=(serve "$MODEL" --host 127.0.0.1 --port "$PORT" --served-model-name "$SERVED"
      --max-model-len "${MAX_MODEL_LEN:-32768}" --gpu-memory-utilization "${GPU_UTIL:-0.85}"
      --limit-mm-per-prompt "${MM_LIMIT:-{\"image\": 1, \"video\": 0\}}"
      --attention-backend FLASH_ATTN --gdn-prefill-backend triton
      --enable-prefix-caching)
# NO_LORA=1: serve a model without LoRA support (the RQ1 baselines, 2026-10-03); EXTRA_ARGS: more vllm flags
# (e.g. --trust-remote-code for InternVL).
[ "${NO_LORA:-0}" = "1" ] || args+=(--enable-lora --max-lora-rank "${MAX_LORA_RANK:-16}" --max-loras "${MAX_LORAS:-4}")
# shellcheck disable=SC2206
[ -n "${EXTRA_ARGS:-}" ] && args+=(${EXTRA_ARGS})
# CHAT_KWARGS: chat-template kwargs; default thinking off (our training rows). CHAT_KWARGS=none keeps the model's own
# defaults (Fara1.5 as released, 2026-10-02). MM_LIMIT: images per prompt (Fara sends up to 3).
CHAT_KWARGS="${CHAT_KWARGS:-{\"enable_thinking\": false\}}"
[ "$CHAT_KWARGS" != "none" ] && args+=(--default-chat-template-kwargs "$CHAT_KWARGS")
[ "$EAGER" = "1" ] && args+=(--enforce-eager)
if [ -n "$LORA_MODULES" ]; then
  args+=(--lora-modules)
  for m in ${LORA_MODULES//,/ }; do args+=("$m"); done
fi
exec vllm "${args[@]}"
