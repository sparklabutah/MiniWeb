#!/usr/bin/env bash
# =============================================================================
# Batch browser-agent evaluation for all built MiniWeb sites.
#
# Usage:
#   # Option A: Submit as batch job (recommended):
#   bash scripts/submit_eval.sh [-- OPTIONS]
#
#   # Option B: Interactive allocation (no GPU needed):
#   salloc --partition=kmarino-gpu-grn --qos=kmarino-gpu-grn --account=kmarino \
#          --time=06:00:00 --ntasks=1 --mem=60G
#   bash scripts/run_batch_eval.sh [OPTIONS]
#
# Options:
#   --model MODEL         LLM backend (default: gpt)
#   --workers N           Parallel browser instances per site (default: 4)
#   --max-steps N         Max agent steps per task (default: 20)
#   --rounds N            Browser-eval rounds per site (default: 3)
#   --sites "a b c"       Only eval these sites (default: all built sites)
#   --port-start N        Starting port for Flask servers (default: 8090)
#   --parallel N          Sites to eval simultaneously (default: 2)
#   --site-timeout N      Max seconds per site eval (default: 1800 = 30 min)
#   --task-timeout N      Max seconds per task (default: 180 = 3 min)
#   --judge               Use LLM-as-judge instead of verifiers.py
#   --judge-model MODEL   Model for LLM judge (default: gpt-4.1-nano)
#   --new-only            Skip sites that already have eval results
#   --dry-run             Print what would run without executing
# =============================================================================
set -uo pipefail
# NOTE: not using set -e because background jobs may return non-zero
# (e.g., eval failures, timeouts) and we want to continue processing

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Defaults
MODEL="gpt"
WORKERS=6
MAX_STEPS=20
ROUNDS=1
PORT_START=8090
PARALLEL=6
JUDGE=false
JUDGE_MODEL="gpt-4.1-nano"
DRY_RUN=false
NEW_ONLY=false
SITES=""
SITE_TIMEOUT=1800     # 30 min per site
TASK_TIMEOUT=180      # 3 min per task
DATA_SOURCES="/scratch/general/vast/u1653932/data_sources"

# Helper: check that a flag has a value argument
require_arg() {
    if [[ $# -lt 2 || "$2" == --* ]]; then
        echo "Error: $1 requires a value"; exit 1
    fi
}

# Parse args
while [[ $# -gt 0 ]]; do
    case $1 in
        --model) require_arg "$@"; MODEL="$2"; shift 2 ;;
        --workers) require_arg "$@"; WORKERS="$2"; shift 2 ;;
        --max-steps) require_arg "$@"; MAX_STEPS="$2"; shift 2 ;;
        --rounds) require_arg "$@"; ROUNDS="$2"; shift 2 ;;
        --sites) require_arg "$@"; SITES="$2"; shift 2 ;;
        --port-start) require_arg "$@"; PORT_START="$2"; shift 2 ;;
        --parallel) require_arg "$@"; PARALLEL="$2"; shift 2 ;;
        --site-timeout) require_arg "$@"; SITE_TIMEOUT="$2"; shift 2 ;;
        --task-timeout) require_arg "$@"; TASK_TIMEOUT="$2"; shift 2 ;;
        --judge) JUDGE=true; shift ;;
        --judge-model) require_arg "$@"; JUDGE_MODEL="$2"; shift 2 ;;
        --new-only) NEW_ONLY=true; shift ;;
        --dry-run) DRY_RUN=true; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# Find conda
CONDA_BIN="/scratch/general/vast/u1653932/miniforge3/condabin/conda"
PYTHON="$CONDA_BIN run -n miniweb-eval python -u"

# Load env vars
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
fi

# Discover built sites (have tasks.json)
if [ -z "$SITES" ]; then
    SITES=""
    for site_dir in sites/*/; do
        site=$(basename "$site_dir")
        [[ "$site" == _* ]] && continue
        [[ "$site" == __* ]] && continue
        [ -f "$site_dir/tasks.json" ] || continue
        SITES="$SITES $site"
    done
fi

# Filter to new-only if requested (skip sites with existing results/)
if [ "$NEW_ONLY" = true ]; then
    FILTERED=""
    for site in $SITES; do
        if [ -d "sites/$site/results" ] && ls sites/$site/results/*/results.json &>/dev/null; then
            echo "  SKIP (already evaluated): $site"
        else
            FILTERED="$FILTERED $site"
        fi
    done
    SITES="$FILTERED"
