#!/bin/bash -l
# Live-web runs, one component per Slurm step so restarting one never takes down the others:
#   live.sh serve <gpu> <port> <name> "<lora modules>"      a vLLM server (at most 24 browsers per server: more made
#                                                            LLM calls exceed the timeout)
#   live.sh run <run folder>[@part] <port> <workers> <webmix.om2w args ...>
# Judge where the API keys are: python -m webmix.om2w_judge <run> --bench webvoyager|om2w --workers 4
source "$(dirname "$0")/env.sh"
O=$B/om2w/runs
log() { echo "$(date '+%F %T') $*"; }
cd $B/miniweb
case "$1" in
  serve)
    log "serve $4 on GPU $2 :$3"
    CUDA_VISIBLE_DEVICES=$2 WEBMIX_ENV=$B/env PORT=$3 MAX_LORAS=8 MAX_LORA_RANK=64 LORA_MODULES="$5" \
      exec bash webmix/serve.sh > $B/logs/vllm_live_$4.log 2>&1 ;;
  run)
    label=$2; d=${2%@*}; port=$3; w=$4; shift 4      # <folder>@<tag>: one part of a run split across nodes (--slot-range)
    until curl -sf -m 10 http://127.0.0.1:$port/v1/models > /dev/null; do sleep 15; done
    log "start $label ($w browsers): $*"
    $B/menv/bin/python -m webmix.om2w "$@" --vllm http://127.0.0.1:$port/v1 --workers $w --out $O/$d >> $B/logs/live_${label/@/_}.log 2>&1
    log "done $label: $(tail -1 $B/logs/live_${label/@/_}.log)" ;;
  *) echo "usage: live.sh serve|run ..."; exit 2 ;;
esac
