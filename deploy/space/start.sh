#!/bin/sh
# The demo's entry point (deploy/space/Dockerfile): rebuild the data from the Hugging Face release, then serve.
# A Space's disk does not survive a restart, so every start begins from the released data.
# MINIWEB_DEMO_MEDIA=0 skips the 8 GB of site images (pages then load them from their original links).
set -e
cd "$(dirname "$0")/../.."
if [ "${MINIWEB_DEMO_MEDIA:-1}" = "0" ]; then
    python scripts/demo_setup.py --no-media
else
    python scripts/demo_setup.py
fi
D="$PWD/data/demo"
export MINIWEB_DEMO=1 MINIWEB_DB="$D/miniweb.db" MINIWEB_DATA_STATIC="$D/static" MINIWEB_MEDIA_DIR="$D/media" \
       MINIWEB_ANNOTATIONS_DIR="$D/annotations" MINIWEB_TRANSLATION_REPLAY="$D/translation_replay.json"
# one worker: the request logs the verifiers read live in the worker's memory (as in the main Dockerfile)
exec gunicorn run:app --bind "0.0.0.0:${PORT:-7860}" --workers 1 --threads 8 --timeout 120
