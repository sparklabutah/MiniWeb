#!/usr/bin/env bash
# Option A multi-GPU eval: one ollama server + one eval runner PER GPU.
# Each model is pinned to one GPU via CUDA_VISIBLE_DEVICES, reached on its own
# ollama port, and graded by its own runner on its own Flask port. No code
# changes needed — this is pure orchestration around run_agent_verify.py.
#
# Usage:
#   evaluation/run_multi_gpu.sh ollama/llama3.3 ollama/qwen2.5 ollama/mistral
#     (arg N -> GPU N). With no args, uses the DEFAULT_MODELS below.
#
# Env knobs:
#   TASKS=all            # "all" | "site:banking" | '["Minh/e-commerce_224c4c", ...]'
#   OBS=axtree           # axtree | html | visual
#   BASE_OLLAMA_PORT=11434
#   BASE_FLASK_PORT=8101
#   PY=~/.conda/envs/miniweb/bin/python
set -uo pipefail
cd "$(dirname "$0")/.."                     # repo root

PY="${PY:-$HOME/.conda/envs/miniweb/bin/python}"
TASKS="${TASKS:-all}"
OBS="${OBS:-axtree}"
BASE_OLLAMA_PORT="${BASE_OLLAMA_PORT:-11434}"
BASE_FLASK_PORT="${BASE_FLASK_PORT:-8101}"
DEFAULT_MODELS=( "ollama/llama3.3" "ollama/qwen2.5" "ollama/mistral" )

MODELS=( "$@" ); [ ${#MODELS[@]} -eq 0 ] && MODELS=( "${DEFAULT_MODELS[@]}" )

STAMP=$(date +%Y%m%d_%H%M%S)
OUT="evaluation/results/multigpu_${STAMP}"
CFGDIR="scratchpad/mgpu_cfg"
mkdir -p "$OUT" "$CFGDIR"
echo "GPUs/models: ${MODELS[*]}"
echo "tasks=$TASKS obs=$OBS  ->  $OUT"

pids=()
for i in "${!MODELS[@]}"; do
  model="${MODELS[$i]}"; short="${model##*/}"
  oport=$((BASE_OLLAMA_PORT + i)); fport=$((BASE_FLASK_PORT + i))
  ohost="127.0.0.1:${oport}"

  # 1) ollama server pinned to GPU i (start only if its port isn't already up)
  if ! curl -sf "http://${ohost}/api/tags" >/dev/null 2>&1; then
    echo "[gpu $i] starting ollama on ${ohost}  (CUDA_VISIBLE_DEVICES=$i)"
    CUDA_VISIBLE_DEVICES=$i OLLAMA_HOST="$ohost" nohup ollama serve \
        > "$OUT/ollama_gpu${i}.log" 2>&1 &
    for _ in $(seq 1 60); do
      curl -sf "http://${ohost}/api/tags" >/dev/null 2>&1 && break; sleep 1
    done
  else
    echo "[gpu $i] reusing ollama already on ${ohost}"
  fi

  # 2) make sure the model is present on that server
  echo "[gpu $i] pull ${short}"
  OLLAMA_HOST="$ohost" ollama pull "$short" >> "$OUT/ollama_gpu${i}.log" 2>&1 || \
    echo "[gpu $i] WARN: pull failed (model may already exist / name mismatch)"

  # 3) one-model config for this GPU
  cfg="$CFGDIR/gpu${i}_${short}.json"
  TASKS="$TASKS" OBS="$OBS" "$PY" - "$cfg" "$model" "$short" "$OUT" <<'PYCFG'
import json, os, sys
cfg, model, short, out = sys.argv[1:5]
t = os.environ["TASKS"].strip()
tasks = json.loads(t) if t.startswith("[") else t          # list or "all"/"site:x"
json.dump({"agents": [{"model": model, "label": short, "obs": os.environ["OBS"]}],
           "tasks": tasks, "harness": "browser-use", "grade": "verifier",
           "out": f"{out}/{short}"}, open(cfg, "w"), indent=1)
PYCFG

  # 4) runner: OLLAMA_HOST -> this GPU's server, its own Flask port
  echo "[gpu $i] runner: $model  ->  ollama ${ohost}, flask ${fport}"
  OLLAMA_HOST="$ohost" nohup "$PY" evaluation/run_agent_verify.py \
      --config "$cfg" --port "$fport" \
      > "$OUT/runner_gpu${i}_${short}.log" 2>&1 &
  pids+=($!)
done

echo "launched ${#pids[@]} runners; waiting (tail -f $OUT/runner_gpu*.log to watch)"
rc=0
for p in "${pids[@]}"; do wait "$p" || rc=1; done
echo "all runners done (rc=$rc). results + logs under $OUT/"
echo "note: ollama servers are left running for reuse — stop with: pkill -f 'ollama serve'"
exit $rc
