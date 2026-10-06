#!/bin/bash -l
# RQ1 own-loop baselines on one GPU: the agent's released loop (webmix/ownloop_runner.py) against MiniWeb.
#   ownloop.sh <gpu> <vllm port> <model> <served> <agent: uitars|molmoweb|fara7b|opencua> <out name> <miniweb ports> [args]
# The run folder must hold tasks.json (python -m webmix.fara_rq1 prep --out <run> --split all); grade where the API
# keys are: python -m webmix.fara_rq1 grade --out <run> --arm <served>. Serving defaults per agent (env overrides them):
#   uitars    MM_LIMIT {"image": 5}: the agent sends its last 5 screenshots
#   molmoweb  --trust-remote-code (Molmo2's processor), bf16 (the checkpoints are fp32), causal attention on image tokens
#             (vLLM serves Molmo2 as a prefix LM; MolmoWeb is trained causal), MAX_MODEL_LEN 10240
#   fara7b    MM_LIMIT {"image": 3}: Fara-7B sends its last 3 screenshots
#   opencua   --trust-remote-code with the tokenizer of experiments/cluster/opencua (see its NOTE.txt) and the vLLM plugin
#             in experiments/cluster/opencua/plugin, on this server only
# Agent code on sys.path (OWNLOOP_PATH): microsoft/fara a675d6d (src) + browserbase 1.20.0, xlang-ai/OSWorld b138d34
# (mm_agents/opencua) + loguru. Fara1.5-4B runs in its own venv instead (webmix/fara_runner.py).
source "$(dirname "$0")/env.sh"
GPU=$1; VPORT=$2; MODEL=$3; SERVED=$4; AGENT=$5; NAME=$6; PORTS=$7; shift 7
HERE=$B/miniweb/experiments/cluster
node_db
SERVE_ENV=(CUDA_VISIBLE_DEVICES=$GPU PORT=$VPORT MODEL=$MODEL SERVED=$SERVED NO_LORA=1 CHAT_KWARGS=none)
case "$AGENT" in
  uitars)   SERVE_ENV+=(MM_LIMIT="${MM_LIMIT:-{\"image\": 5, \"video\": 0\}}") ;;
  molmoweb) SERVE_ENV+=(EXTRA_ARGS="${EXTRA_ARGS:---trust-remote-code --dtype bfloat16 --hf-overrides {\"is_mm_prefix_lm\":false\}}"
                        MAX_MODEL_LEN="${MAX_MODEL_LEN:-10240}") ;;
  fara7b)   SERVE_ENV+=(MM_LIMIT="${MM_LIMIT:-{\"image\": 3, \"video\": 0\}}") ;;
  opencua)  SERVE_ENV+=(MM_LIMIT="${MM_LIMIT:-{\"image\": 3, \"video\": 0\}}" PYTHONPATH=$HERE/opencua/plugin
                        EXTRA_ARGS="${EXTRA_ARGS:---trust-remote-code --tokenizer $B/opencua_tokenizer}") ;;
  *) echo "unknown agent $AGENT"; exit 2 ;;
esac
cd $B/miniweb
serve $B/logs/vllm_$NAME.log "${SERVE_ENV[@]}"
echo "$(date +%F\ %T) $AGENT $NAME ($MODEL) on GPU $GPU, vLLM :$VPORT, MiniWeb $PORTS: $*"
$B/menv/bin/python -m webmix.ownloop_runner $AGENT --tasks $B/eval/$NAME/tasks.json --out $B/eval/$NAME --ports $PORTS \
  --endpoint http://127.0.0.1:$VPORT/v1 --model $SERVED --path "${OWNLOOP_PATH:-$B/fara7b_pkgs:$B/fara/src:$B/opencua_pkgs:$B/osworld}" "$@"
echo "$(date +%F\ %T) OWNLOOP_DONE $NAME"
