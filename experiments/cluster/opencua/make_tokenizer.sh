#!/bin/bash
# Build $WEBMIX_ROOT/opencua_tokenizer (see NOTE.txt): the HF snapshot's tokenizer files with this folder's
# tokenizer_config.json (no unk_token / pad_token). Needs the xlangai/OpenCUA-7B snapshot in $WEBMIX_ROOT/hf.
set -e
B=${WEBMIX_ROOT:?set WEBMIX_ROOT}
SNAP=$(ls -d $B/hf/hub/models--xlangai--OpenCUA-7B/snapshots/*/ | head -1)
mkdir -p $B/opencua_tokenizer
cp $SNAP/tokenization_opencua.py $SNAP/tiktoken.model $B/opencua_tokenizer/
cp "$(dirname "$0")/tokenizer_config.json" "$(dirname "$0")/NOTE.txt" $B/opencua_tokenizer/
echo "built $B/opencua_tokenizer from $SNAP"
