"""Train one WebMix LoRA adapter on replayed browser-use rows (runs in the `webmix` env).

    python -m webmix.train --adapter drag            # family adapter: CE on its rows, KL anchor on the rest
    python -m webmix.train --adapter pooled          # one adapter on every family's rows, no anchor

Rows: data/webmix/replay/<task>/rows.jsonl (webmix.replay; browser-use's own prompt + screenshot ->
the flash-mode JSON it answered). Each row is a family's by the macro segment it came from.

Loss (WebMix's row-disjoint KL anchor, method/hyperWeb/integrations/llamafactory-kl.patch
`disjoint_kl_loss`, re-implemented here because that patch targets a LLaMA-Factory fork): a row is
either a CE row (the adapter's own families: mean -log p(target token)) or a KL row (other families,
`--anchor-ratio` of them per CE row, redrawn every epoch: the k3 estimate exp(d) - d - 1 with
d = log p_ref - log p_theta on the target's action tokens (not the templated memory, see
`action_mask`), clamped to [-20, 8], weighted by --beta). The
reference is the same model with the adapter disabled, so no second copy is loaded.

Recipe (WebMix default): rank 16, alpha 32, dropout 0.05, attention + MLP projections of the language
model only (targets.py `attn_mlp`: q/k/v/o on the full-attention layers, gate/up/down on every
layer; no vision tower, no DeltaNet projections), lr 1e-4 cosine, AdamW. Batch 1 x grad-accum.
Only the target positions' logits are computed (`logits_to_keep`): a 248k-token vocabulary over a
~6.6k-token prompt would not fit otherwise.

Multi-GPU (granite, 4x A800, 2026-09-30): `torchrun --nproc_per_node N -m webmix.train ...` gives each rank a
disjoint share of every epoch's rows and sums the LoRA gradients across ranks at each optimizer step (one
flat all-reduce; no DDP wrapper, so KL rows' adapter-off forwards need no special handling). --grad-accum
stays the GLOBAL batch in rows, so a run's recipe does not depend on the GPU count. Rows are encoded
(screenshot decode + tokenization) in background threads ahead of the GPU.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import math
import random
import time
from pathlib import Path

from webmix import REPLAY_DIR

ROOT = Path(__file__).resolve().parent.parent
ROWS_DIR = REPLAY_DIR
OUT_DIR = ROOT / "data" / "webmix" / "adapters"
MODEL = os.environ.get("WEBMIX_BASE_MODEL", "Qwen/Qwen3.5-4B")   # e.g. microsoft/Fara1.5-4B (RQ2 init swap), Qwen/Qwen3.5-9B

FAMILIES = ["Drag & gesture", "Discrete selection", "Text entry", "Form transaction", "Navigation",
            "Out-of-page I/O", "Reasoning base"]
# the one-5090 pilot (design doc "Pilot on one 5090"): three family adapters + one pooled over the rest
ADAPTERS = {
    "pooled": FAMILIES,
    "drag": ["Drag & gesture"],
    "io": ["Out-of-page I/O"],
    "select": ["Discrete selection"],
    "rest": ["Text entry", "Form transaction", "Navigation", "Reasoning base"],
    "planner": ["planner"],          # the macro planner (webmix.planner rows), no anchor
    # reasoning steps and final answers (user, 2026-09-30): rows from rejection sampling on the train-site human
    # reasoning tasks (webmix.evaluate --record-rows), KL-anchored on the synthetic families' rows
    "reasoning": ["Reasoning base"],
}
PLANNER_ROWS = ROOT / "data" / "webmix" / "planner" / "rows.jsonl"
TARGET_LEAVES = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
TARGET_RE = r".*language_model.*\.(" + "|".join(TARGET_LEAVES) + r")$"


def save_adapter(model, out):
    """PEFT writes the training regex into adapter_config.json; servers (vLLM) expect module names.
    The weights only cover language-model modules, so the leaf-name list is equivalent."""
    model.save_pretrained(out, selected_adapters=["default"])     # not the frozen anchor copy (--init-adapter)
    cfg_path = Path(out) / "adapter_config.json"
    cfg = json.loads(cfg_path.read_text())
    cfg["target_modules"] = TARGET_LEAVES
    cfg_path.write_text(json.dumps(cfg, indent=2))


def is_val(task_id, frac=0.05):
    """A fixed ~5% of trajectories (by task) held out for validation loss."""
    return int(hashlib.md5(task_id.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF < frac


def load_rows(rows_dir=ROWS_DIR):
    rows = []
    for p in sorted(rows_dir.glob("*/rows.jsonl")):
        if p.parent.name.startswith("_"):
            continue
        try:
            parts = json.loads((p.parent / "episode.json").read_text()).get("parts")
        except (OSError, ValueError):
            parts = None
        for line in p.read_text().split("\n"):
            if line.strip():
                r = json.loads(line)
                if r.get("inject") or r.get("aug_prefix"):
                    continue          # a recovery episode's injected mistake, and its prefix (a copy of the plain replay)
                r["dir"] = str(p.parent)
                if parts:
                    r["parts"] = parts
                rows.append(r)
    return rows


def in_frac(r, frac):
    """Scaling runs (2026-10-01): keep a fixed `frac` of the generated trajectories, whole episodes at a time (a
    recovery variant follows its source, a chain needs all its parts); nested across fractions, separate from the
    validation split."""
    if frac >= 1:
        return True
    key = lambda t: int(hashlib.md5(f"frac:{t}".encode()).hexdigest()[:8], 16) / 0xFFFFFFFF   # noqa: E731
    return all(key(t) < frac for t in (r.get("parts") or [_base_task(r["task_id"])]))


def in_ids(r, ids):
    """--episode-ids (skill-mix ablation, 2026-10-02): keep a row when its trajectory is listed (a recovery variant follows
    its source, a chain needs all its parts)."""
    return ids is None or all(t in ids for t in (r.get("parts") or [_base_task(r["task_id"])]))


def row_is_val(r):
    """Held out when its trajectory is (a recovery variant follows its source, a chain any of its parts)."""
    return any(is_val(t) for t in (r.get("parts") or [_base_task(r["task_id"])]))


# ── examples ──────────────────────────────────────────────────────────────────

def to_hf(row):
    """OpenAI-format messages (image parts point at files next to rows.jsonl) -> (HF messages, images)."""
    from PIL import Image
    msgs, imgs = [], []
    for m in row["messages"]:
        c = m["content"]
        if isinstance(c, str):
            msgs.append({"role": m["role"], "content": [{"type": "text", "text": c}]})
            continue
        parts = []
        for x in c:
            if x.get("type") == "text":
                parts.append({"type": "text", "text": x["text"]})
            elif x.get("type") == "image_url":
                imgs.append(Image.open(Path(row["dir"]) / x["image_url"]["url"]).convert("RGB"))
                parts.append({"type": "image"})
        msgs.append({"role": m["role"], "content": parts})
    return msgs, imgs


def encode(processor, row):
    """-> model inputs + labels (-100 on the prompt) + n_target (supervised tokens incl. <|im_end|>)."""
    msgs, imgs = to_hf(row)
    prompt = processor.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, enable_thinking=False)
    full = prompt + row["target"] + "<|im_end|>"
    kw = {"images": imgs} if imgs else {}
    enc = processor(text=[full], return_tensors="pt", **kw)
    n_prompt = processor(text=[prompt], return_tensors="pt", **kw)["input_ids"].shape[1]
    labels = enc["input_ids"].clone()
    labels[:, :n_prompt] = -100
    enc["labels"] = labels
    enc["n_target"] = n = enc["input_ids"].shape[1] - n_prompt
    enc["action_mask"] = action_mask(processor.tokenizer, row["target"], n)
    return enc


def action_mask(tokenizer, target, n):
    """(n,) bool over the target tokens: True from the "action" field on (incl. <|im_end|>). The KL
    anchor applies there only (the memory is written by the base model itself since cycle 3, so it needs
    no anchor), and --ce-on action restricts the CE to it. All True when the
    target's standalone tokenization does not line up with its tokens in context."""
    import torch
    t = tokenizer(target + "<|im_end|>", add_special_tokens=False, return_offsets_mapping=True)
    at = target.find('"action"')
    if len(t["input_ids"]) != n or at < 0:
        return torch.ones(n, dtype=torch.bool)
    return torch.tensor([end > at for _, end in t["offset_mapping"]], dtype=torch.bool)


