#!/bin/bash -l
# Train an adapter: train.sh <gpu list, e.g. 0,1,2,3> <rows folder> <adapter name> [miniwebagent.train args ...]
# (python scripts/reproduce.py train <adapter> prints the paper's arguments). Several can run at once on disjoint GPU lists.
source "$(dirname "$0")/env.sh"
GPUS=$1; ROWS=$2; NAME=$3; shift 3
export CUDA_VISIBLE_DEVICES=$GPUS WEBMIX_REPLAY_DIR=$ROWS LD_LIBRARY_PATH=$B/env/lib:$LD_LIBRARY_PATH
export TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=4 TRITON_CACHE_DIR=${TMPDIR:-/tmp}/triton_$NAME WANDB_DIR=$B/wandb
N=$(echo $GPUS | tr "," "\n" | wc -l)
cd $B/miniweb
echo "$(date +%F\ %T) $NAME on GPUs $GPUS ($N): $*"
exec $B/env/bin/torchrun --standalone --nproc_per_node $N -m miniwebagent.train --out $B/adapters/$NAME "$@"