fi

SITE_LIST=($SITES)
TOTAL=${#SITE_LIST[@]}

echo "============================================================"
echo "  MiniWeb Batch Evaluation"
echo "============================================================"
echo "  Model:        $MODEL"
echo "  Workers:      $WORKERS per site"
echo "  Max steps:    $MAX_STEPS per task"
echo "  Task timeout: ${TASK_TIMEOUT}s per task"
echo "  Site timeout: ${SITE_TIMEOUT}s per site"
echo "  Rounds:       $ROUNDS per site"
echo "  Parallel:     $PARALLEL sites simultaneously"
echo "  Judge:        $JUDGE (model: $JUDGE_MODEL)"
echo "  Sites:        $TOTAL"
echo "  Sites list:   ${SITE_LIST[*]}"
echo "============================================================"
echo

if [ "$DRY_RUN" = true ]; then
    echo "[DRY RUN] Would evaluate these sites:"
    PORT=$PORT_START
    for site in "${SITE_LIST[@]}"; do
        echo "  $site (port $PORT)"
        PORT=$((PORT + 1))
    done
    exit 0
fi

# Log file
LOG_DIR="$PROJECT_ROOT/evaluation/logs"
mkdir -p "$LOG_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
MASTER_LOG="$LOG_DIR/batch_${MODEL}_${TIMESTAMP}.log"

echo "Logging to: $MASTER_LOG"
echo "Start time: $(date)" | tee "$MASTER_LOG"

# Update TASK_TIMEOUT in tasks.py to match our setting
sed -i "s/^TASK_TIMEOUT = .*/TASK_TIMEOUT = $TASK_TIMEOUT  # seconds per task/" evaluation/tasks.py

# Site-ID to data_sources directory mapping (where they differ)
declare -A DATA_DIR_MAP=(
    ["academic-paper-db"]="arxiv"
    ["comparison-aggregators"]="gsmarena"
    ["conference-review-submission"]="PeerRead"
    ["dictionaries-language-tools"]="wikidictionary"
    ["e-commerce"]="webshop"
    ["email"]="enron"
    ["forums"]="reddit-augment"
    ["health-fitness-tracking"]="health-fitness"
    ["job-sites"]="indeed-jobs-augment"
    ["live"]="live"
    ["petitions-voting-info"]="petitions-voting"
    ["qa-knowledge"]="stackexchange-augment"
    ["ride-hailing-delivery"]="ride-hailing"
    ["tax-filing-dmv-permits"]="tax-dmv"
    ["team-chat-workspace"]="team-chat"
    ["version-control"]="gitlab-augment"
)

# Resolve data_sources directory for a site
get_data_dir() {
    local site=$1
    local mapped="${DATA_DIR_MAP[$site]:-}"
    if [ -n "$mapped" ]; then
        echo "$DATA_SOURCES/$mapped"
    elif [ -d "$DATA_SOURCES/$site" ]; then
        echo "$DATA_SOURCES/$site"
    else
        echo ""
    fi
}

# Reset all site data to pristine before starting
echo "Resetting all site data to pristine..." | tee -a "$MASTER_LOG"
for site in "${SITE_LIST[@]}"; do
    data_dir=$(get_data_dir "$site")
    if [ -n "$data_dir" ] && [ -d "$data_dir/.pristine" ]; then
        for f in "$data_dir/.pristine"/*.json; do
            [ -f "$f" ] && cp "$f" "$data_dir/$(basename "$f")"
        done
    fi
done

# Kill any leftover processes on a port
kill_port() {
    local port=$1
    local pids
    pids=$(lsof -ti ":$port" 2>/dev/null) || true
    if [ -n "$pids" ]; then
        echo "$pids" | xargs kill -9 2>/dev/null || true
        sleep 1
    fi
}

# Run a single site eval with timeout
run_site_eval() {
    local site=$1
    local port=$2
    local round=$3
    local site_log="$LOG_DIR/${site}_${MODEL}_r${round}_${TIMESTAMP}.log"

    echo "[$(date +%H:%M:%S)] Starting $site round $round on port $port" | tee -a "$MASTER_LOG"

    # Reset data before each round
    local data_dir
    data_dir=$(get_data_dir "$site")
    if [ -n "$data_dir" ] && [ -d "$data_dir/.pristine" ]; then
        for f in "$data_dir/.pristine"/*.json; do
            [ -f "$f" ] && cp "$f" "$data_dir/$(basename "$f")"
        done
    fi

    # Kill anything on the port first
    kill_port "$port"

    # Build judge flags
    local judge_flags=""
    if [ "$JUDGE" = true ]; then
        judge_flags="--judge --judge-model $JUDGE_MODEL"
    fi

    # Run with site-level timeout
    timeout --kill-after=30 "$SITE_TIMEOUT" \
        $PYTHON evaluation/run_eval.py \
            --site "$site" \
            --model "$MODEL" \
            --port "$port" \
            --workers "$WORKERS" \
            --max-steps "$MAX_STEPS" \
            $judge_flags \
            > "$site_log" 2>&1

    local exit_code=$?

    # Clean up: kill the flask server on this port
    kill_port "$port"

    # Extract pass rate from output
    local pass_rate=$(grep -oP '\d+/\d+ passed \(\K[0-9.]+' "$site_log" 2>/dev/null || echo "?")

    if [ $exit_code -eq 0 ]; then
        echo "[$(date +%H:%M:%S)] DONE $site round $round: ${pass_rate}% (log: $site_log)" | tee -a "$MASTER_LOG"
    elif [ $exit_code -eq 124 ]; then
        echo "[$(date +%H:%M:%S)] TIMEOUT $site round $round: killed after ${SITE_TIMEOUT}s (log: $site_log)" | tee -a "$MASTER_LOG"
    else
        echo "[$(date +%H:%M:%S)] FAIL $site round $round: exit=$exit_code (log: $site_log)" | tee -a "$MASTER_LOG"
    fi

    # Always return 0 so background wait doesn't kill the parent script
    return 0
}

# Main evaluation loop
COMPLETED=0
FAILED=0

for round in $(seq 1 $ROUNDS); do
    echo "" | tee -a "$MASTER_LOG"
    echo "==================== Round $round/$ROUNDS ====================" | tee -a "$MASTER_LOG"

    # Process sites in batches of $PARALLEL
    i=0
    while [ $i -lt $TOTAL ]; do
        PIDS=()

        # Launch batch
        for j in $(seq 0 $((PARALLEL - 1))); do
            idx=$((i + j))
            [ $idx -ge $TOTAL ] && break
            site="${SITE_LIST[$idx]}"
            port=$((PORT_START + j))

            run_site_eval "$site" "$port" "$round" &
            PIDS+=($!)
        done

        # Wait for batch to complete
        for pid in "${PIDS[@]}"; do
            wait "$pid" 2>/dev/null
            if [ $? -eq 0 ]; then
                COMPLETED=$((COMPLETED + 1))
            else
                FAILED=$((FAILED + 1))
            fi
        done

        i=$((i + PARALLEL))
    done
done

echo "" | tee -a "$MASTER_LOG"
echo "============================================================" | tee -a "$MASTER_LOG"
echo "  Batch evaluation complete" | tee -a "$MASTER_LOG"
echo "  Total runs: $((TOTAL * ROUNDS))" | tee -a "$MASTER_LOG"
echo "  Completed:  $COMPLETED" | tee -a "$MASTER_LOG"
echo "  Failed:     $FAILED" | tee -a "$MASTER_LOG"
echo "  End time:   $(date)" | tee -a "$MASTER_LOG"
echo "============================================================" | tee -a "$MASTER_LOG"

# Generate summary
echo "" | tee -a "$MASTER_LOG"
echo "Per-site best results:" | tee -a "$MASTER_LOG"
for site in "${SITE_LIST[@]}"; do
    latest=$(ls -td "sites/$site/results/${MODEL}_"* 2>/dev/null | head -1)
    if [ -n "$latest" ] && [ -f "$latest/results.json" ]; then
        rate=$($PYTHON -c "import json; d=json.load(open('$latest/results.json')); print(f'{d[\"passed\"]}/{d[\"total\"]} ({d[\"pass_rate\"]}%)')" 2>/dev/null || echo "?")
        echo "  $site: $rate" | tee -a "$MASTER_LOG"
    else
        echo "  $site: no results" | tee -a "$MASTER_LOG"
    fi
done
