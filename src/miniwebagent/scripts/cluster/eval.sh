#!/bin/bash -l
# One MiniWeb run on one GPU: a vLLM server with the given LoRAs, then miniwebagent.evaluate.
#   eval.sh <gpu> <vllm port> "<lora name=path ...>" <out name> <miniweb ports, e.g. 8300,8301> [miniwebagent.evaluate args ...]
# Env: MAX_LORAS (8), MAX_LORA_RANK (64); MODEL / SERVED / NO_LORA / EXTRA_ARGS / CHAT_KWARGS for other models (RQ1).
# There are no API keys on the cluster, so the answer checks' LLM tier is off here (VERIFIER_JUDGE_MODEL=none):
# re-grade the run where keys are, with `python -m miniwebagent.evaluate --regrade <run> --out <run>`.
source "$(dirname "$0")/env.sh"
GPU=$1; VPORT=$2; LORAS=$3; NAME=$4; PORTS=$5; shift 5
node_db
cd $B/miniweb
serve $B/logs/vllm_$NAME.log CUDA_VISIBLE_DEVICES=$GPU PORT=$VPORT LORA_MODULES="$LORAS" MAX_LORAS=${MAX_LORAS:-8} \
  MAX_LORA_RANK=${MAX_LORA_RANK:-64}
export VERIFIER_JUDGE_MODEL=none
echo "$(date +%F\ %T) eval $NAME on GPU $GPU, vLLM :$VPORT, MiniWeb $PORTS: $*"
$B/menv/bin/python -m miniwebagent.evaluate --vllm http://127.0.0.1:$VPORT/v1 --ports $PORTS --out $B/eval/$NAME "$@"
