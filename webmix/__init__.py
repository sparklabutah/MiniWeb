"""WebMix on MiniWeb: family LoRA adapters trained on replayed datagen trajectories.

Design: Claude Doc "WebMix on MiniWeb — ported architecture". Every arm (zero-shot base, pooled,
family adapters, planner) runs the same browser-use harness (`webmix.harness`); training rows are
browser-use's own prompts, recorded by replaying kept datagen trajectories through that harness with
a scripted model (`webmix.replay`), so the prompt format matches the eval by construction.
"""

import os as _os
from pathlib import Path as _Path

# Replayed training rows. Cycle 4 (2026-09-30: pointer-only sliders, retired datagen trajectories,
# recovery / chain augmentations) starts a fresh set; data/webmix/replay holds cycle 3's.
# WEBMIX_REPLAY_DIR points the replay, the training and the planner at another set.
REPLAY_DIR = _Path(_os.environ.get("WEBMIX_REPLAY_DIR",
                                   _Path(__file__).resolve().parent.parent / "data" / "webmix" / "replay_v4")).resolve()
