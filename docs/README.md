# docs/

Project documentation and reference material.

| File | Contents |
|---|---|
| `ARCHITECTURE.md` | System architecture — how the app, sites, data layer, annotation tooling, and eval harness fit together. |
| `macro_system.md` | The two-axis macro model — base macros + reasoning operations, the registry, and how tasks are tagged. |
| `thesis.md` | Long-form write-up / thesis material. |
| `EXTRACTION_ON_COMPUTE_NODE.md` | How the external datasets (GitLab, Reddit, StackExchange, Wikipedia, OSM) were sampled into the DB. The one-time `extract_*` scripts it references were archived to `../MiniWeb-archive/cleanup-20260810/scripts/`. |
| `refined_macro_set.csv` | The current macro set as a CSV (also downloadable from the Macro Template Builder). |
| `*.pptx` | Slide decks — annotation/eval guide, dataset statistics. |

The authoritative, always-loaded project rules live in the root `CLAUDE.md`
(DB access, macro system, "never do" list), not here.