def target_logprobs(model, enc, device):
    """log p(target token) at each supervised position, computing logits only for those positions."""
    import torch
    n = enc["n_target"]
    inputs = {k: v.to(device) for k, v in enc.items() if k not in ("labels", "n_target", "action_mask")}
    out = model(**inputs, logits_to_keep=n + 1, use_cache=False)
    logits = out.logits[:, :-1, :].float()                    # positions predicting the n target tokens
    tgt = enc["labels"][:, -n:].to(device)
    return torch.log_softmax(logits, dim=-1).gather(-1, tgt.unsqueeze(-1)).squeeze(-1)   # (1, n)


def prefetched(processor, items, workers=4, ahead=8):
    """Yield (item, encode(row)) in order, encoding up to `ahead` rows in background threads."""
    from collections import deque
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(workers) as ex:
        q, it = deque(), iter(items)
        for x in it:
            q.append((x, ex.submit(encode, processor, x[0])))
            if len(q) >= ahead:
                break
        while q:
            x, fut = q.popleft()
            nxt = next(it, None)
            if nxt is not None:
                q.append((nxt, ex.submit(encode, processor, nxt[0])))
            yield x, fut.result()


def _dist():
    """-> (rank, world, local_rank); initialises NCCL under torchrun."""
    import os
    world = int(os.environ.get("WORLD_SIZE", "1"))
    if world == 1:
        return 0, 1, 0
    import torch
    import torch.distributed as dist
    local = int(os.environ["LOCAL_RANK"])
    torch.cuda.set_device(local)
    from datetime import timedelta
    dist.init_process_group("nccl", timeout=timedelta(hours=1))      # rank 0 evaluates while the others wait
    return dist.get_rank(), world, local


