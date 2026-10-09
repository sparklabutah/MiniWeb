#!/bin/bash
# Reset the given WebArena instances (default 1-4), then wait until every site serves. A site still down 15 min after
# its reset (GitLab, twice in our runs) gets its own reset and another wait. Instance i serves shopping, shopping_admin,
# reddit and gitlab on ports 8081+100(i-1) .. +3 of WA_HOST; miniwebagent.wa reads the same layout.
H=${WA_HOST:-127.0.0.1}
TOKEN=${WA_RESET_TOKEN:?set WA_RESET_TOKEN to the reset API token}
INST="${@:-1 2 3 4}"
"$(dirname "$0")/reset.sh" $INST
serving() { [ "$(curl -s -m 30 -o /dev/null -w '%{http_code}' "$1")" = "200" ]; }
wait_url() { for k in $(seq 1 30); do serving "$1" && return 0; sleep 30; done; return 1; }
for i in $INST; do
  b=$((8081 + (i - 1) * 100))
  for site in shopping:$b/ shopping_admin:$((b + 1))/admin reddit:$((b + 2))/forums/all gitlab:$((b + 3))/users/sign_in; do
    name=${site%%:*}; u="http://$H:${site#*:}"
    if ! wait_url "$u"; then
      echo "instance $i: $name still down after 15 min; resetting it again"
      curl -s -m 900 -X POST -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:$((8090 + i))/reset/$name" | head -c 200; echo
      wait_url "$u" || { echo "instance $i: $name DOWN"; exit 1; }
    fi
  done
  echo "instance $i: all sites serving"
done
