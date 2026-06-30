#!/usr/bin/env bash
# =============================================================================
# Submit MiniWeb batch evaluation as a SLURM job.
#
# Usage:
#   bash scripts/submit_eval.sh                          # all sites, gpt model
#   bash scripts/submit_eval.sh -- --model gemini-flash  # all sites, gemini
#   bash scripts/submit_eval.sh -- --sites "news weather" --model gpt
#   bash scripts/submit_eval.sh -- --new-only            # skip already-evaluated
#   bash scripts/submit_eval.sh -- --dry-run             # preview only
#
# All arguments after -- are passed to run_batch_eval.sh.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Parse submit-level args (before --)
PARTITION="kmarino-gpu-grn"
QOS="kmarino-gpu-grn"
ACCOUNT="kmarino"
TIME="12:00:00"
MEM="60G"
NTASKS=1
JOB_NAME="miniweb-eval"

# Collect args after -- for run_batch_eval.sh
EVAL_ARGS=""
FOUND_SEP=false
for arg in "$@"; do
    if [ "$FOUND_SEP" = true ]; then
        EVAL_ARGS="$EVAL_ARGS $arg"
    elif [ "$arg" = "--" ]; then
        FOUND_SEP=true
    fi
done

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_DIR="$PROJECT_ROOT/evaluation/logs"
mkdir -p "$LOG_DIR"
SLURM_LOG="$LOG_DIR/slurm_${TIMESTAMP}_%j.log"

echo "============================================================"
echo "  MiniWeb Batch Eval — SLURM Submission"
echo "============================================================"
echo "  Partition:   $PARTITION"
echo "  Time limit:  $TIME"
echo "  Memory:      $MEM"
echo "  Eval args:   $EVAL_ARGS"
echo "  Log:         $SLURM_LOG"
echo "============================================================"
echo

# Submit
JOB_ID=$(sbatch \
    --partition="$PARTITION" \
    --qos="$QOS" \
    --account="$ACCOUNT" \
    --time="$TIME" \
    --ntasks="$NTASKS" \
    --mem="$MEM" \
    --job-name="$JOB_NAME" \
    --output="$SLURM_LOG" \
    --error="$SLURM_LOG" \
    --export=ALL \
    --wrap="cd $PROJECT_ROOT && bash scripts/run_batch_eval.sh $EVAL_ARGS" \
    --parsable)

echo "Submitted job $JOB_ID"
echo "Monitor: tail -f $LOG_DIR/slurm_${TIMESTAMP}_${JOB_ID}.log"
echo "Status:  squeue -u $(whoami) -j $JOB_ID"
echo "Cancel:  scancel $JOB_ID"