def _allreduce_grads(params, world):
    import torch
    import torch.distributed as dist
    grads = [p.grad if p.grad is not None else torch.zeros_like(p) for p in params]
    flat = torch.cat([g.reshape(-1) for g in grads])
    dist.all_reduce(flat)
    flat /= world
    i = 0
    for p, g in zip(params, grads):
        n = g.numel()
        p.grad = flat[i:i + n].view_as(p)
        i += n


# ── training ──────────────────────────────────────────────────────────────────

def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m webmix.train")
    ap.add_argument("--adapter", required=True, choices=sorted(ADAPTERS))
    ap.add_argument("--epochs", type=float, default=3)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--alpha", type=int, default=32)
    ap.add_argument("--grad-accum", type=int, default=8)
    ap.add_argument("--beta", type=float, default=0.1, help="KL anchor weight (0 = no anchor rows)")
    ap.add_argument("--anchor-ratio", type=float, default=0.5, help="KL rows per CE row")
    ap.add_argument("--limit", type=int, default=0, help="cap CE rows (smoke tests)")
    ap.add_argument("--max-steps", type=int, default=0, help="stop after this many rows (smoke tests)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--wandb-project", default="webmix-pilot", help="wandb project ('' = no wandb)")
    ap.add_argument("--ce-on", choices=["all", "action"], default="all",
                    help="CE on the whole target (memory + action) or on the action tokens only")
    ap.add_argument("--exclude-variants", default="", help="comma list of replay variants to leave out (recovery,chain)")
    ap.add_argument("--planner-rows", default=None, help="--adapter planner: rows file (default data/webmix/planner/rows.jsonl)")
    ap.add_argument("--frac", type=float, default=1.0,
                    help="scaling: train on this fraction of the generated episodes (whole episodes, nested)")
    ap.add_argument("--episode-ids", default=None,
                    help="train only on the trajectories listed in this file (one task id per line; variants follow)")
    ap.add_argument("--init-adapter", default=None,
                    help="branch-then-specialize (2026-10-01): start from this adapter's weights (same rank/alpha) and "
                         "anchor the KL rows to it (a frozen copy) instead of the base model")
    ap.add_argument("--drop-done", action="store_true",
                    help="review round 1 control (2026-10-05): leave out every episode's final `done` step, so practice does "
                         "not teach the single agent to stop after one primitive (the `macro_done` before it stays)")
    ap.add_argument("--save-every", type=int, default=5000,
                    help="also save the adapter every N rows (out/rows_<n>; 0 = epoch boundaries only)")
    args = ap.parse_args(argv)

    import torch
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForImageTextToText, AutoProcessor

    rank, world, local = _dist()
    main0 = rank == 0
    random.seed(args.seed)
    torch.manual_seed(args.seed)
    fams = set(ADAPTERS[args.adapter])
    if args.adapter == "planner":                # its own rows, split fixed at build time (webmix.planner)
        rows = [json.loads(line) for line in Path(args.planner_rows or PLANNER_ROWS).read_text().split("\n") if line.strip()]
        train = [r for r in rows if r["split"] == "train"]
        val = [r for r in rows if r["split"] == "val"]
        args.beta = 0.0
    else:
        rows = load_rows()
        if args.exclude_variants:
            drop = set(args.exclude_variants.split(","))
            rows = [r for r in rows if _variant(r["task_id"]) not in drop]
        if args.drop_done:
            n0 = len(rows)
            rows = [r for r in rows if r.get("op") != "done"]
            if main0:
                print(f"--drop-done: left out {n0 - len(rows)} final done steps", flush=True)
        ids = set(Path(args.episode_ids).read_text().split()) if args.episode_ids else None
        train = [r for r in rows if not row_is_val(r) and in_frac(r, args.frac) and in_ids(r, ids)]
        val = [r for r in rows if row_is_val(r)]
    ce_rows = [r for r in train if r["family"] in fams]
    kl_pool = [r for r in train if r["family"] not in fams] if args.beta > 0 else []
    if args.limit:
        random.shuffle(ce_rows)
        ce_rows = ce_rows[:args.limit]
    out = Path(args.out) if args.out else OUT_DIR / args.adapter
    out.mkdir(parents=True, exist_ok=True)
    if main0:
        print(f"adapter {args.adapter}: {len(ce_rows)} CE rows ({sorted(fams)}), anchor pool {len(kl_pool)}, "
              f"val {len(val)}, {world} GPU(s)", flush=True)

    device = f"cuda:{local}"
    processor = AutoProcessor.from_pretrained(MODEL)
    model = AutoModelForImageTextToText.from_pretrained(MODEL, dtype=torch.bfloat16, device_map=device,
                                                        attn_implementation="sdpa")
    model.config.use_cache = False
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.enable_input_require_grads()
    model = get_peft_model(model, LoraConfig(r=args.rank, lora_alpha=args.alpha, lora_dropout=0.05, bias="none",
                                             target_modules=TARGET_RE, task_type="CAUSAL_LM"))
    anchor = None
    if args.init_adapter:
        # specialists trained from base on their family's rows alone lost the general habits (scrolling, finding,
        # navigating) pooled_v4 learned from every family; branching from pooled_v4 keeps them
        from peft import set_peft_model_state_dict
        from safetensors.torch import load_file
        sd = load_file(str(Path(args.init_adapter) / "adapter_model.safetensors"))
        res = set_peft_model_state_dict(model, sd)
        missing = [k for k in getattr(res, "missing_keys", []) if "lora_" in k]
        assert not missing, f"--init-adapter left {len(missing)} LoRA weights unset, e.g. {missing[:2]}"
        if args.beta > 0:
            model.load_adapter(args.init_adapter, adapter_name="anchor", is_trainable=False)
            model.set_adapter("default")
            anchor = "anchor"
        if main0:
            print(f"initialized from {args.init_adapter} ({len(sd)} tensors); KL anchor: "
                  f"{'that adapter (frozen)' if anchor else 'none'}", flush=True)
    if main0:
        model.print_trainable_parameters()

    n_kl = int(round(len(ce_rows) * args.anchor_ratio)) if kl_pool else 0
    per_epoch = (len(ce_rows) + n_kl) // world * world         # every rank takes the same number of rows
    total = int(math.ceil(per_epoch * args.epochs)) // world * world
    if args.max_steps:
        total = min(total, args.max_steps // world * world)
    accum = max(1, args.grad_accum // world)                   # rows per rank per optimizer step
    opt_steps = max(1, total // (accum * world))
    params = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(params, lr=args.lr, weight_decay=0.0)
    warm = max(1, int(0.03 * opt_steps))
    sched = torch.optim.lr_scheduler.LambdaLR(
        opt, lambda s: min(1.0, (s + 1) / warm) * 0.5 * (1 + math.cos(math.pi * min(1.0, s / opt_steps))))

    log = open(out / "train_log.jsonl", "a") if main0 else None
    val_fam = [r for r in val if r["family"] in fams]
    random.Random(1).shuffle(val_fam)            # a fixed sample across macros (the file order is alphabetical by macro)
    wb = None
    if args.wandb_project and main0:
        import wandb
        wb = wandb.init(project=args.wandb_project, name=f"{out.name}-{time.strftime('%m%d-%H%M')}", dir=str(out),
                        config={**vars(args), "families": sorted(fams), "base_model": MODEL, "ce_rows": len(ce_rows),
                                "anchor_pool": len(kl_pool), "anchor_rows_per_epoch": n_kl, "val_rows": len(val_fam),
                                "rows_total": total, "optimizer_steps": opt_steps, "gpus": world})
    model.train()
    done, t0, tokens, acc = 0, time.time(), 0, {"ce": [], "kl": []}     # done = rows over all ranks
    saved_at = 0
    epoch = 0
    while done < total:
        batch = [(r, "ce") for r in ce_rows] + [(r, "kl") for r in random.sample(kl_pool, min(n_kl, len(kl_pool)))]
        random.shuffle(batch)                    # the same order on every rank (same seed, same calls)
        batch = batch[:len(batch) // world * world][rank::world]
        batch = batch[:max(0, (total - done) // world)]
        k = 0
        for (r, kind), enc in prefetched(processor, batch):
            logp = target_logprobs(model, enc, device)
            if kind == "ce":
                if args.ce_on == "action":
                    m = enc["action_mask"].to(device).unsqueeze(0).float()
                    loss = -(logp * m).sum() / m.sum().clamp(min=1.0)
                else:
                    loss = -logp.mean()
            else:
                with torch.no_grad():
                    if anchor:                       # the initial adapter, frozen (branch-then-specialize)
                        model.set_adapter(anchor)
                        ref = target_logprobs(model, enc, device)
                        model.set_adapter("default")
                    else:
                        with model.disable_adapter():
                            ref = target_logprobs(model, enc, device)
                d = (ref - logp).clamp(-20.0, 8.0)
                m = enc["action_mask"].to(device).unsqueeze(0).float()
                loss = args.beta * ((torch.exp(d) - d - 1.0) * m).sum() / m.sum().clamp(min=1.0)
            (loss / accum).backward()
            acc[kind].append(loss.item() / (args.beta if kind == "kl" else 1.0))
            tokens += enc["input_ids"].shape[1] * world
            done += world
            k += 1
            if k % accum == 0 or done >= total:
                if world > 1:
                    _allreduce_grads(params, world)
                torch.nn.utils.clip_grad_norm_(params, 1.0)
                opt.step()
                sched.step()
                opt.zero_grad(set_to_none=True)
                # a mid-run checkpoint (a crash loses at most N rows; learning curves come for free)
                if main0 and args.save_every and done < total and done // args.save_every > saved_at // args.save_every:
                    save_adapter(model, out / f"rows_{done}")
                    saved_at = done
            if main0 and (done % (50 * world) == 0 or done >= total):
                el = time.time() - t0
                rec = {"rows": done, "of": total, "epoch": epoch,
                       "ce": sum(acc["ce"]) / max(1, len(acc["ce"])), "kl": sum(acc["kl"]) / max(1, len(acc["kl"])),
                       "lr": sched.get_last_lr()[0], "rows_per_s": done / el, "tokens_per_s": tokens / el,
                       "gpu_gb": torch.cuda.max_memory_allocated() / 2**30}
                log.write(json.dumps(rec) + "\n")
                log.flush()
                print(json.dumps(rec), flush=True)
                if wb:
                    wb.log(rec, step=done)
                acc = {"ce": [], "kl": []}
        epoch += 1
        if done < total:                         # a checkpoint + held-out CE at each epoch boundary
            if main0:
                save_adapter(model, out / f"epoch_{epoch}")
                v = evaluate(model, processor, val_fam[:100], device)
                print(json.dumps({"epoch": epoch, "val_ce": v}), flush=True)
                if wb:
                    wb.log({"val_ce": v, "epoch": epoch}, step=done)
            _barrier(world)
    if not main0:
        _barrier(world)
        return
    save_adapter(model, out)
    val_loss = evaluate(model, processor, val_fam[:200], device)
    meta = {"adapter": args.adapter, "families": sorted(fams), "base_model": MODEL, "ce_rows": len(ce_rows),
            "anchor_pool": len(kl_pool), "rows_trained": done, "val_ce": val_loss, "args": vars(args),
            "minutes": round((time.time() - t0) / 60, 1)}
    (out / "webmix_meta.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta), flush=True)
    if wb:
        wb.log({"val_ce": val_loss, "epoch": epoch}, step=done)
        wb.summary.update({"val_ce_final": val_loss, "minutes": meta["minutes"]})
        wb.finish()
    _barrier(world)


def _barrier(world):
    if world > 1:
        import torch.distributed as dist
        dist.barrier()


def _base_task(task_id):
    """A variant's held-out split follows its (first) source trajectory, so no trajectory leaks across it."""
    return task_id.split("~")[0]


def _variant(task_id):
    return ("recovery" if task_id.endswith("~rec") else "chain" if task_id.startswith("chain-")
            else "taskchain" if task_id.startswith("tchain-") else "plain")


def evaluate(model, processor, rows, device):
    """Mean target-token CE on held-out rows of the adapter's families (None without any)."""
    import torch
    if not rows:
        return None
    model.eval()
    tot = 0.0
    with torch.no_grad():
        for r in rows:
            tot += -target_logprobs(model, encode(processor, r), device).mean().item()
    model.train()
    return tot / len(rows)


if __name__ == "__main__":
    main()
