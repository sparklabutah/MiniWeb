# Shared settings of the cluster wrappers (sourced). WEBMIX_ROOT is a work folder holding:
#   miniweb/        this repository            env/   the webmix env (vLLM 0.30, torch 2.13, peft 0.21, transformers 5.17)
#   menv/           the miniweb env            hf/    the Hugging Face cache (models downloaded beforehand; runs offline)
#   ms-playwright/chromium-1117/               adapters/  rows/  eval/  om2w/runs/  logs/
B=${WEBMIX_ROOT:?set WEBMIX_ROOT to the work folder described in src/miniwebagent/scripts/cluster/env.sh}
export HF_HOME=$B/hf HF_HUB_OFFLINE=1 PYTHONPATH=$B/miniweb/src   # the src/ layout
export DATAGEN_CHROME=$B/ms-playwright/chromium-1117/chrome-linux/chrome
export DBUS_SYSTEM_BUS_ADDRESS=unix:path=/dev/null DBUS_SESSION_BUS_ADDRESS=unix:path=/dev/null
mkdir -p $B/logs
# MiniWeb's SQLite file must not live on NFS (WAL is unsafe there): one node-local copy per job.
node_db() {
  DB=${TMPDIR:-/tmp}/miniweb.db
  exec 9>$DB.lock; flock 9
  [ -f $DB ] || { cp $B/miniweb/data/miniweb.db $DB.part && mv $DB.part $DB; }
  flock -u 9
  export MINIWEB_DB=$DB
}
# Start src/miniwebagent/scripts/serve.sh in the background and wait until it serves (or fails): serve <log> [VAR=value ...]
serve() {
  local log=$1; shift
  : > $log                                      # truncate first: an old run's Traceback would end the wait at once
  env "$@" WEBMIX_ENV=$B/env setsid bash src/miniwebagent/scripts/serve.sh > $log 2>&1 &
  VP=$!
  trap "kill -- -$VP 2>/dev/null" EXIT
  until grep -qE "Application startup complete|Traceback" $log || ! kill -0 $VP 2>/dev/null; do sleep 5; done
  grep -q "Application startup complete" $log || { echo "vLLM failed: $log"; exit 1; }
}
