# tests/

Test suite. Run with:
```
PYTHONPATH=. ~/.conda/envs/miniweb/bin/python -m pytest tests/ -q
```

| File | What it guards |
|---|---|
| `test_macro_registry.py` | Registry drift — the canonical macros (`data/macros.yaml`), their aliases, and operations stay consistent with what the loaders (`annotation/macros.py`) expect. Run it after editing the macro registry or templates. |

Beyond unit tests, the real correctness gates for the verifier set are the
**gold self-check** (each `verifier.json` must pass its own recorded trajectory),
**vacuousness** (must fail an empty trajectory), and **specificity** (should fail
a different task's trajectory) — driven from `evaluation/verifiers.py::verify_task`.
