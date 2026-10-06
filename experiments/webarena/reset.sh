#!/bin/bash
# Reset every mutable site of the given WebArena instances (default 1-4) in parallel, through each instance's reset API
# (ScaleCUA WebArenaLiteV2/reset-api, http://127.0.0.1:<8090+i>). The API token comes from WA_RESET_TOKEN (never stored).
TOKEN=${WA_RESET_TOKEN:?set WA_RESET_TOKEN to the reset API token}
L=${WA_LOG_DIR:-data/webmix/logs}; mkdir -p $L
for i in ${@:-1 2 3 4}; do
  ( t0=$(date +%s); curl -s -m 1500 -X POST -H "Authorization: Bearer $TOKEN" http://127.0.0.1:$((8090+i))/reset > $L/wa_reset_$i.json
    echo "instance $i reset exit=$? in $(( $(date +%s)-t0 ))s" ) &
done
wait
