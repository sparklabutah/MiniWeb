"""Day/night continual learning for web agents (see daynight/README.md).

DAY: a human gives tasks, the day t-1 agent (MiniWebAgent: untrained planner + LoRA executor) attempts them, and the
human corrects it with messages or takes over. NIGHT: a meta-train agent analyzes the logged episodes, proposes
MiniWebGen tasks for the weak macros, and the executor is trained into the day t agent.

Everything a run writes goes under `data/daynight/<experiment>/` (gitignored with the rest of `data/`).
"""
